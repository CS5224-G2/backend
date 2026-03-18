from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from ..database import PlacesDB
from ..schemas import ParkResponse, Paginated
from ..services import parks as parks_service

router = APIRouter(prefix="/parks", tags=["Parks"])

_Limit = Annotated[int, Query(ge=1, le=500)]
_Offset = Annotated[int, Query(ge=0)]
_NearbyLimit = Annotated[int, Query(ge=1, le=100)]
_Lat = Annotated[float, Query(ge=-90, le=90)]
_Lng = Annotated[float, Query(ge=-180, le=180)]
_RadiusM = Annotated[float, Query(gt=0, le=50000)]


@router.get("/", response_model=Paginated[ParkResponse])
async def list_parks(db: PlacesDB, limit: _Limit = 100, offset: _Offset = 0):
    items = await parks_service.list_parks(db, limit=limit, offset=offset)
    total = await parks_service.count_parks(db)
    return Paginated(items=items, total=total, limit=limit, offset=offset)


@router.get("/nearby", response_model=list[ParkResponse])
async def nearby_parks(
    db: PlacesDB,
    lat: _Lat,
    lng: _Lng,
    radius_m: _RadiusM = 1000,
    limit: _NearbyLimit = 20,
):
    rows = await parks_service.list_nearby_parks(
        db, lat=lat, lng=lng, radius_m=radius_m, limit=limit
    )
    return [_merge(row.Park, row.distance_m) for row in rows]


@router.get("/{id}", response_model=ParkResponse, responses={404: {"description": "Park not found"}})
async def get_park(id: int, db: PlacesDB):
    record = await parks_service.get_park(db, id)
    if record is None:
        raise HTTPException(status_code=404, detail="Park not found")
    return record


def _merge(obj, distance_m: float) -> ParkResponse:
    data = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    data["distance_m"] = distance_m
    return ParkResponse.model_validate(data)
