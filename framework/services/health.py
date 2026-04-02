import logging
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pymongo.asynchronous.database import AsyncDatabase
import asyncio

from ..config import settings
from ..clients.http import service_client
from ..clients.redis import redis_client

logger = logging.getLogger(__name__)

async def get_system_health(places_db: AsyncSession, mongo_db: AsyncDatabase) -> dict:
    """
    Ping all dependencies and services to assemble a health status dictionary.
    """
    health = {
        "status": "healthy",
        "dependencies": {},
        "microservices": {}
    }

    # Ping Postgres
    try:
        await places_db.execute(text("SELECT 1"))
        health["dependencies"]["postgresql"] = "up"
    except Exception as e:
        logger.error(f"Postgres health check failed: {e}")
        health["dependencies"]["postgresql"] = "down"
        health["status"] = "degraded"

    # Ping MongoDB
    try:
        await mongo_db.command("ping")
        health["dependencies"]["mongodb"] = "up"
    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        health["dependencies"]["mongodb"] = "down"
        health["status"] = "degraded"

    # Ping Redis
    try:
        # Use shared global client
        await asyncio.to_thread(redis_client.ping)
        health["dependencies"]["redis"] = "up"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        health["dependencies"]["redis"] = "down"
        health["status"] = "degraded"

    # Ping configured microservices
    for service_name in settings.SERVICE_URLS.keys():
        try:
            # Assumes each internal service implements a `/health` endpoint
            resp = await service_client.get(service_name, "/health")
            if resp.status_code == 200:
                health["microservices"][service_name] = "up"
            else:
                health["microservices"][service_name] = f"down ({resp.status_code})"
                health["status"] = "degraded"
        except httpx.RequestError as e:
            logger.error(f"Microservice '{service_name}' health check failed: {e}")
            health["microservices"][service_name] = "down"
            health["status"] = "degraded"

    return health
