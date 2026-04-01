import json
import logging

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clients.redis import redis_client
from ..models import HistoricSite
from ..schemas import HistoricSiteResponse

logger = logging.getLogger(__name__)

_TTL = 86400  # 24 hours


async def list_historic_sites(
    db: AsyncSession, *, limit: int = 100, offset: int = 0
) -> list[HistoricSiteResponse]:
    cache_key = f"poi:historic:list:{limit}:{offset}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return [HistoricSiteResponse.model_validate(item) for item in json.loads(cached)]
    except Exception as exc:
        logger.warning("Redis error in list_historic_sites: %s", exc)

    result = await db.execute(select(HistoricSite).offset(offset).limit(limit))
    records = list(result.scalars().all())
    items = [HistoricSiteResponse.model_validate(r) for r in records]

    try:
        redis_client.set(cache_key, json.dumps([i.model_dump() for i in items]), ex=_TTL)
    except Exception as exc:
        logger.warning("Failed to cache historic sites list: %s", exc)

    return items


async def count_historic_sites(db: AsyncSession) -> int:
    cache_key = "poi:historic:count"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return int(cached)
    except Exception as exc:
        logger.warning("Redis error in count_historic_sites: %s", exc)

    result = await db.execute(select(func.count()).select_from(HistoricSite))
    count = result.scalar_one()

    try:
        redis_client.set(cache_key, str(count), ex=_TTL)
    except Exception as exc:
        logger.warning("Failed to cache historic sites count: %s", exc)

    return count


async def get_historic_site(db: AsyncSession, id: int) -> HistoricSiteResponse | None:
    cache_key = f"poi:historic:id:{id}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return HistoricSiteResponse.model_validate_json(cached)
    except Exception as exc:
        logger.warning("Redis error in get_historic_site: %s", exc)

    result = await db.execute(select(HistoricSite).where(HistoricSite.id == id))
    record = result.scalar_one_or_none()
    if record is None:
        return None

    item = HistoricSiteResponse.model_validate(record)
    try:
        redis_client.set(cache_key, item.model_dump_json(), ex=_TTL)
    except Exception as exc:
        logger.warning("Failed to cache historic site: %s", exc)

    return item


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
