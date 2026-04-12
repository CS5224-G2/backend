#!/usr/bin/env python3
"""
One-time script to pre-download the Singapore OSM road network graph
and upload it to S3 for use by the bike route service.

The graph is downloaded from OpenStreetMap via the Overpass API (OSMnx),
saved as a .graphml file, and optionally uploaded to an S3 bucket.

At runtime the bike-route container will download the graph from S3 once
on startup and serve requests from the in-memory graph — eliminating the
per-request Overpass API call that was the main performance bottleneck.

Usage:
    # Download and upload to S3:
    python scripts/predownload_sg_graph.py --bucket cyclelink-dev-s3-bucket

    # Save locally only (for testing):
    python scripts/predownload_sg_graph.py --local-only

    # Custom output path:
    python scripts/predownload_sg_graph.py --bucket my-bucket --output /tmp/sg.graphml
"""

import argparse
import logging
import os

import networkx as nx
import osmnx as ox
import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_FILENAME = "singapore_bike_graph.graphml"
S3_KEY_PREFIX = "osm-graphs"


def download_singapore_graph(output_path: str, include_elevation: bool = False) -> str:
    """Download the Singapore road + cycling network and save as .graphml.

    Composes the drive graph (roads cyclists share with cars) and the bike graph
    (dedicated cycleways, Park Connector Network paths, etc.) so that both the
    road backbone and cycling-specific infrastructure are present.
    """
    logger.info("Downloading Singapore OSM graph via Overpass API …")
    logger.info("(This may take a few minutes on the first run.)")

    logger.info("Fetching drive network …")
    G_drive = ox.graph_from_place("Singapore", network_type="drive", simplify=True)
    logger.info(f"  drive: {len(G_drive.nodes):,} nodes, {len(G_drive.edges):,} edges")

    logger.info("Fetching bike network …")
    G_bike = ox.graph_from_place("Singapore", network_type="bike", simplify=True)
    logger.info(f"  bike:  {len(G_bike.nodes):,} nodes, {len(G_bike.edges):,} edges")

    # Only graft cycling-specific edges from the bike graph onto the drive graph.
    # We want the infrastructure that is missing from the drive graph: dedicated cycleways, paths (PCN), and tracks.
    _CYCLING_ONLY = {"cycleway", "path", "track"}

    logger.info("Grafting cycling-specific edges from bike network onto drive graph …")
    G = G_drive.copy()
    added_edges = 0
    for u, v, k, data in G_bike.edges(keys=True, data=True):
        hw = data.get("highway", "")
        if isinstance(hw, list):
            hw = hw[0]
        if hw not in _CYCLING_ONLY:
            continue
        # Copy endpoint nodes if not already present
        for node in (u, v):
            if node not in G:
                G.add_node(node, **G_bike.nodes[node])
        G.add_edge(u, v, key=k, **data)
        added_edges += 1
    logger.info(f"  grafted {added_edges:,} cycling-only edges")
    logger.info(f"  combined: {len(G.nodes):,} nodes, {len(G.edges):,} edges")

    # Remove completely isolated nodes (no edges)
    isolated = list(nx.isolates(G))
    G.remove_nodes_from(isolated)
    logger.info(
        f"Removed {len(isolated):,} isolated nodes. "
        f"Final: {len(G.nodes):,} nodes, {len(G.edges):,} edges"
    )

    if include_elevation:
        logger.info("Fetching elevation data for all nodes via opentopodata (this may take a while) …")
        ox.settings.elevation_url_template = "https://api.opentopodata.org/v1/srtm90m?locations={locations}"
        G = ox.elevation.add_node_elevations_google(G, api_key=None, batch_size=100, pause=1.0)
        logger.info("Elevation data added to all nodes.")

    ox.save_graphml(G, output_path)
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    logger.info(f"Saved graph to {output_path} ({size_mb:.1f} MB)")

    return output_path


def upload_to_s3(file_path: str, bucket: str, key: str):
    """Upload the graph file to S3."""
    logger.info(f"Uploading to s3://{bucket}/{key} …")
    s3 = boto3.client("s3")
    s3.upload_file(file_path, bucket, key)
    logger.info("Upload complete!")


def main():
    parser = argparse.ArgumentParser(
        description="Pre-download Singapore OSM graph and upload to S3",
    )
    parser.add_argument("--bucket", type=str, help="S3 bucket name to upload to")
    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_FILENAME,
        help="Local output file path (default: %(default)s)",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Save locally without uploading to S3",
    )
    parser.add_argument(
        "--no-elevation",
        action="store_true",
        help="Skip fetching elevation data for all nodes",
    )
    args = parser.parse_args()

    if not args.local_only and not args.bucket:
        parser.error("--bucket is required unless --local-only is set")

    output_path = download_singapore_graph(args.output, include_elevation=not args.no_elevation)

    s3_key = f"{S3_KEY_PREFIX}/{DEFAULT_FILENAME}"

    if not args.local_only:
        upload_to_s3(output_path, args.bucket, s3_key)
        logger.info(f"\n✅  Graph uploaded to s3://{args.bucket}/{s3_key}")
        logger.info("Set these env vars in your ECS task definition / .env:")
        logger.info(f"  S3_BUCKET_NAME={args.bucket}")
        logger.info(f"  OSM_GRAPH_S3_KEY={s3_key}")
    else:
        abs_path = os.path.abspath(output_path)
        logger.info(f"\n✅  Graph saved locally to {abs_path}")
        logger.info("Set this env var for local development:")
        logger.info(f"  OSM_GRAPH_LOCAL_PATH={abs_path}")


if __name__ == "__main__":
    main()
