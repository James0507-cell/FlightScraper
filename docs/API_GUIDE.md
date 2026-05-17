# Scraper API Guide

This guide explains how to interact with the flight scraper via the FastAPI server.

## Getting Started

1.  **Start the server:**
    ```bash
    python server.py
    ```
2.  **Base URL:** `http://localhost:8000`

## Endpoints

### 1. Scrape Flights
`GET /scrape`

Triggers the scraper with the specified parameters and returns a JSON list of flight details.

#### Query Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `origin` | string | `DVO` | Origin airport code (e.g., MNL, LHR). |
| `dest` | string | `MNL` | Destination airport code (e.g., DVO, JFK). |
| `date` | string | `2026-06-05` | Travel date in `YYYY-MM-DD` format. |
| `stops` | string | `null` | Filter by stops: `nonstop`, `1stop`, `2stops`, `any`. |
| `bags` | integer | `1` | Number of carry-on bags to include. |
| `max_price` | integer | `4000` | Maximum price limit in local currency. |
| `limit` | integer | `10` | Maximum number of flights to return. |
| `airlines` | list | `null` | Optional list of airlines to filter (repeat param). |

#### Example Requests

*   **Default Search:**
    `GET http://localhost:8000/scrape`
*   **Custom Route & Nonstop:**
    `GET http://localhost:8000/scrape?origin=MNL&dest=DVO&stops=nonstop`
*   **Strict Budget Search:**
    `GET http://localhost:8000/scrape?max_price=3000&bags=0`

### 2. Health Check
`GET /health`

Returns the current status of the server.

#### Response
```json
{ "status": "healthy" }
```

## Response Format

The `/scrape` endpoint returns a structured JSON response:

```json
{
  "status": "success",
  "count": 1,
  "data": [
    {
      "airline": "Philippine Airlines",
      "price": "₱3997",
      "cabin": "Economy",
      "is_overnight": false,
      "departure": {
        "time": "2:00 AM",
        "airport": "Davao International Airport (DVO)"
      },
      "amenities": ["Below average legroom (28 in)"],
      "baggage": ["Checked baggage for a fee"],
      "flight_info": ["Airbus A320", "PR 2808"],
      "booking_options": [...]
    }
  ]
}
```

## Error Handling

If a scraping task fails or navigation times out, the API will return a `500 Internal Server Error` with details about the failure.
