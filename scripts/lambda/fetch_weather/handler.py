"""
Fetch Weather Data from data.gov.sg as a Lambda function

Pulls real-time air temperature, relative humidity, and rainfall
data from Singapore's open data APIs and returns a consolidated
weather snapshot keyed by station. Uploads results to S3.
"""

import json
import logging
import os
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

API_URLS = {
    "air_temperature": "https://api-open.data.gov.sg/v2/real-time/api/air-temperature",
    "relative_humidity": "https://api-open.data.gov.sg/v2/real-time/api/relative-humidity",
    "rainfall": "https://api-open.data.gov.sg/v2/real-time/api/rainfall",
}

READING_UNITS = {
    "air_temperature": "°C",
    "relative_humidity": "%",
    "rainfall": "mm",
}


def _fetch_json(url: str) -> dict:
    """Fetch from URL"""
    req = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "CycleLink/1.0",
        },
    )
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        raise


def _parse_response(raw: dict) -> tuple[dict, list]:
    """
    Parses real-time weather response.

    Returns:
        stations: dict mapping station_id -> station metadata
        readings: list of {stationId, value} from the latest reading
    """
    data = raw.get("data", {})

    stations = {}
    for s in data.get("stations", []):
        stations[s["id"]] = {
            "name": s["name"],
            "latitude": s["location"]["latitude"],
            "longitude": s["location"]["longitude"],
        }

    readings_list = data.get("readings", [])
    latest_reading = readings_list[0] if readings_list else {}

    return stations, latest_reading


def fetch_all_weather() -> dict:
    """
    Fetch air temperature, humidity, and rainfall, then merge into a
    single dict keyed by station ID.

    Returns:
        {
            "fetched_at": "...",
            "stations": {
                "S109": {
                    "name": "Ang Mo Kio Avenue 5",
                    "latitude": 1.3764,
                    "longitude": 103.8492,
                    "air_temperature": {"value": 30.1, "unit": "°C"},
                    "relative_humidity": {"value": 63.3, "unit": "%"},
                    "rainfall": {"value": 0, "unit": "mm"},
                },
                ...
            }
        }
    """
    merged_stations: dict[str, dict] = {}

    for metric, url in API_URLS.items():
        logger.info("Fetching %s from %s", metric, url)
        raw = _fetch_json(url)

        if raw.get("code") != 0:
            logger.warning("Non-zero response code for %s: %s", metric, raw.get("errorMsg"))
            continue

        stations, latest_reading = _parse_response(raw)
        timestamp = latest_reading.get("timestamp", "")

        # Ensure every station has a base entry
        for station_id, meta in stations.items():
            if station_id not in merged_stations:
                merged_stations[station_id] = {
                    "name": meta["name"],
                    "latitude": meta["latitude"],
                    "longitude": meta["longitude"],
                }

        # Attach the reading values
        for reading in latest_reading.get("data", []):
            sid = reading["stationId"]
            if sid in merged_stations:
                merged_stations[sid][metric] = {
                    "value": reading["value"],
                    "unit": READING_UNITS[metric],
                    "timestamp": timestamp,
                }

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "stations": merged_stations,
    }


def upload_to_s3(data: dict, bucket_name: str) -> str:
    """
    Upload weather data to S3 as a JSON file.

    Key format: weather/YYYY-MM-DD/HH-MM.json
    Returns the S3 key of the uploaded object.
    """
    now = datetime.now(timezone.utc)
    s3_key = f"weather/{now.strftime('%Y-%m-%d')}/{now.strftime('%H-%M')}.json"

    s3_client = boto3.client("s3")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json.dumps(data),
        ContentType="application/json",
    )

    logger.info("Uploaded weather data to s3://%s/%s", bucket_name, s3_key)
    return s3_key


def lambda_handler(event, _context):
    """AWS Lambda entry point."""
    logger.info("Event: %s", json.dumps(event))

    bucket_name = os.environ.get("S3_BUCKET_NAME")
    if not bucket_name:
        logger.error("S3_BUCKET_NAME environment variable is not set")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "S3_BUCKET_NAME not configured"}),
        }

    try:
        result = fetch_all_weather()
        logger.info("Successfully fetched weather for %d stations", len(result["stations"]))

        s3_key = upload_to_s3(result, bucket_name)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "message": "Weather data fetched and uploaded",
                    "s3_key": s3_key,
                    "station_count": len(result["stations"]),
                }
            ),
        }
    except Exception as exc:
        logger.exception("Error fetching weather data")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(exc)}),
        }


# Allow running locally for testing: python handler.py
if __name__ == "__main__":
    # For local testing, just fetch and print (skip S3 upload)
    result = fetch_all_weather()
    print(json.dumps(result, indent=2))
