import json
import logging

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clients.redis import redis_client
from ..models import HawkerCentre
from ..schemas import HawkerCentreResponse

logger = logging.getLogger(__name__)

_TTL = 86400  # 24 hours


async def list_hawker_centres(
    db: AsyncSession, *, limit: int = 100, offset: int = 0
) -> list[HawkerCentreResponse]:
    cache_key = f"poi:hawker:list:{limit}:{offset}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return [HawkerCentreResponse.model_validate(item) for item in json.loads(cached)]
    except Exception as exc:
        logger.warning("Redis error in list_hawker_centres: %s", exc)

    result = await db.execute(select(HawkerCentre).offset(offset).limit(limit))
    records = list(result.scalars().all())
    items = [HawkerCentreResponse.model_validate(r) for r in records]

    try:
        redis_client.set(cache_key, json.dumps([i.model_dump() for i in items]), ex=_TTL)
    except Exception as exc:
        logger.warning("Failed to cache hawker list: %s", exc)

    return items


async def count_hawker_centres(db: AsyncSession) -> int:
    cache_key = "poi:hawker:count"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return int(cached)
    except Exception as exc:
        logger.warning("Redis error in count_hawker_centres: %s", exc)

    result = await db.execute(select(func.count()).select_from(HawkerCentre))
    count = result.scalar_one()

    try:
        redis_client.set(cache_key, str(count), ex=_TTL)
    except Exception as exc:
        logger.warning("Failed to cache hawker count: %s", exc)

    return count


async def get_hawker_centre(db: AsyncSession, id: int) -> HawkerCentreResponse | None:
    cache_key = f"poi:hawker:id:{id}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return HawkerCentreResponse.model_validate_json(cached)
    except Exception as exc:
        logger.warning("Redis error in get_hawker_centre: %s", exc)

    result = await db.execute(select(HawkerCentre).where(HawkerCentre.id == id))
    record = result.scalar_one_or_none()
    if record is None:
        return None

    item = HawkerCentreResponse.model_validate(record)
    try:
        redis_client.set(cache_key, item.model_dump_json(), ex=_TTL)
    except Exception as exc:
        logger.warning("Failed to cache hawker centre: %s", exc)

    return item


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
