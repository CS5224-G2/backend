from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import HistoricSite


async def list_historic_sites(
    db: AsyncSession, *, limit: int = 100, offset: int = 0
) -> list[HistoricSite]:
    result = await db.execute(
        select(HistoricSite).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


async def count_historic_sites(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(HistoricSite))
    return result.scalar_one()


async def get_historic_site(db: AsyncSession, id: int) -> HistoricSite | None:
    result = await db.execute(
        select(HistoricSite).where(HistoricSite.id == id)
    )
    return result.scalar_one_or_none()


async def list_nearby_historic_sites(
    db: AsyncSession,
    *,
    lat: float,
    lng: float,
    radius_m: float,
    limit: int = 20,
):
    """Return historic sites within radius_m metres of (lat, lng), ordered by distance."""
    point = cast(func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326), Geography)
    dist = func.ST_Distance(HistoricSite.geom, point).label("distance_m")
    result = await db.execute(
        select(HistoricSite, dist)
        .where(func.ST_DWithin(HistoricSite.geom, point, radius_m))
        .order_by(func.ST_Distance(HistoricSite.geom, point))
        .limit(limit)
    )
    return result.all()
