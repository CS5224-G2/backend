from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from ..database import PlacesDB
from ..schemas import HistoricSiteResponse, Paginated
from ..services import historic_sites as historic_sites_service

router = APIRouter(prefix="/historic-sites", tags=["Historic Sites"])

_Limit = Annotated[int, Query(ge=1, le=500)]
_Offset = Annotated[int, Query(ge=0)]
_NearbyLimit = Annotated[int, Query(ge=1, le=100)]
_Lat = Annotated[float, Query(ge=-90, le=90)]
_Lng = Annotated[float, Query(ge=-180, le=180)]
_RadiusM = Annotated[float, Query(gt=0, le=50000)]


@router.get("/", response_model=Paginated[HistoricSiteResponse])
async def list_historic_sites(db: PlacesDB, limit: _Limit = 100, offset: _Offset = 0):
    items = await historic_sites_service.list_historic_sites(db, limit=limit, offset=offset)
    total = await historic_sites_service.count_historic_sites(db)
    return Paginated(items=items, total=total, limit=limit, offset=offset)


@router.get("/nearby", response_model=list[HistoricSiteResponse])
async def nearby_historic_sites(
    db: PlacesDB,
    lat: _Lat,
    lng: _Lng,
    radius_m: _RadiusM = 1000,
    limit: _NearbyLimit = 20,
):
    rows = await historic_sites_service.list_nearby_historic_sites(
        db, lat=lat, lng=lng, radius_m=radius_m, limit=limit
    )
    return [_merge(row.HistoricSite, row.distance_m) for row in rows]


@router.get("/{id}", response_model=HistoricSiteResponse, responses={404: {"description": "Historic site not found"}})
async def get_historic_site(id: int, db: PlacesDB):
    record = await historic_sites_service.get_historic_site(db, id)
    if record is None:
        raise HTTPException(status_code=404, detail="Historic site not found")
    return record


def _merge(obj, distance_m: float) -> HistoricSiteResponse:
    data = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    data["distance_m"] = distance_m
    return HistoricSiteResponse.model_validate(data)
