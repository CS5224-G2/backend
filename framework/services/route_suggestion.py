from fastapi import HTTPException
from ..schemas import Point, RouteRequest, RouteResponse

import xml.etree.ElementTree as ET
import tempfile
import subprocess
import os

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

def _build_cli_command(req: RouteRequest, output_path: str) -> list[str]:
    cmd = [
        "bike_route",
        "--start-lat", str(req.origin.lat),
        "--start-lon", str(req.origin.lon),
        "--end-lat", str(req.destination.lat),
        "--end-lon", str(req.destination.lon),
        "--output", output_path,
    ]

    if req.waypoints:
        cmd.append("--waypoints")
        for wp in req.waypoints:
            cmd.extend([str(wp.lat), str(wp.lon)])

    return cmd

def _run_cli_command(cmd: list[str], output_path: str) -> list[Point]:
    
    # better to use async but somehow does not work so just run synchronously for now
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
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
            detail=result.stderr.strip() or "bike_route CLI failed"
        )

    if not os.path.exists(output_path):
        raise HTTPException(
            status_code=500,
            detail="CLI succeeded but did not create the GPX output file"
        )
    
    return _parse_gpx_points(output_path)

def recommend_route(req: RouteRequest) -> RouteResponse:
    _validate_route_request(req)

    # create temp directory and file for the CLI output
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "route.gpx")

        cmd = _build_cli_command(req, output_path)

        generated_path = _run_cli_command(cmd, output_path)

        return RouteResponse(
            path=generated_path, 
            distance=0.0, # placeholders
            duration=0.0,
        )
