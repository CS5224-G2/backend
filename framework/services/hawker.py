from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import HawkerCentre


async def list_hawker_centres(
    db: AsyncSession, *, limit: int = 100, offset: int = 0
) -> list[HawkerCentre]:
    result = await db.execute(
        select(HawkerCentre).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


async def count_hawker_centres(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(HawkerCentre))
    return result.scalar_one()


async def get_hawker_centre(db: AsyncSession, id: int) -> HawkerCentre | None:
    result = await db.execute(
        select(HawkerCentre).where(HawkerCentre.id == id)
    )
    return result.scalar_one_or_none()


async def list_nearby_hawker_centres(
    db: AsyncSession,
    *,
    lat: float,
    lng: float,
    radius_m: float,
    limit: int = 20,
):
    """Return hawker centres within radius_m metres of (lat, lng), ordered by distance."""
    point = cast(func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326), Geography)
    dist = func.ST_Distance(HawkerCentre.geom, point).label("distance_m")
    result = await db.execute(
        select(HawkerCentre, dist)
        .where(func.ST_DWithin(HawkerCentre.geom, point, radius_m))
        .order_by(func.ST_Distance(HawkerCentre.geom, point))
        .limit(limit)
    )
    return result.all()
