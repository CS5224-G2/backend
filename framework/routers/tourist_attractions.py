from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from ..database import PlacesDB
from ..schemas import TouristAttractionResponse, Paginated
from ..services import tourist_attractions as tourist_attractions_service

router = APIRouter(prefix="/tourist-attractions", tags=["Tourist Attractions"])

_Limit = Annotated[int, Query(ge=1, le=500)]
_Offset = Annotated[int, Query(ge=0)]
_NearbyLimit = Annotated[int, Query(ge=1, le=100)]
_Lat = Annotated[float, Query(ge=-90, le=90)]
_Lng = Annotated[float, Query(ge=-180, le=180)]
_RadiusM = Annotated[float, Query(gt=0, le=50000)]


@router.get("/", response_model=Paginated[TouristAttractionResponse])
async def list_tourist_attractions(db: PlacesDB, limit: _Limit = 100, offset: _Offset = 0):
    items = await tourist_attractions_service.list_tourist_attractions(
        db, limit=limit, offset=offset
    )
    total = await tourist_attractions_service.count_tourist_attractions(db)
    return Paginated(items=items, total=total, limit=limit, offset=offset)


@router.get("/nearby", response_model=list[TouristAttractionResponse])
async def nearby_tourist_attractions(
    db: PlacesDB,
    lat: _Lat,
    lng: _Lng,
    radius_m: _RadiusM = 1000,
    limit: _NearbyLimit = 20,
):
    rows = await tourist_attractions_service.list_nearby_tourist_attractions(
        db, lat=lat, lng=lng, radius_m=radius_m, limit=limit
    )
    return [_merge(row.TouristAttraction, row.distance_m) for row in rows]


@router.get("/{id}", response_model=TouristAttractionResponse, responses={404: {"description": "Tourist attraction not found"}})
async def get_tourist_attraction(id: int, db: PlacesDB):
    record = await tourist_attractions_service.get_tourist_attraction(db, id)
    if record is None:
        raise HTTPException(status_code=404, detail="Tourist attraction not found")
    return record


def _merge(obj, distance_m: float) -> TouristAttractionResponse:
    data = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    data["distance_m"] = distance_m
    return TouristAttractionResponse.model_validate(data)
