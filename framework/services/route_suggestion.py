import asyncio
import functools
import logging
import math
import os
import tempfile
import uuid
import xml.etree.ElementTree as ET

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import POICategory, POIWaypoint, Point, RouteRequest, RouteResponse
from ..config import settings
from . import hawker as hawker_service
from . import historic_sites as historic_sites_service
from . import parks as park_service
from . import tourist_attractions as tourist_attractions_service

logger = logging.getLogger(__name__)

_METRES_PER_DEGREE_LAT = 111_320
_AVG_CYCLING_SPEED_KMH = 15.0

# Set SAVE_GPX=true to persist generated GPX files to the saved_gpx/ folder.
# Each request writes a unique file (route_<uuid>.gpx).
_GPX_DIR = "saved_gpx"

def _validate_route_request(req: RouteRequest):
    if req.origin.lat == req.destination.lat and req.origin.lng == req.destination.lng:
        raise HTTPException(
            status_code=400,
            detail="Origin and destination cannot be the same"
        )

def _parse_gpx_points(gpx_path: str) -> list[Point]:
    tree = ET.parse(gpx_path)   
    root = tree.getroot()

    # GPX namespace
    ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

    points = []

    # Find all track points
    for trkpt in root.findall(".//gpx:trkpt", ns):
        lat = float(trkpt.attrib["lat"])
        lng = float(trkpt.attrib["lon"])
        points.append(Point(lat=lat, lng=lng))

    return points

def _straight_line_distance_m(a: Point, b: Point) -> float:
    """
    Approximate straight-line distance in metres between two lat/lng points.

    This is somewhat inaccurate as compared to Haversine but should be OK for short 
    distances within Singapore, and is much faster to compute. See
    https://en.wikipedia.org/wiki/Equirectangular_projection
    """
    d_lat = (b.lat - a.lat) * _METRES_PER_DEGREE_LAT
    d_lng = (b.lng - a.lng) * _METRES_PER_DEGREE_LAT * math.cos(math.radians((a.lat + b.lat) / 2))
    return math.sqrt(d_lat ** 2 + d_lng ** 2)


def _compute_path_distance_m(path: list[Point]) -> float:
    """Sum of segment distances along the route path in metres."""
    return sum(_straight_line_distance_m(path[i], path[i + 1]) for i in range(len(path) - 1))


def _interpolate_point(origin: Point, destination: Point, t: float) -> Point:
    """
    Return the point at fraction t (0–1) along the straight line from origin to destination.
    
    So this is a point lying along the straight-line route between origin and dest.
    """
    return Point(
        lat=origin.lat + t * (destination.lat - origin.lat),
        lng=origin.lng + t * (destination.lng - origin.lng),
    )


def _active_categories(req: RouteRequest) -> list[POICategory]: 
    # categories included based on user preferences in the request
    prefs = req.preferences
    categories = []
    if prefs.include_hawker_centres:
        categories.append(POICategory.HAWKER_CENTRE)
    if prefs.include_parks:
        categories.append(POICategory.PARK)
    if prefs.include_historic_sites:
        categories.append(POICategory.HISTORIC_SITE)
    if prefs.include_tourist_attractions:
        categories.append(POICategory.TOURIST_ATTRACTION)
    return categories


async def _find_nearest_poi(
    db: AsyncSession, category: POICategory, lat: float, lng: float, radius_m: float
) -> POIWaypoint | None:
    if category == POICategory.HAWKER_CENTRE:
        rows = await hawker_service.list_nearby_hawker_centres(db, lat=lat, lng=lng, radius_m=radius_m, limit=1)
        if rows:
            obj = rows[0].HawkerCentre
            return POIWaypoint(name=obj.name, category=category, point=Point(lat=obj.latitude, lng=obj.longitude))
    elif category == POICategory.PARK:
        rows = await park_service.list_nearby_parks(db, lat=lat, lng=lng, radius_m=radius_m, limit=1)
        if rows:
            obj = rows[0].Park
            return POIWaypoint(name=obj.name, category=category, point=Point(lat=obj.latitude, lng=obj.longitude))
    elif category == POICategory.HISTORIC_SITE:
        rows = await historic_sites_service.list_nearby_historic_sites(db, lat=lat, lng=lng, radius_m=radius_m, limit=1)
        if rows:
            obj = rows[0].HistoricSite
            return POIWaypoint(name=obj.name, category=category, point=Point(lat=obj.latitude, lng=obj.longitude))
    elif category == POICategory.TOURIST_ATTRACTION:
        rows = await tourist_attractions_service.list_nearby_tourist_attractions(db, lat=lat, lng=lng, radius_m=radius_m, limit=1)
        if rows:
            obj = rows[0].TouristAttraction
            return POIWaypoint(name=obj.page_title, category=category, point=Point(lat=obj.latitude, lng=obj.longitude))
    return None


async def _get_poi_waypoints(db: AsyncSession, req: RouteRequest) -> list[POIWaypoint]:
    """
    Split the straight line from origin to dest into segments. 
    For each segment, find the nearest POI of the active categories within a radius proportional to the total distance.
    """
    categories = _active_categories(req)
    n = len(categories)
    if n == 0:
        return []

    total_dist = _straight_line_distance_m(req.origin, req.destination)
    segment_radius = total_dist / (2 * (n + 1))

    poi_waypoints = []
    for i, category in enumerate(categories, start=1):
        t = i / (n + 1)
        segment_point = _interpolate_point(req.origin, req.destination, t)
        poi = await _find_nearest_poi(db, category, segment_point.lat, segment_point.lng, segment_radius)
        if poi:
            poi_waypoints.append(poi)

    return poi_waypoints


async def _compute_route_in_process(
    req: RouteRequest, output_path: str, extra_waypoints: list[Point]
) -> list[Point]:
    """
    Call compute_route directly in-process instead of spawning a subprocess.
    This reuses the graph already loaded in memory — no re-download needed.
    """
    from bike_route.main import compute_route
    from bike_route.utils import init_elevation_cache

    init_elevation_cache()

    start = (req.origin.lat, req.origin.lng)
    end = (req.destination.lat, req.destination.lng)
    waypoints = [(wp.lat, wp.lng) for wp in req.waypoints + extra_waypoints]

    loop = asyncio.get_event_loop()
    try:
        # Run the blocking computation in a thread so it doesn't block the event loop
        await loop.run_in_executor(
            None,
            functools.partial(compute_route, start, end, waypoints, output_path),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Route computation failed: {type(e).__name__}: {repr(e)}",
        ) from e

    if not os.path.exists(output_path):
        raise HTTPException(
            status_code=500,
            detail="compute_route did not create the GPX output file",
        )

    return _parse_gpx_points(output_path)

def compute_shade_score(path: list[Point]) -> float:
    """
    Compute a shade score [0, 1] for a route based on OSM tree density within 15m of the path.

    Queries the in-memory KD-tree built at startup from the pre-downloaded tree dataset.
    Score is normalised so that 2 trees per 100m of route equals 1.0 — a density
    consistent with well-shaded Singapore streets.

    Returns 0.0 if the tree index is not loaded or the path is too short.
    """
    if len(path) < 2:
        return 0.0

    from bike_route import graph_manager

    total_dist_m = _compute_path_distance_m(path)
    path_tuples = [(p.lat, p.lng) for p in path]
    count = graph_manager.count_trees_near_path(path_tuples, radius_m=15.0)

    # 2 trees per 100m → score 1.0
    trees_per_100m = (count / total_dist_m) * 100 if total_dist_m > 0 else 0.0
    score = min(1.0, trees_per_100m / 2.0)
    logger.info("Shade score: %.3f (%d trees, %.0f m route, %.2f trees/100m)", score, count, total_dist_m, trees_per_100m)
    return score


async def recommend_route(db: AsyncSession, req: RouteRequest) -> RouteResponse:
    '''
    Set SAVE_GPX=true to persist generated GPX files to the saved_gpx/ folder.
    Each request gets a unique filename (route_<uuid>.gpx) to avoid collisions.

    Otherwise, GPX files are written to a temporary folder and destroyed immediately.

    To visualize a gpx, you can use https://gpx.studio/app.
    '''
    _validate_route_request(req)

    poi_waypoints = await _get_poi_waypoints(db, req)
    extra_points = [p.point for p in poi_waypoints]

    if settings.SAVE_GPX:
        os.makedirs(_GPX_DIR, exist_ok=True)
        output_path = os.path.join(_GPX_DIR, f"route_{uuid.uuid4().hex}.gpx")
        path = await _compute_route_in_process(req, output_path, extra_points)
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "route.gpx")
            path = await _compute_route_in_process(req, output_path, extra_points)

    distance_m = _compute_path_distance_m(path)
    duration_min = (distance_m / 1000) / _AVG_CYCLING_SPEED_KMH * 60

    from bike_route import graph_manager
    elevations = graph_manager.get_elevations_for_path([(p.lat, p.lng) for p in path])
    total_ascent_m = sum(
        max(0.0, elevations[i + 1] - elevations[i])
        for i in range(len(elevations) - 1)
    )

    return RouteResponse(
        path=path,
        poi_waypoints=poi_waypoints,
        distance=round(distance_m / 1000, 2),
        duration=round(duration_min),
        total_ascent_m=round(total_ascent_m, 1),
    )

