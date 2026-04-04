# Proxy Data for Nanji Parking Prediction

This folder contains scripts to fetch external proxy data for predicting parking availability at Nanji Park.

## Data Sources

1. **Seoul City Real-time Data** (`fetch_city_data.py`): Real-time population, traffic, parking, weather, events in Seoul areas.
2. **Seoul Population Data** (`fetch_population_data.py`): Real-time population data for Seoul areas.
3. **Cultural Events** (`fetch_cultural_events.py`): Information on cultural events in Seoul.
4. **Traffic Info** (`fetch_traffic_info.py`): Real-time road traffic information.
5. **Incident Info** (`fetch_incident_info.py`): Real-time incident reports.
6. **Weather Forecast** (`fetch_weather_forecast.py`): Short-term weather forecast from KMA.
7. **Bike Usage** (`fetch_bike_usage.py`): Hourly bike rental usage data.

## Usage

1. Obtain API keys from data.go.kr for each service.
2. Replace `'your_api_key_here'` or `'sample'` with your actual API key in each script.
3. Run each Python script: `python fetch_*.py`
4. Data will be saved as JSON files in this folder.

Note: Some APIs allow sample keys for limited access (e.g., only 'Gwanghwamun·Deoksugung' area).

## Purpose

These data serve as proxies for parking demand patterns at Nanji Park, since direct historical parking data is unavailable.