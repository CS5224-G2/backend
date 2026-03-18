from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import TouristAttraction


async def list_tourist_attractions(
    db: AsyncSession, *, limit: int = 100, offset: int = 0
) -> list[TouristAttraction]:
    result = await db.execute(
        select(TouristAttraction).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


async def count_tourist_attractions(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(TouristAttraction))
    return result.scalar_one()


async def get_tourist_attraction(db: AsyncSession, id: int) -> TouristAttraction | None:
    result = await db.execute(
        select(TouristAttraction).where(TouristAttraction.id == id)
    )
    return result.scalar_one_or_none()


async def list_nearby_tourist_attractions(
    db: AsyncSession,
    *,
    lat: float,
    lng: float,
    radius_m: float,
    limit: int = 20,
):
    """Return tourist attractions within radius_m metres of (lat, lng), ordered by distance."""
    point = cast(func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326), Geography)
    dist = func.ST_Distance(TouristAttraction.geom, point).label("distance_m")
    result = await db.execute(
        select(TouristAttraction, dist)
        .where(func.ST_DWithin(TouristAttraction.geom, point, radius_m))
        .order_by(func.ST_Distance(TouristAttraction.geom, point))
        .limit(limit)
    )
    return result.all()
