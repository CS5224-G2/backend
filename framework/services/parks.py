import json
import logging

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clients.redis import redis_client
from ..models import Park
from ..schemas import ParkResponse

logger = logging.getLogger(__name__)

_TTL = 86400  # 24 hours


async def list_parks(
    db: AsyncSession, *, limit: int = 100, offset: int = 0
) -> list[ParkResponse]:
    cache_key = f"poi:park:list:{limit}:{offset}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return [ParkResponse.model_validate(item) for item in json.loads(cached)]
    except Exception as exc:
        logger.warning("Redis error in list_parks: %s", exc)

    result = await db.execute(select(Park).offset(offset).limit(limit))
    records = list(result.scalars().all())
    items = [ParkResponse.model_validate(r) for r in records]

    try:
        redis_client.set(cache_key, json.dumps([i.model_dump() for i in items]), ex=_TTL)
    except Exception as exc:
        logger.warning("Failed to cache parks list: %s", exc)

    return items


async def count_parks(db: AsyncSession) -> int:
    cache_key = "poi:park:count"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return int(cached)
    except Exception as exc:
        logger.warning("Redis error in count_parks: %s", exc)

    result = await db.execute(select(func.count()).select_from(Park))
    count = result.scalar_one()

    try:
        redis_client.set(cache_key, str(count), ex=_TTL)
    except Exception as exc:
        logger.warning("Failed to cache parks count: %s", exc)

    return count


async def get_park(db: AsyncSession, id: int) -> ParkResponse | None:
    cache_key = f"poi:park:id:{id}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return ParkResponse.model_validate_json(cached)
    except Exception as exc:
        logger.warning("Redis error in get_park: %s", exc)

    result = await db.execute(select(Park).where(Park.id == id))
    record = result.scalar_one_or_none()
    if record is None:
        return None

    item = ParkResponse.model_validate(record)
    try:
        redis_client.set(cache_key, item.model_dump_json(), ex=_TTL)
    except Exception as exc:
        logger.warning("Failed to cache park: %s", exc)

    return item


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
