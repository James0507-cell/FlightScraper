import asyncio
from playwright.async_api import async_playwright
from urllib.parse import quote

async def research():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Search for a long-haul flight to likely get overnight and more amenities
        search_query = "Flights to JFK from LHR on 2026-06-01"
        search_url = f"https://www.google.com/travel/flights?q={quote(search_query)}"
        
        print(f"Navigating to {search_url}...")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        
        # Handle consent
        for selector in ('button:has-text("Reject all")', 'button:has-text("Accept all")', 'button:has-text("I agree")'):
            btn = page.locator(selector).first
            if await btn.count():
                await btn.click()
                break

        # Wait for cards
        try:
            await page.wait_for_selector('[aria-label*="Select flight"]', timeout=30000)
        except:
            print("No cards found.")
            await browser.close()
            return

        cards = await page.locator('[aria-label*="Select flight"]').all()
        
        # Find a card that might be overnight (usually shows "+1")
        card_to_expand = cards[0]
        for card in cards[:10]:
            label = await card.get_attribute('aria-label') or ""
            if "+1" in label or "arrives" in label.lower():
                card_to_expand = card
                break

        print(f"Expanding card: {await card_to_expand.get_attribute('aria-label')}")
        
        # Get container
        container = card_to_expand.locator(
            "xpath=ancestor::*[@role='listitem' or self::li or contains(@class, 'pI9V6b')][1]"
        ).first
        
        # Expand
        expand_btn = container.locator('button[aria-label*="Flight details"], button[aria-label*="Expand"]').first
        if await expand_btn.count():
            await expand_btn.evaluate("el => el.click()")
            await page.wait_for_timeout(3000)
        
        # Capture the HTML of the expanded container
        html = await container.evaluate("el => el.outerHTML")
        
        with open("amenities_research.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("HTML saved to amenities_research.html")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(research())
