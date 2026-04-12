from fastapi import APIRouter, HTTPException, Path, Query, Depends, status

from ..database import MongoDB, PlacesDB
from ..dependencies import CurrentUser
from ..schemas import CyclistType, RecommendationResult, RecommendationsRequest, RouteDetail, RouteSummary, SaveRouteRequest, SaveRouteResponse, SavedRoutesResponse
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


@router.post("/save", status_code=status.HTTP_201_CREATED)
async def save_route(
    body: SaveRouteRequest,
    current_user: CurrentUser,
    db: PlacesDB,
    mongo: MongoDB,
) -> SaveRouteResponse:
    record = await routes_service.save_route(db, mongo, current_user.id, body)
    return SaveRouteResponse(
        saved_route_id=str(record.id),
        route_id=record.route_id,
        saved_at=record.saved_at.isoformat(),
    )


@router.get("/saved", response_model=SavedRoutesResponse)
async def get_saved_routes(
    current_user: CurrentUser,
    db: PlacesDB,
    mongo: MongoDB,
):
    return await routes_service.get_saved_routes(db, mongo, current_user.id)


@router.delete("/saved/{saved_route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_route(
    saved_route_id: str,
    current_user: CurrentUser,
    db: PlacesDB,
    mongo: MongoDB,
):
    await routes_service.delete_saved_route(db, mongo, current_user.id, saved_route_id)


@router.post("/recommendations", response_model=list[RecommendationResult])
async def post_recommendations(body: RecommendationsRequest, mongo: MongoDB):
    return await routes_service.get_recommendations(mongo, body)


@router.get("/{route_id}", response_model=RouteDetail, dependencies=[Depends(cdn_cache(300))])
async def get_route(
    db: MongoDB,
    route_id: str = Path(examples=["69c7eeb258d7af07774a41f2"]),
):
    route = await routes_service.get_route_by_id(db, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return route
