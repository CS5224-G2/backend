from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Park


async def list_parks(
    db: AsyncSession, *, limit: int = 100, offset: int = 0
) -> list[Park]:
    result = await db.execute(
        select(Park).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


async def count_parks(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(Park))
    return result.scalar_one()


async def get_park(db: AsyncSession, id: int) -> Park | None:
    result = await db.execute(
        select(Park).where(Park.id == id)
    )
    return result.scalar_one_or_none()


async def list_nearby_parks(
    db: AsyncSession,
    *,
    lat: float,
    lng: float,
    radius_m: float,
    limit: int = 20,
):
    """Return parks within radius_m metres of (lat, lng), ordered by distance."""
    point = cast(func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326), Geography)
    dist = func.ST_Distance(Park.geom, point).label("distance_m")
    result = await db.execute(
        select(Park, dist)
        .where(func.ST_DWithin(Park.geom, point, radius_m))
        .order_by(func.ST_Distance(Park.geom, point))
        .limit(limit)
    )
    return result.all()
