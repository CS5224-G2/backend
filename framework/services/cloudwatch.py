import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ..config import settings
from ..clients.redis import redis_client

logger = logging.getLogger(__name__)

def _get_cloudwatch_client():
    return boto3.client("cloudwatch", region_name=settings.AWS_REGION)

def _get_logs_client():
    return boto3.client("logs", region_name=settings.AWS_REGION)

async def get_infrastructure_metrics() -> dict:
    """
    Fetch CPU and Memory Utilization for Backend and Bike-Route ECS Services.
    Results are cached in Redis for 5 minutes to avoid AWS API throttling.
    """
    cache_key = "infra:metrics:ecs"
    
    try:
        cached = await asyncio.to_thread(redis_client.get, cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis cache read failed, falling back to AWS: {e}")

    # Not cached, fetch from AWS
    cluster_name = f"cyclelink-{settings.ENVIRONMENT}-cluster"
    services = [
        f"cyclelink-{settings.ENVIRONMENT}-backend",
        f"cyclelink-{settings.ENVIRONMENT}-bike-route"
    ]

    metrics = {}
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=1)

    try:
        # Run Boto3 synchronously in a thread threadpool to avoid blocking event loop
        def fetch_metrics():
            cw = _get_cloudwatch_client()
            res = {}
            for service in services:
                res[service] = {}
                for metric_name in ["CPUUtilization", "MemoryUtilization"]:
                    response = cw.get_metric_statistics(
                        Namespace="AWS/ECS",
                        MetricName=metric_name,
                        Dimensions=[
                            {"Name": "ClusterName", "Value": cluster_name},
                            {"Name": "ServiceName", "Value": service},
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=300, # 5 min intervals
                        Statistics=["Average"]
                    )
                    
                    datapoints = response.get("Datapoints", [])
                    # Sort desc by timestamp to get latest
                    datapoints.sort(key=lambda x: x["Timestamp"], reverse=True)
                    
                    latest_val = datapoints[0]["Average"] if datapoints else 0.0
                    res[service][metric_name] = round(latest_val, 2)
            return res

        metrics = await asyncio.to_thread(fetch_metrics)
        
        # Save to cache
        try:
            await asyncio.to_thread(redis_client.setex, cache_key, 300, json.dumps(metrics))
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")
            
    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to fetch CloudWatch metrics: {e}")
        # Return fallback zeros if we fail gracefully
        return {s: {"CPUUtilization": 0.0, "MemoryUtilization": 0.0} for s in services}

    return metrics


async def get_recent_error_logs() -> list[dict]:
    """
    Fetch the latest 'ERROR' logs from the backend ECS log group using CloudWatch Logs Insights.
    Cached for 1 minute.
    """
    cache_key = "infra:logs:backend_errors"
    
    try:
        cached = await asyncio.to_thread(redis_client.get, cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis cache read failed: {e}")

    log_group_name = f"/ecs/cyclelink-{settings.ENVIRONMENT}-backend"
    
    end_time = int(datetime.now(timezone.utc).timestamp())
    start_time = end_time - 86400  # Past 24 hours
    
    # Query for ERROR logs
    query = "fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 50"

    try:
        def fetch_logs():
            logs = _get_logs_client()
            start_query_response = logs.start_query(
                logGroupName=log_group_name,
                startTime=start_time,
                endTime=end_time,
                queryString=query,
            )
            query_id = start_query_response['queryId']
            
            # Simple poll
            response = {}
            while response.get('status') in (None, 'Running', 'Scheduled'):
                import time
                time.sleep(1)
                response = logs.get_query_results(queryId=query_id)
                
            parsed_results = []
            for result_row in response.get("results", []):
                item = {}
                for field in result_row:
                    item[field['field']] = field['value']
                parsed_results.append(item)
                
            return parsed_results

        results = await asyncio.to_thread(fetch_logs)
        
        try:
            await asyncio.to_thread(redis_client.setex, cache_key, 60, json.dumps(results))
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")
            
        return results
        
    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to query CloudWatch logs: {e}")
        return []
