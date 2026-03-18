from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from ..database import PlacesDB
from ..schemas import HawkerCentreResponse, Paginated
from ..services import hawker as hawker_service

router = APIRouter(prefix="/hawker-centres", tags=["Hawker Centres"])

_Limit = Annotated[int, Query(ge=1, le=500)]
_Offset = Annotated[int, Query(ge=0)]
_NearbyLimit = Annotated[int, Query(ge=1, le=100)]
_Lat = Annotated[float, Query(ge=-90, le=90)]
_Lng = Annotated[float, Query(ge=-180, le=180)]
_RadiusM = Annotated[float, Query(gt=0, le=50000)]


@router.get("/", response_model=Paginated[HawkerCentreResponse])
async def list_hawker_centres(db: PlacesDB, limit: _Limit = 100, offset: _Offset = 0):
    items = await hawker_service.list_hawker_centres(db, limit=limit, offset=offset)
    total = await hawker_service.count_hawker_centres(db)
    return Paginated(items=items, total=total, limit=limit, offset=offset)


@router.get("/nearby", response_model=list[HawkerCentreResponse])
async def nearby_hawker_centres(
    db: PlacesDB,
    lat: _Lat,
    lng: _Lng,
    radius_m: _RadiusM = 1000,
    limit: _NearbyLimit = 20,
):
    rows = await hawker_service.list_nearby_hawker_centres(
        db, lat=lat, lng=lng, radius_m=radius_m, limit=limit
    )
    return [_merge(row.HawkerCentre, row.distance_m) for row in rows]


@router.get("/{id}", response_model=HawkerCentreResponse, responses={404: {"description": "Hawker centre not found"}})
async def get_hawker_centre(id: int, db: PlacesDB):
    record = await hawker_service.get_hawker_centre(db, id)
    if record is None:
        raise HTTPException(status_code=404, detail="Hawker centre not found")
    return record


def _merge(obj, distance_m: float) -> HawkerCentreResponse:
    data = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    data["distance_m"] = distance_m
    return HawkerCentreResponse.model_validate(data)
