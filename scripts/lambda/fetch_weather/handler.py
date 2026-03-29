import json
import logging
import os
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

import boto3
import redis

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


def fetch_all_weather() -> tuple[dict, dict]:
    """
    Fetch air temperature, humidity, and rainfall, then merge into a
    single dict keyed by station ID.

    Returns:
        (processed_result, raw_data_dict)
    """
    merged_stations: dict[str, dict] = {}
    raw_responses: dict[str, dict] = {}

    for metric, url in API_URLS.items():
        logger.info("Fetching %s from %s", metric, url)
        raw = _fetch_json(url)
        raw_responses[metric] = raw

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

    processed = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "stations": merged_stations,
    }

    return processed, raw_responses


def upload_to_s3(data: dict, bucket_name: str) -> str:
    """
    Upload processed weather data to S3.
    Key format: weather/YYYY-MM-DD/HH-MM/processed.json
    """
    now = datetime.now(timezone.utc)
    date_path = now.strftime('%Y-%m-%d')
    time_path = now.strftime('%H-%M')
    s3_key = f"weather/{date_path}/{time_path}/processed.json"

    s3_client = boto3.client("s3")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json.dumps(data),
        ContentType="application/json",
    )

    logger.info("Uploaded processed weather data to s3://%s/%s", bucket_name, s3_key)
    return s3_key


def upload_raw_responses(raw_responses: dict, bucket_name: str):
    """
    Upload raw API responses for each metric.
    Key format: weather/YYYY-MM-DD/HH-MM/raw/metric.json
    """
    now = datetime.now(timezone.utc)
    date_path = now.strftime('%Y-%m-%d')
    time_path = now.strftime('%H-%M')
    
    s3_client = boto3.client("s3")
    for metric, data in raw_responses.items():
        s3_key = f"weather/{date_path}/{time_path}/raw/{metric}.json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(data),
            ContentType="application/json",
        )
        logger.info("Uploaded raw %s to s3://%s/%s", metric, bucket_name, s3_key)


def lambda_handler(event, _context):
    """
    Entry point for the OUTSIDE VPC Lambda.
    Fetches weather, stores raw data in S3, then invokes the INSIDE VPC Lambda.
    """
    logger.info("Event: %s", json.dumps(event))

    bucket_name = os.environ.get("S3_BUCKET_NAME")
    pusher_lambda = os.environ.get("PUSH_WEATHER_LAMBDA")

    if not bucket_name:
        logger.error("S3_BUCKET_NAME environment variable is not set")
        return {"statusCode": 500, "body": "S3_BUCKET_NAME not configured"}

    try:
        processed, raw_responses = fetch_all_weather()
        logger.info("Successfully fetched weather for %d stations", len(processed["stations"]))

        # 1. Upload processed and raw results to S3 (Works outside VPC)
        s3_key = upload_to_s3(processed, bucket_name)
        upload_raw_responses(raw_responses, bucket_name)

        # 2. Transition the bridge: Invoke the VPC-bound Lambda (Works outside VPC)
        if pusher_lambda:
            logger.info("Invoking pusher lambda: %s", pusher_lambda)
            lambda_client = boto3.client("lambda")
            lambda_client.invoke(
                FunctionName=pusher_lambda,
                InvocationType="Event",  # Asynchronous call
                Payload=json.dumps(processed)
            )
        else:
            logger.warning("PUSH_WEATHER_LAMBDA not set; skipping cache update")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Weather data fetched and uploaded. Bridge invoke sent.",
                "s3_key": s3_key,
                "station_count": len(processed["stations"]),
            }),
        }
    except Exception as exc:
        logger.exception("Error fetching weather data")
        return {"statusCode": 500, "body": str(exc)}


def pusher_handler(event, _context):
    """
    Entry point for the INSIDE VPC Lambda.
    Receives processed data and pushes it to ElastiCache.
    """
    logger.info("Pusher event received")
    
    endpoint = os.environ.get("ELASTICACHE_ENDPOINT")
    port = os.environ.get("ELASTICACHE_PORT", "6379")

    if not endpoint:
        logger.error("ELASTICACHE_ENDPOINT not set")
        return

    try:
        r = redis.Redis(host=endpoint, port=int(port), ssl=True, decode_responses=True)
        # Event is the processed weather data sent from lambda_handler
        r.set("weather:latest", json.dumps(event), ex=900)
        logger.info("Successfully pushed weather data to ElastiCache via bridge")
    except Exception as exc:
        logger.error("Failed to push to ElastiCache: %s", exc)


# Allow running locally for testing: python handler.py
if __name__ == "__main__":
    processed, _ = fetch_all_weather()
    print(json.dumps(processed, indent=2))
