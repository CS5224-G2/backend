import json
import logging
import redis
from fastapi import APIRouter, HTTPException
from ..clients.redis import redis_client

router = APIRouter(prefix="/weather", tags=["Weather"])
logger = logging.getLogger(__name__)

@router.get("/")
async def get_current_weather():
    """
    Retrieves the latest weather snapshot from the Redis/ElastiCache cache.
    """
    try:
        weather_data = redis_client.get("weather:latest")
        if not weather_data:
            return {"status": "success", "data": None, "message": "No weather data found in cache"}
            
        return {"status": "success", "data": json.loads(weather_data)}
        
    except (redis.ConnectionError, redis.TimeoutError) as exc:
        logger.error("Redis connection/timeout error: %s", exc)
        raise HTTPException(status_code=503, detail=f"Failed to connect to weather cache: {exc}") from exc
    except Exception as exc:
        logger.error("Unexpected error in get_current_weather: %s", exc)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {exc}") from exc
