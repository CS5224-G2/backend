import json
import logging
import os
import redis
import ssl

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def pusher_handler(event, _context):
    """
    Entry point for the INSIDE VPC Lambda.
    Receives processed weather data and pushes it to ElastiCache.
    """
    logger.info("Pusher event received")
    
    endpoint = os.environ.get("ELASTICACHE_ENDPOINT")
    port = os.environ.get("ELASTICACHE_PORT", "6379")

    if not endpoint:
        logger.error("ELASTICACHE_ENDPOINT not set")
        return

    try:
        # Event is the processed weather data sent from fetch-weather Lambda
        # Using socket_timeout=5 and bypassing SSL validation to avoid hangs in public subnets without NAT
        r = redis.Redis(
            host=endpoint,
            port=int(port),
            ssl=True,
            ssl_cert_reqs=ssl.CERT_NONE,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5
        )
        r.set("weather:latest", json.dumps(event), ex=900)
        logger.info("Successfully pushed weather data to ElastiCache")
    except Exception as exc:
        logger.error("Failed to push to ElastiCache: %s", exc)
