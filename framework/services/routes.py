from datetime import datetime, timezone

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import (
    AirQualityPreference,
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
    ShadePreference,
    Point,
)

_PRECOMPUTED_COLLECTION = "precomputed-routes"


def _doc_to_route_summary(doc: dict) -> RouteSummary:
    """Convert a precomputed-routes MongoDB document to a RouteSummary."""
    coords = doc.get("coordinates", [])
    first = coords[0] if coords else [0.0, 0.0]   # [lng, lat]
    last  = coords[-1] if coords else [0.0, 0.0]

    return RouteSummary(
        route_id=str(doc["_id"]),
        name=doc.get("name") or "",
        description=doc.get("type"),
        distance=round(doc.get("distance_m", 0) / 1000, 2),
        estimated_time=round(doc.get("estimated_time_min", 0)),
        elevation=ElevationPreference.DONT_CARE,
        shade=ShadePreference.DONT_CARE,
        air_quality=AirQualityPreference.DONT_CARE,
        cyclist_type=CyclistType.GENERAL,
        review_count=0,
        rating=0.0,
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
    if cyclist_type is not None:
        query["cyclist_type"] = cyclist_type.value

    cursor = db[_PRECOMPUTED_COLLECTION].find(query).limit(limit)
    return [_doc_to_route_summary(doc) async for doc in cursor]


async def get_popular_routes(
    db: AsyncDatabase,
    limit: int = 3,
) -> list[RouteSummary]:
    cursor = (
        db[_PRECOMPUTED_COLLECTION]
        .find({"source": "precomputed"})
        .sort([("review_count", -1), ("rating", -1)])
        .limit(limit)
    )
    return [_doc_to_route_summary(doc) async for doc in cursor]


_GENERATED_COLLECTION = "generated-routes"

# Each tuple defines which POI categories are active for that route variant.
# Varied across 3 calls so each recommendation has a different set of waypoints.
_POI_COMBOS = [
    {"include_hawker_centres": True,  "include_parks": True,  "include_historic_sites": False, "include_tourist_attractions": False},
    {"include_hawker_centres": False, "include_parks": False, "include_historic_sites": True,  "include_tourist_attractions": True},
    {"include_hawker_centres": True,  "include_parks": True,  "include_historic_sites": True,  "include_tourist_attractions": True},
]


async def get_recommendations(
    mongo: AsyncDatabase,
    places_db: AsyncSession,
    req: RecommendationsRequest,
) -> list[RecommendationResult]:
    from .route_suggestion import recommend_route

    poi_prefs = req.preferences.points_of_interest
    results = []

    for combo in _POI_COMBOS:
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

        route = await recommend_route(places_db, route_req)

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
        }

        inserted = await mongo[_GENERATED_COLLECTION].insert_one(doc)

        results.append(RecommendationResult(
            route_id=str(inserted.inserted_id),
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
        ))

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
