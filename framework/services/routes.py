import hashlib
import json
import logging
import uuid
import math
from dataclasses import dataclass
from datetime import datetime, timezone

from ..clients.redis import redis_client

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import UserSavedRoute
from ..schemas import (
    AirQualityPreference,
    Checkpoint,
    CyclistType,
    ElevationPreference,
    LatLng,
    NamedLatLng,
    POIVisited,
    RecommendationResult,
    RecommendationsRequest,
    RouteDetail,
    RoutePreferences,
    RouteRequest,
    RouteSummary,
    SaveRouteRequest,
    SavedRouteItem,
    SavedRoutesResponse,
    ShadePreference,
    Point,
)
from ..config import settings
 
logger = logging.getLogger(__name__)

_PRECOMPUTED_COLLECTION = "precomputed-routes"
_GENERATED_COLLECTION = "generated-routes"

async def save_route(
    db: AsyncSession,
    mongo: AsyncDatabase,
    user_id: uuid.UUID,
    body: SaveRouteRequest,
) -> UserSavedRoute:
    """
    Saves a route reference for a user. Raises 409 if already saved or the 3-route cap is reached.
    The route data itself lives in MongoDB, this table stores the user → route_id link.
    """
    # Enforce 3-route cap
    count_result = await db.execute(
        select(UserSavedRoute).where(UserSavedRoute.user_id == user_id)
    )
    if len(count_result.scalars().all()) >= 3:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Saved routes limit reached",
        )

    record = UserSavedRoute(user_id=user_id, route_id=body.route_id)
    db.add(record)
    try:
        await db.commit()
        await db.refresh(record)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Route already saved",
        )

    await mongo["saved-routes"].insert_one({
        "_id": str(record.id),
        "user_id": str(user_id),
        "route_id": body.route_id,
        "name": body.name,
        "description": body.description,
        "distance": body.distance,
        "estimated_time": body.estimated_time,
        "elevation": body.elevation,
        "shade": body.shade,
        "air_quality": body.air_quality,
        "cyclist_type": body.cyclist_type,
        "checkpoints": [c.model_dump() for c in body.checkpoints],
        "points_of_interest_visited": [p.model_dump() for p in body.points_of_interest_visited],
        "route_path": [pt.model_dump() for pt in body.route_path],
        "saved_at": record.saved_at.isoformat(),
    })

    return record


async def get_saved_route_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Returns the number of routes saved by a user (used for favorite_trails_count)."""
    result = await db.execute(
        select(UserSavedRoute).where(UserSavedRoute.user_id == user_id)
    )
    return len(result.scalars().all())


async def delete_saved_route(
    db: AsyncSession,
    mongo: AsyncDatabase,
    user_id: uuid.UUID,
    saved_route_id: str,
) -> None:
    """Deletes a saved route belonging to the user. Raises 404 if not found or not owned by user."""
    try:
        record_id = uuid.UUID(saved_route_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved route not found")

    result = await db.execute(
        select(UserSavedRoute).where(
            UserSavedRoute.id == record_id,
            UserSavedRoute.user_id == user_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved route not found")

    await mongo["saved-routes"].delete_one({"_id": saved_route_id})
    await db.delete(record)
    await db.commit()


async def get_saved_routes(
    db: AsyncSession,
    mongo: AsyncDatabase,
    user_id: uuid.UUID,
) -> SavedRoutesResponse:
    """Returns all saved routes for a user (max 3), ordered by saved_at descending."""
    rows = (await db.execute(
        select(UserSavedRoute)
        .where(UserSavedRoute.user_id == user_id)
        .order_by(UserSavedRoute.saved_at.desc())
    )).scalars().all()

    if not rows:
        return SavedRoutesResponse(saved_routes=[], total=0)

    ids = [str(row.id) for row in rows]
    docs = {
        doc["_id"]: doc
        async for doc in mongo["saved-routes"].find({"_id": {"$in": ids}})
    }

    items = []
    for row in rows:
        doc = docs.get(str(row.id))
        if doc is None:
            continue
        items.append(SavedRouteItem(
            saved_route_id=str(row.id),
            route_id=doc["route_id"],
            name=doc["name"],
            description=doc.get("description"),
            saved_at=doc["saved_at"],
            distance=doc["distance"],
            estimated_time=doc["estimated_time"],
            elevation=doc["elevation"],
            shade=doc["shade"],
            air_quality=doc["air_quality"],
            cyclist_type=doc["cyclist_type"],
            checkpoints=[Checkpoint(**c) for c in doc.get("checkpoints", [])],
            points_of_interest_visited=[POIVisited(**p) for p in doc.get("points_of_interest_visited", [])],
            route_path=[LatLng(**pt) for pt in doc.get("route_path", [])],
        ))

    return SavedRoutesResponse(saved_routes=items, total=len(items))


def _doc_to_route_summary(doc: dict) -> RouteSummary:
    """Convert a precomputed-routes MongoDB document to a RouteSummary."""
    coords = doc.get("coordinates", [])
    first = coords[0] if coords else [0.0, 0.0]   # [lng, lat]
    last  = coords[-1] if coords else [0.0, 0.0]

    return RouteSummary(
        route_id=str(doc["_id"]),
        name=doc.get("name") or "",
        description=doc.get("type") or doc.get("description"),
        distance=round(doc.get("distance_m", 0) / 1000, 2),
        estimated_time=round(doc.get("estimated_time_min", 0)),
        elevation=doc.get("elevation", ElevationPreference.DONT_CARE),
        shade=doc.get("shade", ShadePreference.DONT_CARE),
        air_quality=doc.get("air_quality", AirQualityPreference.DONT_CARE),
        cyclist_type=doc.get("cyclist_type", CyclistType.GENERAL),
        review_count=doc.get("review_count", 0),
        rating=doc.get("rating", 0.0),
        checkpoints=[],
        points_of_interest_visited=[],
        start_point=NamedLatLng(lng=first[0], lat=first[1]),
        end_point=NamedLatLng(lng=last[0], lat=last[1]),
    )


async def get_routes(
    db: AsyncDatabase,
    cyclist_type: CyclistType | None = None,
    limit: int = 3,
) -> list[RouteSummary]:
    query: dict = {"source": "precomputed"}
    if cyclist_type is not None and cyclist_type != CyclistType.GENERAL:
        query["cyclist_type"] = cyclist_type.value

    cursor = db[_PRECOMPUTED_COLLECTION].find(query).limit(limit)
    return [_doc_to_route_summary(doc) async for doc in cursor]


async def get_popular_routes(
    db: AsyncDatabase,
    limit: int = 3,
) -> list[RouteSummary]:
    precomputed = [doc async for doc in db[_PRECOMPUTED_COLLECTION].find()]
    generated = [doc async for doc in db[_GENERATED_COLLECTION].find()]
    all_docs = sorted(
        precomputed + generated,
        key=lambda d: (d.get("review_count", 0), d.get("rating", 0.0)),
        reverse=True,
    )
    return [_doc_to_route_summary(doc) for doc in all_docs[:limit]]

# Each tuple defines which POI categories are active for that route variant.
# Varied across 3 calls so each recommendation has a different set of waypoints.
_POI_COMBOS = [
    {"include_hawker_centres": True,  "include_parks": True,  "include_historic_sites": False, "include_tourist_attractions": False},
    {"include_hawker_centres": False, "include_parks": False, "include_historic_sites": True,  "include_tourist_attractions": True},
    {"include_hawker_centres": True,  "include_parks": True,  "include_historic_sites": True,  "include_tourist_attractions": True},
]


# Scoring functions — each subcategory score is in the range [0, 1].
# Final route score is the sum of all subcategory scores.

_CYCLIST_TYPE_IDEAL_KM = {
    CyclistType.RECREATIONAL: 5.0,
    CyclistType.COMMUTER: 10.0,
    CyclistType.FITNESS: 20.0,
}
_CYCLIST_TYPE_SIGMA = 10.0


def _score_cyclist_type(distance_km: float, cyclist_type: CyclistType) -> float:
    """Score [0, 1] based on how close the route distance is to the ideal for the cyclist type."""
    ideal = _CYCLIST_TYPE_IDEAL_KM.get(cyclist_type)
    if ideal is None:
        return 0.0
    return math.exp(-((distance_km - ideal) ** 2) / (2 * _CYCLIST_TYPE_SIGMA ** 2))


def _nearest_station(lat: float, lng: float, stations: dict) -> dict | None:
    """Return the station dict closest to the given lat/lng."""
    best, best_dist = None, float("inf")
    for s in stations.values():
        d = (s["latitude"] - lat) ** 2 + (s["longitude"] - lng) ** 2
        if d < best_dist:
            best, best_dist = s, d
    return best


def _score_station_conditions(station: dict) -> float:
    """Score [0, 1] for a single weather station based on rainfall, humidity, and temperature."""
    rainfall = station.get("rainfall", {}).get("value", 0)
    humidity = station.get("relative_humidity", {}).get("value", 80)
    temperature = station.get("air_temperature", {}).get("value", 28)

    # Rainfall: any rain is bad
    rainfall_score = 0.0 if rainfall > 0 else 1.0

    # Humidity: <=70% is ideal, >=90% is bad, linear between
    humidity_score = max(0.0, min(1.0, (90 - humidity) / 20))

    # Temperature: <=27°C is ideal, >=33°C is bad, linear between
    temp_score = max(0.0, min(1.0, (33 - temperature) / 6))

    return (rainfall_score + humidity_score + temp_score) / 3


def _score_elevation(total_ascent_m: float, elevation_preference) -> float:
    """Score [0, 1] based on how well the route's total ascent matches the elevation preference.

    higher: linear 0→1 from 0–500m, capped at 1.0 beyond 500m.
    lower:  linear 1→0 from 0–250m, capped at 0.0 beyond 250m.
    dont-care: neutral (0).
    """
    if elevation_preference == ElevationPreference.HIGHER:
        return min(1.0, total_ascent_m / 500)
    if elevation_preference == ElevationPreference.LOWER:
        return max(0.0, 1.0 - total_ascent_m / 250)
    return 0.0


def _score_shade(shade_score: float, shade_preference) -> float:
    """Score [0, 1] based on how well the route's tree density matches the shade preference.

    reduce-shade: prefer routes with higher tree coverage (higher shade_score).
    dont-care: neutral (0).
    """
    if shade_preference == ShadePreference.REDUCE_SHADE:
        return shade_score
    return 0.0


def _score_air_quality(air_quality_preference, poi_waypoints: list, start_point, weather: dict | None) -> float:
    """Score [0, 1] based on air quality preference.

    Weather is sampled at POI waypoints since each route variant visits different POIs,
    making this the only signal that meaningfully differs between routes with the same
    start/end. If a route has no POI waypoints, falls back to the start point.

    Returns 0 if weather data is unavailable or air_quality_preference is dont-care.
    """
    if air_quality_preference == AirQualityPreference.DONT_CARE:
        return 0.0
    if not weather:
        return 0.0

    stations = weather.get("stations", {})
    if not stations:
        return 0.0

    # Sample weather at each POI waypoint; fall back to start point if no POIs
    sample_points = [(wp.point.lat, wp.point.lng) for wp in poi_waypoints] if poi_waypoints else [(start_point.lat, start_point.lng)]

    scores = []
    for lat, lng in sample_points:
        station = _nearest_station(lat, lng, stations)
        if station:
            scores.append(_score_station_conditions(station))

    return sum(scores) / len(scores) if scores else 0.0


def _get_weather() -> dict | None:
    """Fetch weather data from Redis. Returns None on any failure."""
    try:
        raw = redis_client.get("weather:latest")
        if raw:
            logger.info("Weather data fetched from Redis (%d bytes)", len(raw))
            return json.loads(raw)
        logger.warning("No weather data found in Redis (key: weather:latest)")
        return None
    except Exception as exc:
        logger.warning("Failed to fetch weather from Redis: %s", exc)
        return None


def _score_route(distance_km: float, total_ascent_m: float, preferences, poi_waypoints: list, start_point, weather: dict | None, community_rating: float = 0.0, shade_score: float = 0.0) -> float:
    cyclist_score = _score_cyclist_type(distance_km, preferences.cyclist_type)
    elevation_score = _score_elevation(total_ascent_m, preferences.elevation_preference)
    air_quality_score = _score_air_quality(preferences.air_quality_preference, poi_waypoints, start_point, weather)
    shade_score_val = _score_shade(shade_score, preferences.shade_preference)
    rating_score = community_rating / 5.0  # normalise 0–5 → 0–1
    logger.info("Route scoring — distance: %.2f km, ascent: %.1f m | cyclist_type score: %.3f | elevation score: %.3f | air_quality score: %.3f | shade score: %.3f | rating score: %.3f", distance_km, total_ascent_m, cyclist_score, elevation_score, air_quality_score, shade_score_val, rating_score)
    return cyclist_score + elevation_score + air_quality_score + shade_score_val + rating_score


@dataclass
class _ComboResult:
    result: RecommendationResult
    poi_waypoints: list
    ascent_m: float


async def _try_combo(
    combo: dict,
    req: RecommendationsRequest,
    places_db: AsyncSession,
    mongo: AsyncDatabase,
    seen_fingerprints: list[tuple],
) -> "_ComboResult | None":
    from .route_suggestion import recommend_route

    poi_prefs = req.preferences.points_of_interest
    route_req = RouteRequest(
        origin=Point(lat=req.start_point.lat, lng=req.start_point.lng),
        destination=Point(lat=req.end_point.lat, lng=req.end_point.lng),
        waypoints=[Point(lat=cp.lat, lng=cp.lng) for cp in req.checkpoints],
        preferences=RoutePreferences(
            include_hawker_centres=combo["include_hawker_centres"] and poi_prefs.allow_hawker_center,
            include_parks=combo["include_parks"] and poi_prefs.allow_park,
            include_historic_sites=combo["include_historic_sites"] and poi_prefs.allow_historic_site,
            include_tourist_attractions=combo["include_tourist_attractions"] and poi_prefs.allow_tourist_attraction,
        ),
    )

    try:
        route = await recommend_route(places_db, route_req)
    except Exception as exc:
        logger.warning("Route computation failed for combo %s, skipping: %s", combo, exc)
        return None

    if req.preferences.max_distance is not None and route.distance > req.preferences.max_distance:
        logger.info("Route exceeds max_distance (%.2f km > %.2f km), skipping", route.distance, req.preferences.max_distance)
        return None

    path = route.path
    fingerprint = tuple(
        (round(p.lat, 4), round(p.lng, 4))
        for p in [path[0], path[len(path) // 2], path[-1]]
    )
    if fingerprint in seen_fingerprints:
        logger.info("Skipping duplicate route (fingerprint: %s)", fingerprint)
        return None
    seen_fingerprints.append(fingerprint)

    start_name = req.start_point.name or f"{req.start_point.lat:.4f}, {req.start_point.lng:.4f}"
    end_name = req.end_point.name or f"{req.end_point.lat:.4f}, {req.end_point.lng:.4f}"

    pois = [
        {"name": p.name, "description": p.category.value, "lat": p.point.lat, "lng": p.point.lng}
        for p in route.poi_waypoints
    ]
    checkpoints = [
        {"checkpoint_id": f"cp_{i + 1:03d}", "checkpoint_name": p["name"], "description": p["description"], "lat": p["lat"], "lng": p["lng"]}
        for i, p in enumerate(pois)
    ]

    doc = {
        "source": "generated",
        "name": f"{start_name} → {end_name}",
        "description": None,
        "coordinates": [[p.lng, p.lat] for p in route.path],
        "distance_m": round(route.distance * 1000, 1),
        "estimated_time_min": round(route.duration),
        "start_point": {"lat": req.start_point.lat, "lng": req.start_point.lng, "name": req.start_point.name},
        "end_point": {"lat": req.end_point.lat, "lng": req.end_point.lng, "name": req.end_point.name},
        "cyclist_type": req.preferences.cyclist_type.value,
        "elevation": req.preferences.elevation_preference.value,
        "shade": req.preferences.shade_preference.value,
        "air_quality": req.preferences.air_quality_preference.value,
        "checkpoints": checkpoints,
        "points_of_interest_visited": pois,
        "review_count": 0,
        "rating": 0.0,
        "created_at": datetime.now(timezone.utc),
        **({"computation_time_ms": route.computation_time_ms} if route.computation_time_ms is not None else {}),
    }

    inserted = await mongo[_GENERATED_COLLECTION].insert_one(doc)
    route_id_str = str(inserted.inserted_id)

    recommendation = RecommendationResult(
        route_id=route_id_str,
        name=doc["name"],
        description=doc["description"],
        distance=route.distance,
        estimated_time=round(route.duration),
        elevation=req.preferences.elevation_preference,
        shade=req.preferences.shade_preference,
        air_quality=req.preferences.air_quality_preference,
        cyclist_type=req.preferences.cyclist_type,
        review_count=0,
        rating=0.0,
        points_of_interest_visited=[
            POIVisited(name=p["name"], description=p["description"], lat=p["lat"], lng=p["lng"])
            for p in pois
        ],
        shade_score=route.shade_score,
    )
    return _ComboResult(
        result=recommendation,
        poi_waypoints=route.poi_waypoints,
        ascent_m=route.total_ascent_m,
    )


async def get_recommendations(
    mongo: AsyncDatabase,
    places_db: AsyncSession,
    req: RecommendationsRequest,
) -> list[RecommendationResult]:
    # 1. Check Redis Cache
    request_dump = req.model_dump_json()
    cache_key = f"routes:recommendations:{hashlib.md5(request_dump.encode()).hexdigest()}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            logger.info("Serving recommendations from cache: %s", cache_key)
            return [RecommendationResult.model_validate(res) for res in json.loads(cached)]
    except Exception as exc:
        logger.warning("Redis error in get_recommendations check: %s", exc)

    # 2. Compute Recommendations
    poi_prefs = req.preferences.points_of_interest
    weather = _get_weather()
    results = []
    poi_waypoints_per_result = []
    ascents_per_result = []

    eligible_combos = [
        c for c in _POI_COMBOS
        if (c["include_hawker_centres"] and poi_prefs.allow_hawker_center)
        or (c["include_parks"] and poi_prefs.allow_park)
        or (c["include_historic_sites"] and poi_prefs.allow_historic_site)
        or (c["include_tourist_attractions"] and poi_prefs.allow_tourist_attraction)
    ]
    if not eligible_combos:
        eligible_combos = [{"include_hawker_centres": False, "include_parks": False, "include_historic_sites": False, "include_tourist_attractions": False}]

    seen_fingerprints: list[tuple] = []

    for combo in eligible_combos[:req.limit]:
        combo_result = await _try_combo(combo, req, places_db, mongo, seen_fingerprints)
        if combo_result:
            results.append(combo_result.result)
            poi_waypoints_per_result.append(combo_result.poi_waypoints)
            ascents_per_result.append(combo_result.ascent_m)

    # Fallback: if all combos failed or were filtered, try a no-POI route
    if not results:
        no_poi_combo = {k: False for k in _POI_COMBOS[0]}
        combo_result = await _try_combo(no_poi_combo, req, places_db, mongo, seen_fingerprints)
        if combo_result:
            results.append(combo_result.result)
            poi_waypoints_per_result.append(combo_result.poi_waypoints)
            ascents_per_result.append(combo_result.ascent_m)

    # 3. Rank results by score (highest first)
    ranked = sorted(
        zip(results, poi_waypoints_per_result, ascents_per_result),
        key=lambda pair: _score_route(pair[0].distance, pair[2], req.preferences, pair[1], req.start_point, weather, shade_score=pair[0].shade_score),
        reverse=True,
    )
    results = [r for r, _, _ in ranked]

    # 4. Cache the results for 30 minutes
    try:
        if results:
            redis_client.set(
                cache_key, 
                json.dumps([res.model_dump() for res in results]), 
                ex=1800
            )
    except Exception:
        pass

    return results


def _doc_to_route_detail_generated(doc: dict) -> RouteDetail:
    """Convert a generated-routes MongoDB document to a RouteDetail."""
    coords = doc.get("coordinates", [])
    sp = doc.get("start_point", {})
    ep = doc.get("end_point", {})
    return RouteDetail(
        route_id=str(doc["_id"]),
        name=doc.get("name") or "",
        description=doc.get("description"),
        distance=round(doc.get("distance_m", 0) / 1000, 2),
        estimated_time=round(doc.get("estimated_time_min", 0)),
        elevation=doc.get("elevation", ElevationPreference.DONT_CARE),
        shade=doc.get("shade", ShadePreference.DONT_CARE),
        air_quality=doc.get("air_quality", AirQualityPreference.DONT_CARE),
        cyclist_type=doc.get("cyclist_type", CyclistType.GENERAL),
        review_count=doc.get("review_count", 0),
        rating=doc.get("rating", 0.0),
        checkpoints=doc.get("checkpoints", []),
        points_of_interest_visited=doc.get("points_of_interest_visited", []),
        start_point=NamedLatLng(lat=sp.get("lat", 0.0), lng=sp.get("lng", 0.0), name=sp.get("name")),
        end_point=NamedLatLng(lat=ep.get("lat", 0.0), lng=ep.get("lng", 0.0), name=ep.get("name")),
        route_path=[LatLng(lat=c[1], lng=c[0]) for c in coords],
    )


async def get_route_by_id(db: AsyncDatabase, route_id: str) -> RouteDetail | None:
    try:
        oid = ObjectId(route_id)
    except Exception:
        return None

    doc = await db[_PRECOMPUTED_COLLECTION].find_one({"_id": oid})
    if doc is not None:
        coords = doc.get("coordinates", [])
        summary = _doc_to_route_summary(doc)
        return RouteDetail(
            **summary.model_dump(),
            route_path=[LatLng(lat=c[1], lng=c[0]) for c in coords],
        )

    doc = await db[_GENERATED_COLLECTION].find_one({"_id": oid})
    if doc is not None:
        return _doc_to_route_detail_generated(doc)

    return None
