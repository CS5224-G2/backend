import logging
import redis
import ssl
from ..config import settings

logger = logging.getLogger(__name__)

# Single Redis client with connection pooling
# Note: For FastAPI/async usage, redis-py 5.x supports redis.asyncio. Redis() 
# here defaults to the standard connection pool.
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    ssl=settings.REDIS_SSL,
    ssl_cert_reqs=ssl.CERT_NONE,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
    # Standard connection pooling is enabled by default in redis-py
    retry_on_timeout=True
)

def get_redis_client():
    """Returns the global Redis client instance."""
    return redis_client
