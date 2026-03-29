# This script is used to import community routes from Google Maps into the database.

# These routes are sourced from https://pcncyclingsingapore.wordpress.com/.
# View Online: https://www.google.com/maps/d/u/0/embed?mid=13PRb7OmKXskuiAm_a5bujIIDO3NK4Gn9&ll=1.3642079937535965%2C103.83212786689772&z=12
# KML Download: https://www.google.com/maps/d/kml?forcekml=1&mid=13PRb7OmKXskuiAm_a5bujIIDO3NK4Gn9

# Usage:
#   Local only (JSON, no DB upload):
#     uv run scripts/import_community_routes.py --no-db
#
#   Upload to MongoDB (uses MONGODB_URL from .env by default):
#     uv run scripts/import_community_routes.py
#
#   Override MongoDB URL explicitly:
#     uv run scripts/import_community_routes.py --mongodb-url "mongodb+srv://user:pass@cluster.mongodb.net"
#
#   Optional: filter by minimum route length in metres (default: 1000):
#     uv run scripts/import_community_routes.py --min-distance 500

import argparse
import json
import math
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET

from pymongo import MongoClient, UpdateOne

# Load app settings so we pick up MONGODB_URL from .env automatically
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from framework.config import settings

# Average cycling speed in km/h used for time estimates
AVG_SPEED_KMH = 15.0


def haversine_distance(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """Return great-circle distance in metres between two (lng, lat) points."""
    R = 6_371_000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def route_distance_m(coords: list[list[float]]) -> float:
    """Sum of haversine distances along a coordinate sequence. Returns metres."""
    total = 0.0
    for i in range(len(coords) - 1):
        total += haversine_distance(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
    return total

# Only extract these folders as "existing" routes (exclude Future Network, Closures, Points)
ROUTE_FOLDERS = {
    "Cycling Path Network",
    "Park Connector Network",
    "Mountain Bike Trails",
}

FOLDER_CYCLIST_TYPE = {
    "Cycling Path Network": "commuter",
    "Park Connector Network": "recreational",
    "Mountain Bike Trails": "fitness",
}

FITNESS_DISTANCE_M = 20_000

NS = "{http://www.opengis.net/kml/2.2}"

SCRIPTS_DIR = os.path.dirname(__file__)
KML_URL = "https://www.google.com/maps/d/kml?forcekml=1&mid=13PRb7OmKXskuiAm_a5bujIIDO3NK4Gn9"
KML_FILE = os.path.join(SCRIPTS_DIR, "community_routes.kml")
OUTPUT_FILE = os.path.join(SCRIPTS_DIR, "community_routes.json")


def parse_coordinates(coord_text: str) -> list[list[float]]:
    """Parse KML coordinates string into [[lng, lat], ...] (altitude dropped)."""
    coords = []
    for triplet in coord_text.strip().split():
        parts = triplet.split(",")
        coords.append([float(parts[0]), float(parts[1])])
    return coords


def extract_routes(kml_path: str) -> list[dict]:
    tree = ET.parse(kml_path)
    root = tree.getroot()
    doc = root.find(f"{NS}Document")

    routes = []
    for folder in doc.findall(f"{NS}Folder"):
        folder_name = folder.find(f"{NS}name").text
        if folder_name not in ROUTE_FOLDERS:
            continue

        for placemark in folder.findall(f".//{NS}Placemark"):
            name_el = placemark.find(f"{NS}name")
            name = name_el.text if name_el is not None else None

            linestring = placemark.find(f".//{NS}LineString")
            if linestring is None:
                continue

            coord_el = linestring.find(f"{NS}coordinates")
            if coord_el is None or not coord_el.text:
                continue

            coords = parse_coordinates(coord_el.text)
            distance_m = route_distance_m(coords)
            estimated_time_min = (distance_m / 1000) / AVG_SPEED_KMH * 60
            cyclist_type = (
                "fitness"
                if distance_m >= FITNESS_DISTANCE_M
                else FOLDER_CYCLIST_TYPE[folder_name]
            )
            routes.append({
                "source": "precomputed",
                "name": name,
                "type": folder_name,
                "cyclist_type": cyclist_type,
                "distance_m": round(distance_m, 1),
                "estimated_time_min": round(estimated_time_min, 1),
                "coordinates": coords,
                "review_count": 0,
                "rating": 0.0,
            })

    return routes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import community cycling routes from KML to JSON.")
    parser.add_argument(
        "--min-distance",
        type=float,
        default=1000.0,
        metavar="METRES",
        help="Only include routes at least this many metres long (default: 1000).",
    )
    parser.add_argument(
        "--mongodb-url",
        type=str,
        default=settings.MONGODB_URL,
        metavar="URL",
        help="MongoDB connection URL (default: value from MONGODB_URL in .env).",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip uploading to MongoDB (JSON output only).",
    )
    args = parser.parse_args()

    print(f"Downloading KML from {KML_URL} ...")
    urllib.request.urlretrieve(KML_URL, KML_FILE)
    print(f"Saved KML to {KML_FILE}")

    print(f"Parsing {KML_FILE} ...")
    routes = extract_routes(KML_FILE)
    print(f"Extracted {len(routes)} routes")

    if args.min_distance > 0:
        before = len(routes)
        routes = [r for r in routes if r["distance_m"] >= args.min_distance]
        print(f"Filtered to {len(routes)} routes >= {args.min_distance} m (removed {before - len(routes)})")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(routes, f, ensure_ascii=False, indent=2)
    print(f"Saved to {OUTPUT_FILE}")

    if not args.no_db:
        print(f"Uploading to MongoDB ({args.mongodb_url}) ...")
        client = MongoClient(args.mongodb_url)
        collection = client.cyclelink["precomputed-routes"]

        # Upsert by (name, type) so _id is stable across re-runs and serves as the public route ID.
        # route_id integer is intentionally not stored — use _id (ObjectId) instead.
        ops = [
            UpdateOne(
                {"name": route["name"], "type": route["type"]},
                {"$set": route},
                upsert=True,
            )
            for route in routes
        ]
        result = collection.bulk_write(ops)
        client.close()
        print(f"Upserted {result.upserted_count} new, modified {result.modified_count} existing documents")




