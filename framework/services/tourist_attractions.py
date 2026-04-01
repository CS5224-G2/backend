import json
import logging

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clients.redis import redis_client
from ..models import TouristAttraction
from ..schemas import TouristAttractionResponse

logger = logging.getLogger(__name__)

_TTL = 86400  # 24 hours


async def list_tourist_attractions(
    db: AsyncSession, *, limit: int = 100, offset: int = 0
) -> list[TouristAttractionResponse]:
    cache_key = f"poi:tourist:list:{limit}:{offset}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return [TouristAttractionResponse.model_validate(item) for item in json.loads(cached)]
    except Exception as exc:
        logger.warning("Redis error in list_tourist_attractions: %s", exc)

    result = await db.execute(select(TouristAttraction).offset(offset).limit(limit))
    records = list(result.scalars().all())
    items = [TouristAttractionResponse.model_validate(r) for r in records]

    try:
        redis_client.set(cache_key, json.dumps([i.model_dump() for i in items]), ex=_TTL)
    except Exception as exc:
        logger.warning("Failed to cache tourist attractions list: %s", exc)

    return items


async def count_tourist_attractions(db: AsyncSession) -> int:
    cache_key = "poi:tourist:count"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return int(cached)
    except Exception as exc:
        logger.warning("Redis error in count_tourist_attractions: %s", exc)

    result = await db.execute(select(func.count()).select_from(TouristAttraction))
    count = result.scalar_one()

    try:
        redis_client.set(cache_key, str(count), ex=_TTL)
    except Exception as exc:
        logger.warning("Failed to cache tourist attractions count: %s", exc)

    return count


async def get_tourist_attraction(db: AsyncSession, id: int) -> TouristAttractionResponse | None:
    cache_key = f"poi:tourist:id:{id}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return TouristAttractionResponse.model_validate_json(cached)
    except Exception as exc:
        logger.warning("Redis error in get_tourist_attraction: %s", exc)

    result = await db.execute(select(TouristAttraction).where(TouristAttraction.id == id))
    record = result.scalar_one_or_none()
    if record is None:
        return None

    item = TouristAttractionResponse.model_validate(record)
    try:
        redis_client.set(cache_key, item.model_dump_json(), ex=_TTL)
    except Exception as exc:
        logger.warning("Failed to cache tourist attraction: %s", exc)

    return item


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
