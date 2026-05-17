import asyncio
import json
import re
from urllib.parse import quote, urlparse
from playwright.async_api import async_playwright

CARD_SELECTOR = '[aria-label*="Select flight"]'
BOOKING_BUTTON_SELECTOR = 'button[aria-label^="Continue"]'

def clean_text(text, keep_newlines=False):
    """
    Normalizes whitespace and removes non-breaking space artifacts.
    """
    if not text:
        return ""
    text = text.replace('\u00a0', ' ').replace('\u202f', ' ').replace('\u2007', ' ')
    if keep_newlines:
        lines = [re.sub(r'[ \t\f\v]+', ' ', line).strip() for line in text.split('\n')]
        return '\n'.join(lines)
    else:
        return re.sub(r'\s+', ' ', text).strip()

def log_message(message):
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", "replace").decode("ascii"))

async def dismiss_consent(page):
    for selector in (
        'button:has-text("Reject all")',
        'button:has-text("Accept all")',
        'button:has-text("I agree")',
    ):
        button = page.locator(selector).first
        if await button.count():
            try:
                await button.click(timeout=3000)
                return
            except Exception:
                continue

async def goto_flights_results(page, search_url, attempts=3):
    last_error = None
    for attempt in range(attempts):
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            await dismiss_consent(page)
            await page.wait_for_selector(CARD_SELECTOR, timeout=30000)
            return
        except Exception as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
            await page.wait_for_timeout(1500 * (attempt + 1))
    raise last_error

async def get_valid_cards(page):
    cards = page.locator(CARD_SELECTOR)
    count = await cards.count()
    valid_cards = []
    # Only check the first 30 cards to avoid timeouts
    for i in range(min(count, 30)):
        card = cards.nth(i)
        try:
            label = await card.get_attribute('aria-label', timeout=2000)
            if label and label.strip() != "Select flight" and len(label) > 50:
                valid_cards.append(card)
        except Exception:
            continue
    return valid_cards

async def reveal_booking_options(page, card, attempts=3):
    last_error = None
    container = card.locator(
        "xpath=ancestor::*[@role='listitem' or self::li or contains(@class, 'pI9V6b')][1]"
    ).first
    for attempt in range(attempts):
        try:
            await container.scroll_into_view_if_needed(timeout=10000)
            try:
                await click_locator(card, timeout=10000)
            except Exception:
                await click_locator(container, timeout=10000)
            await page.wait_for_selector(BOOKING_BUTTON_SELECTOR, timeout=12000)
            return
        except Exception as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
            await page.wait_for_timeout(1000 * (attempt + 1))
    raise last_error

def build_favicon_url(url):
    if not url or "google.com/travel/clk" in url:
        return None
    try:
        hostname = urlparse(url).hostname
    except Exception:
        hostname = None
    if not hostname:
        return None
    return f"https://www.google.com/s2/favicons?domain={hostname}&sz=64"

def guess_provider_favicon(provider_name):
    normalized = re.sub(r'[^a-z0-9.]', '', (provider_name or '').lower())
    if not normalized:
        return None
    domain = normalized if "." in normalized else f"{normalized}.com"
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"

def pick_provider_logo(provider_name, extracted_logo, airline_name, airline_logo, redirect_url):
    if extracted_logo:
        return extracted_logo
    if provider_name and airline_name and provider_name.lower() == airline_name.lower():
        return airline_logo
    return build_favicon_url(redirect_url) or guess_provider_favicon(provider_name)

async def click_locator(locator, timeout=10000):
    try:
        await locator.click(timeout=timeout)
    except Exception:
        await locator.evaluate("el => el.click()")

def append_unique(target_list, value):
    cleaned = clean_text(value)
    if cleaned and cleaned not in target_list:
        target_list.append(cleaned)

import argparse

async def process_flight(context, search_url, index, semaphore):
    """
    Processes a single flight entry: expands details, extracts rich data, logos, and gets booking links.
    """
    async with semaphore:
        page = await context.new_page()
        try:
            log_message(f"  [Task {index+1}] Navigating...")
            await goto_flights_results(page, search_url)
            
            valid_cards = await get_valid_cards(page)
            
            if index >= len(valid_cards):
                log_message(f"  [Task {index+1}] Card index {index} not found in {len(valid_cards)} valid cards.")
                return None
            
            card = valid_cards[index]
            raw_aria_label = await card.get_attribute('aria-label', timeout=5000) or ""
            aria_label = clean_text(raw_aria_label)
            log_message(f"  [Task {index+1}] Found card: {aria_label[:50]}...")

            container = card.locator(
                "xpath=ancestor::*[@role='listitem' or self::li or contains(@class, 'pI9V6b')][1]"
            ).first
            
            # Extract Airline Logo
            airline_logo_url = await card.evaluate("""el => {
                const container = el.closest('li, [role="listitem"], .pI9V6b');
                if (!container) return null;
                const logos = container.querySelectorAll('div[style*="image"], img');
                for (const logo of logos) {
                    let src = null;
                    if (logo.tagName === 'IMG') {
                        src = logo.src;
                    } else {
                        const style = logo.getAttribute('style');
                        const match = style.match(/url\\((.*?)\\)/);
                        if (match) src = match[1].replace(/['"]/g, '');
                    }
                    if (src && !src.includes('arrow') && !src.includes('info') && !src.includes('battery')) {
                        return src;
                    }
                }
                return null;
            }""")

            # Expand details
            expand_btn = container.locator('button[aria-label*="Flight details"], button[aria-label*="Expand"]').first
            if await expand_btn.count():
                log_message(f"  [Task {index+1}] Expanding flight details...")
                await expand_btn.evaluate("el => el.click()")
                await page.wait_for_timeout(2000)
            else:
                log_message(f"  [Task {index+1}] No expand button found, clicking card...")
                await card.evaluate("el => el.click()")
                await page.wait_for_timeout(2000)
            
            # Extract text
            raw_container_text = await container.evaluate("el => el.innerText")
            container_text = clean_text(raw_container_text, keep_newlines=True)
            lines = [line.strip() for line in container_text.split('\n') if line.strip()]
            full_text = clean_text(raw_container_text)
            
            flight_data = {
                "airline": None,
                "airline_logo": airline_logo_url,
                "price": None,
                "cabin": None,
                "duration": None,
                "is_overnight": False,
                "departure": {"time": None, "airport": None},
                "landing": {"time": None, "airport": None},
                "emissions": {"amount": None, "comparison": None, "contrail": None},
                "amenities": [],
                "baggage": [],
                "flight_info": [],
                "booking_options": []
            }

            # Summary parsing
            price_match = re.search(r'([₱$£€][\d,]+)', aria_label)
            if not price_match:
                price_match = re.search(r'(\d[\d,]*) (?:Philippine pesos|pounds|dollars|euros|euro)', aria_label, re.I)
            
            if price_match:
                price_val = price_match.group(1).replace(',', '')
                if 'peso' in price_match.group(0).lower(): flight_data["price"] = "₱" + price_val
                elif 'pound' in price_match.group(0).lower(): flight_data["price"] = "£" + price_val
                elif 'dollar' in price_match.group(0).lower(): flight_data["price"] = "$" + price_val
                elif 'euro' in price_match.group(0).lower(): flight_data["price"] = "€" + price_val
                else: flight_data["price"] = price_match.group(1)

            airline_match = re.search(r'with (.*?)\.', aria_label)
            if airline_match: flight_data["airline"] = airline_match.group(1)
            
            duration_match = re.search(r'duration (.*?)\.', aria_label)
            if duration_match: flight_data["duration"] = duration_match.group(1)

            # Overnight check: Look for "+1" or "arrives ... next day" in aria-label or full text
            if "+1" in aria_label or "+1" in full_text or "next day" in full_text.lower():
                flight_data["is_overnight"] = True

            # Cabin parsing
            for cabin_type in ["Economy", "Premium Economy", "Business", "First"]:
                if cabin_type in full_text:
                    flight_data["cabin"] = cabin_type
                    break

            # Location and Time Extraction
            time_pattern = r'(\d{1,2}:\d{2}\s?(?:AM|PM))\s*(.*)'
            found_locations = []
            for line in lines:
                match = re.search(time_pattern, line, re.I)
                if match:
                    # Clean up the location text - often it has junk like "7:05 AM on Mon, Jun 1"
                    loc_text = match.group(2).strip()
                    loc_text = re.sub(r'on\s+[A-Z][a-z]{2},\s+[A-Z][a-z]{2}\s+\d+', '', loc_text).strip()
                    found_locations.append({
                        "time": match.group(1).strip(),
                        "airport": loc_text
                    })
            
            if len(found_locations) >= 2:
                # First is departure, last is landing (to handle layovers)
                flight_data["departure"] = found_locations[0]
                flight_data["landing"] = found_locations[-1]
            
            # Fallback for locations if empty
            if not flight_data["departure"]["airport"] or not flight_data["landing"]["airport"]:
                journey_match = re.search(
                    r'Leaves (.*?) at (\d{1,2}:\d{2}\s?(?:AM|PM)).*?arrives at (.*?) at (\d{1,2}:\d{2}\s?(?:AM|PM))',
                    aria_label,
                    re.I,
                )
                if journey_match:
                    if not flight_data["departure"]["time"]: flight_data["departure"]["time"] = journey_match.group(2).strip()
                    if not flight_data["departure"]["airport"]: flight_data["departure"]["airport"] = journey_match.group(1).strip()
                    if not flight_data["landing"]["time"]: flight_data["landing"]["time"] = journey_match.group(4).strip()
                    if not flight_data["landing"]["airport"]: flight_data["landing"]["airport"] = journey_match.group(3).strip()

            # Dynamic classification
            for i, line in enumerate(lines):
                low_line = line.lower()
                
                # Filter out very long lines that are likely UI blocks
                if len(line) > 150:
                    continue

                # Emissions
                if "co2e" in low_line:
                    amount_match = re.search(r'(\d+)\s*kg\s*co2e', line, re.I)
                    if amount_match:
                        flight_data["emissions"]["amount"] = amount_match.group(0)
                    elif i > 0 and "emissions" in lines[i-1].lower():
                         flight_data["emissions"]["amount"] = line
                
                if "emissions" in low_line and ("%" in line or "avg" in line or "typical" in low_line):
                    flight_data["emissions"]["comparison"] = line
                elif "contrail" in low_line:
                    flight_data["emissions"]["contrail"] = line
                
                # Amenities - expanded list
                amenity_keywords = [
                    "legroom", "wi-fi", "outlet", "usb", "entertainment", 
                    "stream", "on-demand video", "power", "seatback"
                ]
                if any(kw in low_line for kw in amenity_keywords):
                    append_unique(flight_data["amenities"], line)
                
                # Baggage - capture actual descriptive text
                if "bag" in low_line and ("fee" in low_line or "included" in low_line or "access" in low_line):
                    # Filter out noise like "If you need a carry-on bag, use the Bags filter"
                    if "filter" not in low_line and "update prices" not in low_line and "Departure" not in line:
                        append_unique(flight_data["baggage"], line)
                
                # Flight Info
                if re.search(r'^(?:[A-Z0-9]{2}\s?\d{2,4}|(?:Airbus|Boeing|Embraer)\b)', line):
                    # Avoid adding common noise
                    if len(line) > 3 and "Departure" not in line:
                        append_unique(flight_data["flight_info"], line)

            # Global regex fallbacks
            amenity_patterns = [
                r'.*?legroom\s*\(\d+\s*in\)',
                r'Wi-?Fi(?: for a fee| included)?',
                r'.*?USB outlet',
                r'.*?Power outlet',
                r'On-demand video',
                r'Seatback entertainment',
                r'Stream media to your device'
            ]
            for pat in amenity_patterns:
                for match in re.findall(pat, full_text, re.I):
                    if len(match) < 150:
                        append_unique(flight_data["amenities"], match)

            baggage_patterns = [
                r'Checked baggage(?: for a fee| included)?',
                r'Carry-on bag(?: for a fee| included)?',
                r'Overhead bin access(?: for a fee| included)?',
                r'This price does not include overhead bin access'
            ]
            for pat in baggage_patterns:
                for match in re.findall(pat, full_text, re.I):
                    if "Departure" not in match and "Select" not in match:
                        append_unique(flight_data["baggage"], match)

            aircraft_match = re.search(
                r'(Airbus\s+A\d{3}(?:neo)?|Boeing\s+\d{3}(?:-\d{3})?|Embraer\s+E?\d{3})',
                full_text,
                re.I,
            )
            if aircraft_match:
                append_unique(flight_data["flight_info"], aircraft_match.group(1))

            # Improved flight number regex: 2 chars + space? + 1-4 digits
            # We filter this to ensure it looks like a real flight number (e.g., SK 802)
            for match in re.findall(r'\b([A-Z][A-Z0-9]\s?\d{1,4})\b', full_text):
                if match not in ["CO2", "LHR", "JFK", "CDG", "LGW"]: # Filter obvious airport codes
                    append_unique(flight_data["flight_info"], match)

            # 5. Booking details and provider logos
            await reveal_booking_options(page, card)
            
            # Refined provider extraction logic
            provider_containers = await page.locator(f'div[role="list"] > div:has({BOOKING_BUTTON_SELECTOR})').all()
            if not provider_containers:
                 # Fallback to direct buttons
                 provider_containers = await page.locator(BOOKING_BUTTON_SELECTOR).all()

            for p_container in provider_containers[:3]:
                # Reach the button
                is_btn = await p_container.get_attribute('aria-label') is not None
                btn = p_container if is_btn else p_container.locator('button[aria-label^="Continue"]').first
                if not await btn.count(): continue
                
                p_label = clean_text(await btn.get_attribute('aria-label') or "")
                
                # Extract Provider Logo from the expanded booking view
                p_logo_url = await btn.evaluate("""el => {
                    const scopes = [
                        el.closest('li, [role="listitem"], .mxvQLc, div[jscontroller], div[data-ved]'),
                        el.parentElement,
                        el
                    ].filter(Boolean);
                    const isUseful = (src) => src
                        && !src.startsWith('data:')
                        && !src.includes('arrow')
                        && !src.includes('info')
                        && !src.includes('battery')
                        && src.length > 10;

                    for (const scope of scopes) {
                        const nodes = scope.querySelectorAll('img, [style*="background"], [style*="image"]');
                        for (const node of nodes) {
                            let src = null;
                            if (node.tagName === 'IMG') {
                                src = node.currentSrc || node.src;
                            } else {
                                const style = node.getAttribute('style') || '';
                                const match = style.match(/url\\((.*?)\\)/);
                                if (match) src = match[1].replace(/['"]/g, '');
                            }
                            if (isUseful(src)) return src;
                        }
                    }
                    return null;
                }""")

                try:
                    async with page.expect_popup(timeout=5000) as popup_info:
                        await click_locator(btn, timeout=5000)
                    popup = await popup_info.value
                    try:
                        await popup.wait_for_load_state("domcontentloaded", timeout=10000)
                        await popup.wait_for_timeout(1500)
                    except Exception:
                        pass
                    redirect_url = popup.url
                    await popup.close()
                except Exception:
                    redirect_url = "Dynamic - Check details"
                
                p_name = None
                if 'with ' in p_label:
                    p_name = p_label.split('with ')[1].split(' airline')[0].split(' for')[0]

                flight_data["booking_options"].append({
                    "provider": p_name,
                    "provider_logo": pick_provider_logo(
                        p_name,
                        p_logo_url,
                        flight_data["airline"],
                        airline_logo_url,
                        redirect_url,
                    ),
                    "url": redirect_url,
                    "full_info": p_label
                })

            # Final cleanup: if lists are empty, keep them as None.
            if not flight_data["amenities"]: flight_data["amenities"] = None
            if not flight_data["baggage"]: flight_data["baggage"] = None
            if not flight_data["flight_info"]: flight_data["flight_info"] = None
            if not flight_data["booking_options"]: flight_data["booking_options"] = None

            log_message(f"  [Task {index+1}] Completed: {flight_data['airline']} ({flight_data['price']})")
            return flight_data
        except Exception as e:
            log_message(f"  [Task {index+1}] Failed: {str(e)[:100]}")
            try:
                await page.screenshot(path=f"error_task_{index+1}.png")
            except:
                pass
            return None
        finally:
            await page.close()

async def scrape_google_flights(origin, destination, date, flight_type='oneway', concurrency=5, limit=10):
    """
    Main entry point for concurrent Google Flights scraping.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        search_query = f"Flights to {destination} from {origin} on {date} {flight_type}"
        search_url = f"https://www.google.com/travel/flights?q={quote(search_query)}"
        
        log_message(f"Navigating to {search_url}...")
        main_page = await context.new_page()
        try:
            await goto_flights_results(main_page, search_url)
            valid_cards = await get_valid_cards(main_page)
        except Exception as e:
            log_message(f"Initial navigation failed: {e}")
            await main_page.screenshot(path="navigation_error.png")
            await browser.close()
            return []

        indices_to_scrape = list(range(min(limit, len(valid_cards))))
        
        await main_page.close()
        effective_concurrency = max(1, min(concurrency, 3))
        log_message(f"Processing {len(indices_to_scrape)} flights with concurrency={effective_concurrency}...")

        semaphore = asyncio.Semaphore(effective_concurrency)
        tasks = [process_flight(context, search_url, i, semaphore) for i in indices_to_scrape]
        
        results = await asyncio.gather(*tasks)
        results = [r for r in results if r is not None]
        
        await browser.close()
        return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Flights Scraper")
    parser.add_argument("--origin", default="LON", help="Origin airport code")
    parser.add_argument("--dest", default="PAR", help="Destination airport code")
    parser.add_argument("--date", default="2026-06-01", help="Date in YYYY-MM-DD")
    parser.add_argument("--type", default="oneway", help="Flight type (oneway/roundtrip)")
    parser.add_argument("--limit", type=int, default=5, help="Max flights to scrape")
    parser.add_argument("--concurrency", type=int, default=2, help="Max concurrent tasks")
    
    args = parser.parse_args()
    
    data = asyncio.run(scrape_google_flights(
        args.origin, args.dest, args.date, 
        flight_type=args.type, 
        concurrency=args.concurrency, 
        limit=args.limit
    ))
    
    output_file = "flights.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    log_message(f"\nSuccessfully scraped {len(data)} flights.")
    log_message(f"Output saved to: {output_file}")
