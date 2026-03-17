from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

import subprocess
import os
import tempfile

import xml.etree.ElementTree as ET
from typing import List

app = FastAPI()

class Point(BaseModel):
    lat: float
    lon: float

class RouteRequest(BaseModel):
    origin: Point
    destination: Point
    waypoints: Optional[List[Point]] = []
    preferences: Optional[dict] = None

class RouteResponse(BaseModel):
    # To visualize the output, you can use https://gpx.studio/app
    path: List[Point]
    distance: float
    duration: float

def validate_route_request(req: RouteRequest):
    if req.origin.lat == req.destination.lat and req.origin.lon == req.destination.lon:
        raise HTTPException(
            status_code=400,
            detail="Origin and destination cannot be the same"
        )

def parse_gpx_points(gpx_path: str) -> List[Point]:
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

def build_cli_command(req: RouteRequest, output_path: str) -> List[str]:
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

def run_cli_command(cmd: List[str], output_path: str) -> List[Point]:
    
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
            detail=f"result.stderr.strip()" or "bike_route CLI failed"
        )

    if not os.path.exists(output_path):
        raise HTTPException(
            status_code=500,
            detail="CLI succeeded but did not create the GPX output file"
        )
    
    return parse_gpx_points(output_path)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/routes/recommend", response_model=RouteResponse)
async def recommend_route(req: RouteRequest):

    validate_route_request(req)

    # create temp directory and file for the CLI output
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "route.gpx")
        print(output_path)

        cmd = build_cli_command(req, output_path)
        print(cmd)

        generated_path = run_cli_command(cmd, output_path)

        return RouteResponse(
            path=generated_path, 
            distance=0.0, # placeholders
            duration=0.0,
        )

'''
Example: Gardens By the Bay route

curl -X 'POST' \
  'http://127.0.0.1:8000/routes/recommend' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "origin": {
    "lat": 1.3009,
    "lon": 103.9122
  },
  "destination": {
    "lat": 1.3038,
    "lon": 103.9385
  },
  "waypoints": [],
  "preferences": {}
}'
'''

