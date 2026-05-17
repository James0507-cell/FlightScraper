# FlightScraper Core Logic

This document explains how the Google Flights scraper works internally.

## Overview

The scraper uses **Playwright** and an **asyncio-based concurrent architecture** to efficiently retrieve flight data. It follows a **Hybrid Search Strategy**, combining direct URL navigation with real-time UI interactions.

## Key Components

### 1. Hybrid Search Approach
Instead of relying solely on complex URL parameters (which Google often changes), the scraper:
1.  **Constructs a base URL** with the origin, destination, and date.
2.  **Navigates** to that URL to reach the results page.
3.  **Applies Filters via UI:** It interacts with dropdown menus (Stops, Bags, Price) using automated clicks and keyboard inputs.

### 2. Intelligent Card Expansion
Google Flights hides many details (flight numbers, aircraft models, legroom) until a card is expanded.
-   The scraper identifies "valid" flight cards based on their `aria-label` content.
-   It uses **JavaScript-based clicks** to bypass overlapping elements and reliably trigger the "Flight details" view.

### 3. Data Extraction & Cleaning
-   **Regex Matching:** Uses sophisticated regular expressions to extract flight numbers, aircraft types (Airbus/Boeing), and emission data from raw text.
-   **Amenity Detection:** Scans the expanded card for keywords like "USB outlet," "Wi-Fi," and "legroom."
-   **Baggage Extraction:** Pulls the actual descriptive text from the web (e.g., "Checked baggage for a fee") rather than using hardcoded values.
-   **Overnight Detection:** Checks for the `+1` indicator in arrival times to set an `is_overnight` flag.

### 4. Concurrency Management
To speed up scraping, the script uses `asyncio.Semaphore` to process multiple flight cards in parallel using separate browser pages within a single context.

### 5. Null-Safe Data Model
The scraper initializes all fields as `null` (Python `None`). If information is missing from the web page, it remains `null` in the final JSON, ensuring a clean and predictable data structure for downstream applications.
