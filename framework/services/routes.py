from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from ..schemas import (
    AirQualityPreference,
    CyclistType,
    ElevationPreference,
    NamedLatLng,
    RouteSummary,
    ShadePreference,
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
