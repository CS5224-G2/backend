from fastapi import APIRouter, HTTPException, Path, Query, Depends

from ..database import MongoDB, PlacesDB
from ..schemas import CyclistType, RecommendationResult, RecommendationsRequest, RouteDetail, RouteSummary
from ..services import routes as routes_service
from ..utils.cache import cdn_cache

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.get("", response_model=list[RouteSummary])
async def get_routes(
    db: MongoDB,
    cyclist_type: CyclistType | None = Query(default=None),
    limit: int = Query(default=3, ge=1, le=3),
):
    return await routes_service.get_routes(db, cyclist_type=cyclist_type, limit=limit)


@router.get("/popular", response_model=list[RouteSummary], dependencies=[Depends(cdn_cache(3600))])
async def get_popular_routes(
    db: MongoDB,
    limit: int = Query(default=3, ge=1, le=3),
):
    return await routes_service.get_popular_routes(db, limit=limit)


@router.post("/recommendations", response_model=list[RecommendationResult])
async def post_recommendations(body: RecommendationsRequest, mongo: MongoDB, places_db: PlacesDB):
    return await routes_service.get_recommendations(mongo, places_db, body)


@router.get("/{route_id}", response_model=RouteDetail)
async def get_route(
    db: MongoDB,
    route_id: str = Path(example="69c7eeb258d7af07774a41f2"),
):
    route = await routes_service.get_route_by_id(db, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route
