#!/usr/bin/env python3
"""
Fetch Singapore OSM tree data and upload to S3 for use by the shade scoring system.

At runtime the tree data is loaded into memory as a KD-tree (via graph_manager),
mirroring how the road network graph is handled.

Usage:
    # Fetch and upload to S3:
    python scripts/import_trees.py --bucket cyclelink-dev-s3-bucket

    # Save locally only (for local dev):
    python scripts/import_trees.py --local-only

Set OSM_TREES_LOCAL_PATH in your .env to point the service at the local file.
"""

import argparse
import json
import logging
import time
import urllib.request

import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_FILENAME = "singapore_trees.json"
S3_KEY = "osm-graphs/singapore_trees.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Bounding box covers all of Singapore
OVERPASS_QUERY = """
[out:json][timeout:60];
(
  node["natural"="tree"](1.1,103.6,1.5,104.0);
  node["natural"="wood"](1.1,103.6,1.5,104.0);
);
out body;
"""


def fetch_trees() -> list[list[float]]:
    """Fetch tree nodes from Overpass API. Returns list of [lat, lng] pairs."""
    logger.info("Fetching OSM tree data from Overpass API …")
    data = OVERPASS_QUERY.encode("utf-8")
    req = urllib.request.Request(OVERPASS_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=90) as resp:
        result = json.loads(resp.read())

    coords = [
        [el["lat"], el["lon"]]
        for el in result.get("elements", [])
        if el.get("type") == "node" and "lat" in el and "lon" in el
    ]
    logger.info(f"  → {len(coords):,} tree nodes fetched")
    return coords


def save_local(coords: list[list[float]], output_path: str):
    with open(output_path, "w") as f:
        json.dump(coords, f)
    logger.info(f"Saved {len(coords):,} trees to {output_path}")


def upload_to_s3(file_path: str, bucket: str):
    logger.info(f"Uploading to s3://{bucket}/{S3_KEY} …")
    s3 = boto3.client("s3")
    s3.upload_file(file_path, bucket, S3_KEY)
    logger.info("Upload complete.")


def main():
    parser = argparse.ArgumentParser(description="Fetch Singapore OSM trees and upload to S3")
    parser.add_argument("--bucket", type=str, help="S3 bucket name")
    parser.add_argument("--output", type=str, default=DEFAULT_FILENAME, help="Local output path")
    parser.add_argument("--local-only", action="store_true", help="Save locally without uploading")
    args = parser.parse_args()

    if not args.local_only and not args.bucket:
        parser.error("--bucket is required unless --local-only is set")

    start = time.time()
    coords = fetch_trees()
    save_local(coords, args.output)

    if not args.local_only:
        upload_to_s3(args.output, args.bucket)
        logger.info(f"\n✅  Tree data uploaded to s3://{args.bucket}/{S3_KEY}")
        logger.info("Set this env var in your ECS task definition / .env:")
        logger.info(f"  OSM_TREES_S3_KEY={S3_KEY}")
    else:
        import os
        abs_path = os.path.abspath(args.output)
        logger.info(f"\n✅  Tree data saved locally to {abs_path}")
        logger.info("Set this env var for local development:")
        logger.info(f"  OSM_TREES_LOCAL_PATH={abs_path}")

    logger.info(f"Done in {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
