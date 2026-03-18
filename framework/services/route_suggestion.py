import math
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import POICategory, POIWaypoint, Point, RouteRequest, RouteResponse
from . import hawker as hawker_service
from . import historic_sites as historic_sites_service
from . import parks as park_service
from . import tourist_attractions as tourist_attractions_service

_METRES_PER_DEGREE_LAT = 111_320

# Set to a directory path to keep generated GPX files for debugging, e.g. "debug_gpx"
_DEBUG_GPX_DIR: str | None = None
_DEBUG_GPX_DIR = "debug_gpx"

def _validate_route_request(req: RouteRequest):
    if req.origin.lat == req.destination.lat and req.origin.lon == req.destination.lon:
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
        lon = float(trkpt.attrib["lon"])
        points.append(Point(lat=lat, lon=lon))

    return points

def _straight_line_distance_m(a: Point, b: Point) -> float:
    """
    Approximate straight-line distance in metres between two lat/lon points.

    This is somewhat inaccurate as compared to Haversine but should be OK for short 
    distances within Singapore, and is much faster to compute. See
    https://en.wikipedia.org/wiki/Equirectangular_projection
    """
    d_lat = (b.lat - a.lat) * _METRES_PER_DEGREE_LAT
    d_lon = (b.lon - a.lon) * _METRES_PER_DEGREE_LAT * math.cos(math.radians((a.lat + b.lat) / 2))
    return math.sqrt(d_lat ** 2 + d_lon ** 2)


def _interpolate_point(origin: Point, destination: Point, t: float) -> Point:
    """
    Return the point at fraction t (0–1) along the straight line from origin to destination.
    
    So this is a point lying along the straight-line route between origin and dest.
    """
    return Point(
        lat=origin.lat + t * (destination.lat - origin.lat),
        lon=origin.lon + t * (destination.lon - origin.lon),
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
    db: AsyncSession, category: POICategory, lat: float, lon: float, radius_m: float
) -> POIWaypoint | None:
    if category == POICategory.HAWKER_CENTRE:
        rows = await hawker_service.list_nearby_hawker_centres(db, lat=lat, lng=lon, radius_m=radius_m, limit=1)
        if rows:
            obj = rows[0].HawkerCentre
            return POIWaypoint(name=obj.name, category=category, point=Point(lat=obj.latitude, lon=obj.longitude))
    elif category == POICategory.PARK:
        rows = await park_service.list_nearby_parks(db, lat=lat, lng=lon, radius_m=radius_m, limit=1)
        if rows:
            obj = rows[0].Park
            return POIWaypoint(name=obj.name, category=category, point=Point(lat=obj.latitude, lon=obj.longitude))
    elif category == POICategory.HISTORIC_SITE:
        rows = await historic_sites_service.list_nearby_historic_sites(db, lat=lat, lng=lon, radius_m=radius_m, limit=1)
        if rows:
            obj = rows[0].HistoricSite
            return POIWaypoint(name=obj.name, category=category, point=Point(lat=obj.latitude, lon=obj.longitude))
    elif category == POICategory.TOURIST_ATTRACTION:
        rows = await tourist_attractions_service.list_nearby_tourist_attractions(db, lat=lat, lng=lon, radius_m=radius_m, limit=1)
        if rows:
            obj = rows[0].TouristAttraction
            return POIWaypoint(name=obj.page_title, category=category, point=Point(lat=obj.latitude, lon=obj.longitude))
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
        poi = await _find_nearest_poi(db, category, segment_point.lat, segment_point.lon, segment_radius)
        if poi:
            poi_waypoints.append(poi)

    return poi_waypoints


def _build_cli_command(req: RouteRequest, output_path: str, extra_waypoints: list[Point] = []) -> list[str]:
    cmd = [
        "bike_route",
        "--start-lat", str(req.origin.lat),
        "--start-lon", str(req.origin.lon),
        "--end-lat", str(req.destination.lat),
        "--end-lon", str(req.destination.lon),
        "--output", output_path,
    ]

    all_waypoints = req.waypoints + extra_waypoints
    if all_waypoints:
        cmd.append("--waypoints")
        for wp in all_waypoints:
            cmd.extend([str(wp.lat), str(wp.lon)])

    return cmd

def _run_cli_command(cmd: list[str], output_path: str) -> list[Point]:
    # better to use async but somehow does not work so just run synchronously for now
    # stdout/stderr are inherited (not captured) so bike_route output streams to the server terminal
    try:
        result = subprocess.run(
            cmd,
            check=False
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start route generation: {type(e).__name__}: {repr(e)}"
        )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail="bike_route CLI failed"
        )

    if not os.path.exists(output_path):
        raise HTTPException(
            status_code=500,
            detail="CLI succeeded but did not create the GPX output file"
        )
    
    return _parse_gpx_points(output_path)

async def recommend_route(db: AsyncSession, req: RouteRequest) -> RouteResponse:
    '''
    You can keep the generated GPX file for debugging / visualization by setting 
    _DEBUG_GPX_DIR to a directory path, e.g. "debug_gpx" (just uncomment the line on top of this file).
    If so, the GPX file will be saved in that directory with a fixed name "route.gpx" (overwritten on each request).

    Otherwise, it will just write it to a temporary folder which is destroyed immediately.
    
    To visualize a gpx, you can use https://gpx.studio/app.
    '''
    _validate_route_request(req)

    poi_waypoints = await _get_poi_waypoints(db, req)
    extra_points = [p.point for p in poi_waypoints]

    if _DEBUG_GPX_DIR:
        os.makedirs(_DEBUG_GPX_DIR, exist_ok=True)
        output_path = os.path.join(_DEBUG_GPX_DIR, "route.gpx")
        cmd = _build_cli_command(req, output_path, extra_points)
        path = _run_cli_command(cmd, output_path)
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "route.gpx")
            cmd = _build_cli_command(req, output_path, extra_points)
            path = _run_cli_command(cmd, output_path)

    return RouteResponse(
        path=path,
        poi_waypoints=poi_waypoints,
        distance=0.0,  # placeholder
        duration=0.0,  # placeholder
    )
