import json
import redis
from fastapi import APIRouter, HTTPException
from ..config import settings

router = APIRouter(prefix="/weather", tags=["Weather"])

@router.get("/")
async def get_current_weather():
    """
    Retrieves the latest weather snapshot from the Redis/ElastiCache cache.
    """
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            ssl=settings.REDIS_SSL,
            ssl_cert_reqs=None,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5
        )
        
        weather_data = r.get("weather:latest")
        if not weather_data:
            return {"status": "success", "data": None, "message": "No weather data found in cache"}
            
        return {"status": "success", "data": json.loads(weather_data)}
        
    except redis.ConnectionError as exc:
        raise HTTPException(status_code=503, detail=f"Failed to connect to weather cache: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {exc}") from exc
