from fastapi import APIRouter

from ..database import PlacesDB
from ..schemas import RouteRequest, RouteResponse
from ..services import route_suggestion as route_service

router = APIRouter(prefix="/route-suggestion", tags=["Route Suggestion"])


@router.post("/recommend", response_model=RouteResponse)
async def recommend_route(req: RouteRequest, db: PlacesDB):
    return await route_service.recommend_route(db, req)
