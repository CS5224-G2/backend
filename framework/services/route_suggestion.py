import asyncio
import boto3
import functools
import httpx
import logging
import math
import os
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import POICategory, POIWaypoint, Point, RoutePreferences, RouteRequest, RouteResponse
from ..config import settings
from . import hawker as hawker_service
from . import historic_sites as historic_sites_service
from . import parks as park_service
from . import tourist_attractions as tourist_attractions_service

logger = logging.getLogger(__name__)

_METRES_PER_DEGREE_LAT = 111_320
_AVG_CYCLING_SPEED_KMH = 15.0
_POI_RADIUS_MIN_M = 500.0    # always search at least 500 m per segment
_POI_RADIUS_MAX_M = 3_000.0  # cap to avoid large detours

# Set SAVE_GPX=true to persist generated GPX files to the saved_gpx/ folder.
# Each request writes a unique file (route_<uuid>.gpx).
_GPX_DIR = "saved_gpx"


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


def _downsample_path_for_shade(path: list[Point], min_spacing_m: float) -> list[Point]:
    """Keep start/end and points spaced at least min_spacing_m apart (cheap equirectangular spacing)."""
    if len(path) < 2 or min_spacing_m <= 0:
        return path
    out: list[Point] = [path[0]]
    accumulated = 0.0
    for i in range(1, len(path)):
        accumulated += _straight_line_distance_m(path[i - 1], path[i])
        if accumulated >= min_spacing_m:
            out.append(path[i])
            accumulated = 0.0
    if out[-1] != path[-1]:
        out.append(path[-1])
    if len(out) < 2:
        return [path[0], path[-1]]
    return out


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
    segment_radius = max(_POI_RADIUS_MIN_M, min(total_dist / (2 * (n + 1)), _POI_RADIUS_MAX_M))

    poi_waypoints = []
    for i, category in enumerate(categories, start=1):
        t = i / (n + 1)
        segment_point = _interpolate_point(req.origin, req.destination, t)
        poi = await _find_nearest_poi(db, category, segment_point.lat, segment_point.lng, segment_radius)
        if poi:
            logger.info("POI selected: %s (%s) at (%.6f, %.6f)", poi.name, category.value, poi.point.lat, poi.point.lng)
            poi_waypoints.append(poi)
        else:
            logger.info("No POI found for category %s within %.0fm of (%.6f, %.6f)", category.value, segment_radius, segment_point.lat, segment_point.lng)

    return poi_waypoints


async def _compute_route_in_process(
    req: RouteRequest, output_path: str, extra_waypoints: list[Point]
) -> list[Point]:
    """
    Call compute_route directly in-process instead of spawning a subprocess.
    This reuses the graph already loaded in memory — no re-download needed.
    Used by the route service (bike-route container) which owns the graph data.
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
        import networkx as nx

        if isinstance(e, nx.NetworkXNoPath):
            raise HTTPException(
                status_code=422,
                detail=f"No road path for the selected route: {e!s}",
            ) from e
        if isinstance(e, TypeError) and "geometry" in str(e).lower():
            raise HTTPException(
                status_code=422,
                detail=f"Routing geometry error: {e!s}",
            ) from e
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

    sample_spacing = settings.SHADE_PATH_SAMPLE_SPACING_M
    sampled = _downsample_path_for_shade(path, sample_spacing)
    total_dist_m = _compute_path_distance_m(path)
    path_tuples = [(p.lat, p.lng) for p in sampled]
    count = graph_manager.count_trees_near_path(path_tuples, radius_m=15.0)

    # 2 trees per 100m → score 1.0
    trees_per_100m = (count / total_dist_m) * 100 if total_dist_m > 0 else 0.0
    score = min(1.0, trees_per_100m / 2.0)
    logger.info("Shade score: %.3f (%d trees, %.0f m route, %.2f trees/100m)", score, count, total_dist_m, trees_per_100m)
    return score


async def _recommend_via_service(
    req: RouteRequest, poi_waypoints: list, extra_points: list[Point]
) -> RouteResponse:
    """
    Delegate route computation to the bike-route service via HTTP.
    Used by the framework (main backend) service to avoid loading graph data in-process.
    POI waypoints are already resolved from the DB; they are passed as plain waypoints
    so the route service treats them as routing stops (no second DB lookup needed).
    """
    from ..clients.http import service_client

    # Build a request with all POI prefs disabled — POIs are already resolved as waypoints
    _no_poi_prefs = RoutePreferences(
        include_hawker_centres=False,
        include_parks=False,
        include_historic_sites=False,
        include_tourist_attractions=False,
    )
    delegated_req = RouteRequest(
        origin=req.origin,
        destination=req.destination,
        waypoints=req.waypoints + extra_points,
        preferences=_no_poi_prefs,
    )

    _route_http_timeout = httpx.Timeout(
        connect=5.0,
        read=settings.ROUTE_SERVICE_HTTP_READ_TIMEOUT,
        write=10.0,
        pool=5.0,
    )
    try:
        resp = await service_client.post(
            "bike-route",
            "/v1/route-suggestion/recommend",
            json=delegated_req.model_dump(),
            timeout=_route_http_timeout,
        )
        resp.raise_for_status()
    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=504,
            detail=f"Route service timed out: {repr(e)}",
        ) from e
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Route service returned {e.response.status_code}: {e.response.text[:200]}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Route service call failed: {type(e).__name__}: {repr(e)}",
        ) from e

    data = resp.json()
    path = [Point(**p) for p in data["path"]]
    return RouteResponse(
        path=path,
        poi_waypoints=poi_waypoints,
        distance=data["distance"],
        duration=data["duration"],
        total_ascent_m=data.get("total_ascent_m", 0.0),
        shade_score=data.get("shade_score", 0.0),
        computation_time_ms=data.get("computation_time_ms"),
    )


def _emit_route_computation_time(elapsed_ms: float) -> None:
    """Emit RouteComputationTime custom metric to CloudWatch (best-effort, non-blocking)."""
    try:
        cw = boto3.client("cloudwatch", region_name=settings.AWS_REGION)
        cw.put_metric_data(
            Namespace="CycleLink/RouteService",
            MetricData=[{
                "MetricName": "RouteComputationTime",
                "Value": elapsed_ms,
                "Unit": "Milliseconds",
            }],
        )
    except Exception as e:
        logger.warning("Failed to emit RouteComputationTime metric: %s", e)


async def _recommend_in_process(
    req: RouteRequest, poi_waypoints: list, extra_points: list[Point]
) -> RouteResponse:
    """
    Compute route in-process using the graph already loaded in memory.
    Used by the bike-route service which owns the graph and tree data.
    """
    t_start = time.monotonic()

    if settings.SAVE_GPX:
        os.makedirs(_GPX_DIR, exist_ok=True)
        output_path = os.path.join(_GPX_DIR, f"route_{uuid.uuid4().hex}.gpx")
        path = await _compute_route_in_process(req, output_path, extra_points)
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "route.gpx")
            path = await _compute_route_in_process(req, output_path, extra_points)

    elapsed_ms = (time.monotonic() - t_start) * 1000
    logger.info("Route computation completed in %.0f ms", elapsed_ms)
    asyncio.get_event_loop().run_in_executor(None, _emit_route_computation_time, elapsed_ms)

    if not path:
        raise HTTPException(status_code=500, detail="Route computation produced an empty path")

    distance_m = _compute_path_distance_m(path)
    duration_min = (distance_m / 1000) / _AVG_CYCLING_SPEED_KMH * 60

    from bike_route import graph_manager
    elevations = graph_manager.get_elevations_for_path([(p.lat, p.lng) for p in path])
    total_ascent_m = sum(
        max(0.0, elevations[i + 1] - elevations[i])
        for i in range(len(elevations) - 1)
    )

    shade_score = compute_shade_score(path)

    return RouteResponse(
        path=path,
        poi_waypoints=poi_waypoints,
        distance=round(distance_m / 1000, 2),
        duration=round(duration_min),
        total_ascent_m=round(total_ascent_m, 1),
        shade_score=shade_score,
        computation_time_ms=round(elapsed_ms, 1),
    )


async def recommend_route(db: AsyncSession, req: RouteRequest) -> RouteResponse:
    poi_waypoints = await _get_poi_waypoints(db, req)

    async def _attempt(pois: list) -> RouteResponse:
        extra_points = [p.point for p in pois]
        if "bike-route" in settings.SERVICE_URLS and not settings.BIKE_ROUTE_API_STANDALONE:
            return await _recommend_via_service(req, pois, extra_points)
        return await _recommend_in_process(req, pois, extra_points)

    try:
        return await _attempt(poi_waypoints)
    except HTTPException as exc:
        if exc.status_code not in (422, 500):
            raise
        had_stops = bool(poi_waypoints or req.waypoints)
        if not had_stops:
            raise
        logger.warning(
            "Route with intermediate stops failed (HTTP %s); retrying origin→destination only",
            exc.status_code,
        )
        plain = RouteRequest(
            origin=req.origin,
            destination=req.destination,
            waypoints=[],
            preferences=RoutePreferences(
                include_hawker_centres=False,
                include_parks=False,
                include_historic_sites=False,
                include_tourist_attractions=False,
            ),
        )
        if "bike-route" in settings.SERVICE_URLS and not settings.BIKE_ROUTE_API_STANDALONE:
            return await _recommend_via_service(plain, [], [])
        return await _recommend_in_process(plain, [], [])

