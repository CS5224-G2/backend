"""
Manages the pre-downloaded Singapore OSM graph.

On container startup, the graph is downloaded from S3 (or loaded from a local
file) and kept in memory.  At request time, a bounding-box subgraph is
extracted from the in-memory graph instead of calling the Overpass API.

This eliminates the ~2-10 second per-request download that was the main
performance bottleneck.
"""

import logging
import os
import tempfile

import networkx as nx
import osmnx as ox

logger = logging.getLogger(__name__)

# The in-memory graph (set once on startup, read-only afterwards)
_graph: nx.MultiDiGraph | None = None

S3_KEY_DEFAULT = "osm-graphs/singapore_bike_graph.graphml"


# ── Loading ────────────────────────────────────────────────────────────

def load_graph_from_s3(bucket: str, key: str | None = None):
    """Download the graph from S3 and load it into memory."""
    global _graph

    # Lazy import — boto3 is only needed when using S3
    import boto3

    s3_key = key or S3_KEY_DEFAULT
    logger.info(f"Downloading OSM graph from s3://{bucket}/{s3_key} …")

    s3 = boto3.client("s3")
    with tempfile.NamedTemporaryFile(suffix=".graphml", delete=False) as tmp:
        s3.download_file(bucket, s3_key, tmp.name)
        tmp_path = tmp.name

    logger.info("Loading graph into memory …")
    _graph = ox.load_graphml(tmp_path)
    os.unlink(tmp_path)

    logger.info(
        f"Graph loaded: {len(_graph.nodes):,} nodes, {len(_graph.edges):,} edges"
    )


def load_graph_from_file(path: str):
    """Load the graph from a local .graphml file (for local development)."""
    global _graph

    logger.info(f"Loading graph from {path} …")
    _graph = ox.load_graphml(path)
    logger.info(
        f"Graph loaded: {len(_graph.nodes):,} nodes, {len(_graph.edges):,} edges"
    )


# ── Query ──────────────────────────────────────────────────────────────

def get_subgraph(
    north: float, south: float, east: float, west: float
) -> nx.MultiDiGraph:
    """
    Extract a subgraph for the given bounding box from the pre-loaded graph.

    Returns a **copy** so callers can safely mutate it (filter edges, add
    virtual waypoint nodes, etc.) without affecting the master graph.
    """
    if _graph is None:
        raise RuntimeError(
            "OSM graph not loaded. "
            "Call load_graph_from_s3() or load_graph_from_file() first."
        )

    nodes_in_bbox = [
        n
        for n, d in _graph.nodes(data=True)
        if south <= d["y"] <= north and west <= d["x"] <= east
    ]

    if not nodes_in_bbox:
        raise ValueError(
            f"No OSM nodes found in bounding box "
            f"(N={north}, S={south}, E={east}, W={west}). "
            f"Is the area within Singapore?"
        )

    subgraph = _graph.subgraph(nodes_in_bbox).copy()
    logger.info(
        f"  Subgraph extracted: {len(subgraph.nodes):,} nodes, "
        f"{len(subgraph.edges):,} edges"
    )
    return subgraph


def is_loaded() -> bool:
    """Check whether the graph has been loaded into memory."""
    return _graph is not None
