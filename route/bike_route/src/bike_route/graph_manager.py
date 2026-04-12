"""
Manages the pre-downloaded Singapore OSM graph.

On container startup, the graph is downloaded from S3 (or loaded from a local
file) and kept in memory.  At request time, a bounding-box subgraph is
extracted from the in-memory graph instead of calling the Overpass API.

This eliminates the ~2-10 second per-request download that was the main
performance bottleneck.
"""

import json
import logging
import os
import tempfile

import networkx as nx
import numpy as np
import osmnx as ox
from scipy.spatial import KDTree

logger = logging.getLogger(__name__)

# The in-memory graph (set once on startup, read-only afterwards)
_graph: nx.MultiDiGraph | None = None

# OSM tree index (set once on startup, read-only afterwards)
_tree_kdtree: KDTree | None = None
_tree_coords: np.ndarray | None = None  # shape (N, 2): [[lat, lng], ...]

# Node spatial index for fast bounding-box queries (set once on startup)
_node_ids_arr: np.ndarray | None = None  # shape (N,) — graph node IDs
_node_lats: np.ndarray | None = None     # shape (N,), float64 — node latitudes  (d["y"])
_node_lngs: np.ndarray | None = None     # shape (N,), float64 — node longitudes (d["x"])

# Edge spatial index — avoids rebuilding a GeoDataFrame per request (set once on startup)
# Stores edge midpoints so nearest_edge() is a single KDTree query instead of
# graph_to_gdfs() + STRtree rebuild on every call.
_edge_kdtree: KDTree | None = None
_edge_records: list | None = None  # parallel list of (u, v, key) tuples

S3_KEY_DEFAULT = "osm-graphs/singapore_bike_graph.graphml"
TREES_S3_KEY_DEFAULT = "osm-graphs/singapore_trees.json"

# At Singapore's latitude (~1.3°N), 1 degree ≈ 111,320 m for both lat and lng
_METRES_PER_DEGREE = 111_320


# ── Loading ────────────────────────────────────────────────────────────

def _build_node_index():
    """Build numpy arrays of node coordinates for fast bounding-box filtering."""
    global _node_ids_arr, _node_lats, _node_lngs
    node_data = [(n, d["y"], d["x"]) for n, d in _graph.nodes(data=True)]
    _node_ids_arr = np.array([nd[0] for nd in node_data])
    _node_lats    = np.array([nd[1] for nd in node_data], dtype=np.float64)
    _node_lngs    = np.array([nd[2] for nd in node_data], dtype=np.float64)
    logger.info(f"Node spatial index built: {len(_node_ids_arr):,} nodes")


def _build_edge_index():
    """Build a KDTree over midpoints of *allowed* edges in the *main* component.

    Only indexing the main weakly-connected component of the allowed subgraph
    guarantees that nearest_edge_in_subgraph() never returns an edge that sits in
    a small disconnected island — which was causing 'no path' regressions when
    bike-graph path edges snapped into isolated fragments of large subgraphs.
    """
    global _edge_kdtree, _edge_records
    from bike_route.utils import is_allowed_road  # avoid circular import at module level

    node_coords = {n: (d["y"], d["x"]) for n, d in _graph.nodes(data=True)}

    # Build set of allowed edges and their induced node set
    allowed_edge_keys = [
        (u, v, k)
        for u, v, k, d in _graph.edges(keys=True, data=True)
        if is_allowed_road(d)
    ]
    allowed_nodes = {n for u, v, _ in allowed_edge_keys for n in (u, v)}
    allowed_subgraph = _graph.subgraph(allowed_nodes)

    # Find the main weakly-connected component
    main_comp = max(nx.weakly_connected_components(allowed_subgraph), key=len)
    logger.info(
        f"Allowed edge index: {len(allowed_edge_keys):,} allowed edges, "
        f"main component has {len(main_comp):,} nodes"
    )

    records = []
    midpoints = []
    for u, v, k in allowed_edge_keys:
        if u not in main_comp or v not in main_comp:
            continue
        u_lat, u_lng = node_coords[u]
        v_lat, v_lng = node_coords[v]
        midpoints.append(((u_lat + v_lat) / 2, (u_lng + v_lng) / 2))
        records.append((u, v, k))

    _edge_kdtree = KDTree(np.array(midpoints, dtype=np.float64))
    _edge_records = records
    logger.info(f"Edge spatial index built: {len(records):,} edges in main component")


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
    _build_node_index()
    _build_edge_index()


def load_graph_from_file(path: str):
    """Load the graph from a local .graphml file (for local development)."""
    global _graph

    logger.info(f"Loading graph from {path} …")
    _graph = ox.load_graphml(path)
    logger.info(
        f"Graph loaded: {len(_graph.nodes):,} nodes, {len(_graph.edges):,} edges"
    )
    _build_node_index()
    _build_edge_index()


# ── Tree index ─────────────────────────────────────────────────────────

def _build_tree_index(coords: list[list[float]]):
    """Build the in-memory KD-tree from a list of [lat, lng] pairs."""
    global _tree_coords, _tree_kdtree
    _tree_coords = np.array(coords, dtype=np.float64)
    _tree_kdtree = KDTree(_tree_coords)
    logger.info(f"Tree index built: {len(_tree_coords):,} trees loaded")


def load_trees_from_s3(bucket: str, key: str | None = None):
    """Download the tree JSON from S3 and build the in-memory KD-tree."""
    import boto3

    s3_key = key or TREES_S3_KEY_DEFAULT
    logger.info(f"Downloading tree data from s3://{bucket}/{s3_key} …")

    s3 = boto3.client("s3")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        s3.download_file(bucket, s3_key, tmp.name)
        tmp_path = tmp.name

    with open(tmp_path) as f:
        coords = json.load(f)
    os.unlink(tmp_path)
    _build_tree_index(coords)


def load_trees_from_file(path: str):
    """Load tree data from a local JSON file (for local development)."""
    logger.info(f"Loading tree data from {path} …")
    with open(path) as f:
        coords = json.load(f)
    _build_tree_index(coords)


def count_trees_near_path(path: list[tuple[float, float]], radius_m: float = 15.0) -> int:
    """
    Count unique OSM trees within radius_m of any point on the path.

    Uses the in-memory KD-tree built at startup. Returns 0 if no tree data
    is loaded or the path is too short to query.
    """
    if _tree_kdtree is None or len(path) < 2:
        return 0

    radius_deg = radius_m / _METRES_PER_DEGREE
    path_array = np.array(path, dtype=np.float64)  # [[lat, lng], ...]

    # query_ball_point returns per-point lists of matching tree indices;
    # union them to count each tree only once
    matches_per_point = _tree_kdtree.query_ball_point(path_array, r=radius_deg)
    unique_trees = set().union(*matches_per_point)
    return len(unique_trees)


def trees_loaded() -> bool:
    """Check whether the tree index has been loaded into memory."""
    return _tree_kdtree is not None


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

    if _node_ids_arr is not None:
        mask = (south <= _node_lats) & (_node_lats <= north) & (west <= _node_lngs) & (_node_lngs <= east)
        nodes_in_bbox = _node_ids_arr[mask].tolist()
    else:
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


def get_elevations_for_path(path: list[tuple[float, float]]) -> list[float]:
    """
    Return elevation (metres) for each (lat, lng) point in the path by finding
    the nearest graph node. Returns 0.0 for any point where elevation is unavailable.
    """
    if _graph is None:
        return [0.0] * len(path)

    lats = [p[0] for p in path]
    lngs = [p[1] for p in path]
    node_ids = ox.distance.nearest_nodes(_graph, lngs, lats)

    elevations = []
    for node_id in node_ids:
        ele = _graph.nodes[node_id].get("elevation", 0.0)
        elevations.append(float(ele) if ele is not None else 0.0)
    return elevations


def nearest_edge(lat: float, lng: float) -> tuple | None:
    """Return the (u, v, key) of the nearest edge in the full graph to (lat, lng).

    Uses the pre-built midpoint KDTree — O(log N) per query, no GeoDataFrame
    allocation.  Returns None if the edge index has not been built.
    """
    if _edge_kdtree is None:
        return None
    _, idx = _edge_kdtree.query([lat, lng])
    return _edge_records[idx]


def is_loaded() -> bool:
    """Check whether the graph has been loaded into memory."""
    return _graph is not None
