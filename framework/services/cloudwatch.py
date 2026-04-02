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
    start_time = end_time - timedelta(hours=24)

    try:
        # Run Boto3 synchronously in a thread threadpool to avoid blocking event loop
        def fetch_metrics():
            cw = _get_cloudwatch_client()
            # --- 1. ECS CPU/Memory ---
            for service in services:
                res[service] = {"CPUUtilization": [], "MemoryUtilization": []}
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
                        Period=900, # 15 min intervals for 24h
                        Statistics=["Average"]
                    )
                    
                    datapoints = response.get("Datapoints", [])
                    datapoints.sort(key=lambda x: x["Timestamp"])
                    
                    for dp in datapoints:
                        res[service][metric_name].append({
                            "timestamp": dp["Timestamp"].isoformat(),
                            "value": round(dp["Average"], 2)
                        })
            
            # --- 2. ELB Metrics ---
            res["alb"] = {"RequestCount": [], "TargetResponseTime": [], "HTTPCode_5XX": []}
            try:
                elbv2 = boto3.client('elbv2', region_name=settings.AWS_REGION)
                albs = elbv2.describe_load_balancers(Names=[f"cyclelink-{settings.ENVIRONMENT}-alb"])
                alb_arn = albs['LoadBalancers'][0]['LoadBalancerArn']
                alb_dim = alb_arn.split("loadbalancer/")[1]
                
                tgs = elbv2.describe_target_groups(LoadBalancerArn=alb_arn)
                # Filter for the backend tg (port 8000) or just take the first
                tg_dim = tgs['TargetGroups'][0]['TargetGroupArn'].split(":")[-1]
                
                # RequestCount
                resp_rc = cw.get_metric_statistics(
                    Namespace="AWS/ApplicationELB", MetricName="RequestCount",
                    Dimensions=[{"Name": "LoadBalancer", "Value": alb_dim}],
                    StartTime=start_time, EndTime=end_time, Period=900, Statistics=["Sum"]
                )
                for dp in sorted(resp_rc.get("Datapoints", []), key=lambda x: x["Timestamp"]):
                    res["alb"]["RequestCount"].append({"timestamp": dp["Timestamp"].isoformat(), "value": dp["Sum"]})
                
                # ELB 5xx Errors
                resp_5xx = cw.get_metric_statistics(
                    Namespace="AWS/ApplicationELB", MetricName="HTTPCode_ELB_5XX_Count",
                    Dimensions=[{"Name": "LoadBalancer", "Value": alb_dim}],
                    StartTime=start_time, EndTime=end_time, Period=900, Statistics=["Sum"]
                )
                for dp in sorted(resp_5xx.get("Datapoints", []), key=lambda x: x["Timestamp"]):
                    res["alb"]["HTTPCode_5XX"].append({"timestamp": dp["Timestamp"].isoformat(), "value": dp["Sum"]})
                    
                # TargetResponseTime
                resp_lt = cw.get_metric_statistics(
                    Namespace="AWS/ApplicationELB", MetricName="TargetResponseTime",
                    Dimensions=[{"Name": "LoadBalancer", "Value": alb_dim}, {"Name": "TargetGroup", "Value": tg_dim}],
                    StartTime=start_time, EndTime=end_time, Period=900, Statistics=["Average"]
                )
                for dp in sorted(resp_lt.get("Datapoints", []), key=lambda x: x["Timestamp"]):
                    res["alb"]["TargetResponseTime"].append({"timestamp": dp["Timestamp"].isoformat(), "value": round(dp["Average"] * 1000, 2)}) # ms
            except Exception as e:
                logger.error(f"Failed to fetch ALB metrics: {e}")
                
            return res

        metrics = await asyncio.to_thread(fetch_metrics)
        
        # Save to cache
        try:
            await asyncio.to_thread(redis_client.setex, cache_key, 300, json.dumps(metrics))
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")
            
    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to fetch CloudWatch metrics: {e}")
        return {}

    return metrics


async def get_recent_error_logs() -> dict:
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
                    key = field['field'].lstrip('@')
                    if key != 'ptr':
                        item[key] = field['value']
                parsed_results.append(item)
                
            return {
                "total_errors": int(response.get("statistics", {}).get("recordsMatched", len(parsed_results))),
                "errors": parsed_results,
                "period_hours": 24,
                "limit_applied": 50
            }

        results = await asyncio.to_thread(fetch_logs)
        
        try:
            await asyncio.to_thread(redis_client.setex, cache_key, 60, json.dumps(results))
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")
            
        return results
        
    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to query CloudWatch logs: {e}")
        return {"total_errors": 0, "errors": [], "period_hours": 24, "limit_applied": 50}
