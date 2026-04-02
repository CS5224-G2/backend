import logging
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pymongo.asynchronous.database import AsyncDatabase
import asyncio
import boto3
from botocore.exceptions import BotoCoreError, ClientError

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

    # Ping ECS
    try:
        def check_ecs():
            ecs = boto3.client("ecs", region_name=settings.AWS_REGION)
            cluster = f"cyclelink-{settings.ENVIRONMENT}-cluster"
            services = [
                f"cyclelink-{settings.ENVIRONMENT}-backend",
                f"cyclelink-{settings.ENVIRONMENT}-bike-route"
            ]
            health["infrastructure"] = {}
            res = ecs.describe_services(cluster=cluster, services=services)
            for svc in res.get("services", []):
                name = svc["serviceName"]
                # A service is fully up if it is ACTIVE and running count >= desired count
                is_up = svc["status"] == "ACTIVE" and svc.get("runningCount", 0) >= svc.get("desiredCount", 1)
                health["infrastructure"][name] = "up" if is_up else "degraded"
                if not is_up:
                    health["status"] = "degraded"
            # If services array was empty or failed
            if not res.get("services"):
                health["infrastructure"]["ecs"] = "down"
                health["status"] = "degraded"

        await asyncio.to_thread(check_ecs)
    except (BotoCoreError, ClientError, Exception) as e:
        logger.error(f"ECS health check failed: {e}")
        health["infrastructure"] = health.get("infrastructure", {})
        health["infrastructure"]["ecs"] = "down"
        health["status"] = "degraded"

    return health
