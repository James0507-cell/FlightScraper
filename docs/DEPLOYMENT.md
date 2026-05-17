# Deployment Guide

This guide explains how to deploy the FlightScraper service using Docker.

## Prerequisites

- Install [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/).

## Deployment Instructions

### 1. Build the Docker Image
From the project root, run:
```bash
docker-compose build
```

### 2. Run the Service
Start the container in detached mode:
```bash
docker-compose up -d
```

### 3. Verification
Verify that the service is running:
```bash
curl http://localhost:8000/health
```

### 4. Stopping the Service
To stop the running container:
```bash
docker-compose down
```

## Production Considerations
- **Environment Variables:** For production, consider using environment variables for configuration.
- **Data Persistence:** The current configuration mounts the current directory as a volume (`.:/app`). In production, you might want to isolate the application files and handle `flights.json` persistence separately.
- **Headless Mode:** The service runs Playwright in `headless=True` mode by default, which is appropriate for server environments.
