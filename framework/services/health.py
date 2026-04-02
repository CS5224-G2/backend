import logging
import asyncio
import boto3
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pymongo.asynchronous.database import AsyncDatabase
from botocore.exceptions import BotoCoreError, ClientError

from ..config import settings
from ..clients.http import service_client
from ..clients.redis import redis_client

logger = logging.getLogger(__name__)


async def _check_postgresql(db_session: AsyncSession) -> str:
    """Helper to check Postgres availability."""
    try:
        await db_session.execute(text("SELECT 1"))
        return "up"
    except Exception as e:
        logger.error("Postgres health check failed: %s", e)
        return "down"


async def _check_mongodb(mongo_db: AsyncDatabase) -> str:
    """Helper to check MongoDB connectivity."""
    try:
        await mongo_db.command("ping")
        return "up"
    except Exception as e:
        logger.error("MongoDB health check failed: %s", e)
        return "down"


async def _check_redis() -> str:
    """Helper to check Redis connectivity (synchronous check in thread)."""
    try:
        await asyncio.to_thread(redis_client.ping)
        return "up"
    except Exception as e:
        logger.error("Redis health check failed: %s", e)
        return "down"


async def _check_external_services() -> tuple[dict, str]:
    """Helper to ping all registered external microservices."""
    service_status = {}
    overall_reachability = "up"
    
    for service_name in settings.SERVICE_URLS.keys():
        try:
            resp = await service_client.get(service_name, "/health")
            if resp.status_code == 200:
                service_status[service_name] = "up"
            else:
                service_status[service_name] = f"down ({resp.status_code})"
                overall_reachability = "degraded"
        except (httpx.RequestError, Exception) as e:
            logger.error("Microservice '%s' health check failed: %s", service_name, e)
            service_status[service_name] = "down"
            overall_reachability = "degraded"
            
    return service_status, overall_reachability


async def _check_ecs_status() -> tuple[dict, str]:
    """Helper to check ECS service health status."""
    infra_status = {}
    overall_infra = "up"
    
    try:
        def fetch_ecs_status():
            cw_ecs = boto3.client("ecs", region_name=settings.AWS_REGION)
            cluster = f"cyclelink-{settings.ENVIRONMENT}-cluster"
            services = [
                f"cyclelink-{settings.ENVIRONMENT}-backend",
                f"cyclelink-{settings.ENVIRONMENT}-bike-route"
            ]
            return cw_ecs.describe_services(cluster=cluster, services=services)

        res = await asyncio.to_thread(fetch_ecs_status)
        
        if not res.get("services"):
            return {"ecs": "down"}, "degraded"

        for svc in res.get("services", []):
            name = svc["serviceName"]
            is_up = svc["status"] == "ACTIVE" and svc.get("runningCount", 0) >= svc.get("desiredCount", 1)
            infra_status[name] = "up" if is_up else "degraded"
            if not is_up:
                overall_infra = "degraded"
                
    except (BotoCoreError, ClientError, Exception) as e:
        logger.error("ECS health check failed: %s", e)
        infra_status["ecs_cluster"] = "down"
        overall_infra = "degraded"
        
    return infra_status, overall_infra


async def get_system_health(places_db: AsyncSession, mongo_db: AsyncDatabase) -> dict:
    """
    Orchestrator to ping all dependencies and return a unified health status.
    """
    # 1. Run Postgres check immediately
    postgres_status = await _check_postgresql(places_db)
    
    # 2. Parallelize everything else
    results = await asyncio.gather(
        _check_mongodb(mongo_db),
        _check_redis(),
        _check_external_services(),
        _check_ecs_status()
    )
    
    mongo_status, redis_status, (ext_services, ext_overall), (ecs_services, ecs_overall) = results

    # 3. Consolidate into a single 'services' dict
    unified_services = {**ext_services, **ecs_services}

    # 4. Assemble the final health object
    health = {
        "status": "healthy",
        "dependencies": {
            "postgresql": postgres_status,
            "mongodb": mongo_status,
            "redis": redis_status
        },
        "services": unified_services
    }

    # 5. Global status check
    if any(s != "up" for s in [postgres_status, mongo_status, redis_status, ext_overall, ecs_overall]):
        health["status"] = "degraded"

    return health
