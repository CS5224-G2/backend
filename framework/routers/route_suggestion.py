from fastapi import APIRouter
from ..schemas import RouteRequest, RouteResponse
from ..services import route_suggestion as route_service

router = APIRouter(prefix="/route-suggestion", tags=["Route Suggestion"])

@router.post("/recommend", response_model=RouteResponse)
async def recommend_route(req: RouteRequest):
    route = route_service.recommend_route(req)
    return route
