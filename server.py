import asyncio
from fastapi import FastAPI, HTTPException, Query
from typing import Optional, List
from main import scrape_google_flights
import uvicorn

app = FastAPI(title="Google Flights Scraper API")

@app.get("/scrape")
async def scrape_flights(
    origin: str = "DVO",
    dest: str = "MNL",
    date: str = "2026-06-05",
    flight_type: str = "oneway",
    limit: int = 10,
    concurrency: int = 2,
    stops: Optional[str] = None,
    bags: Optional[int] = 1,
    airlines: Optional[List[str]] = Query(None),
    max_price: Optional[int] = 4000
):
    """
    Endpoint to scrape Google Flights based on provided parameters and filters.
    """
    filters = {}
    if stops: filters["stops"] = stops
    if bags is not None: filters["bags"] = bags
    if airlines: filters["airlines"] = airlines
    if max_price is not None: filters["max_price"] = max_price

    try:
        log_message = f"API Request: {origin} -> {dest} on {date}, filters={filters}"
        print(log_message)
        
        results = await scrape_google_flights(
            origin, 
            dest, 
            date, 
            flight_type=flight_type, 
            concurrency=concurrency, 
            limit=limit,
            filters=filters
        )
        
        return {
            "status": "success",
            "count": len(results),
            "data": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
