"""Lambda handler for operational metrics endpoint.

Handles:
- GET /metrics: Returns CloudWatch metrics for the Ops dashboard

Queries CloudWatch for Lambda invocations, errors, DynamoDB capacity,
and API Gateway latency over the last 24 hours.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any

import boto3

try:
    from log_config import configure_logging
except ImportError:
    from backend.api_handlers.log_config import configure_logging

logger = configure_logging(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for operational metrics."""
    logger.info("Metrics handler invoked")

    try:
        metrics = _get_operational_metrics()
        return _response(200, metrics)
    except Exception as e:
        logger.exception("Error fetching metrics")
        return _response(500, {"error": "Failed to fetch metrics"})


def _get_operational_metrics() -> dict[str, Any]:
    """Query CloudWatch for operational metrics over the last 24 hours."""
    cw = boto3.client("cloudwatch", region_name=AWS_REGION)
    dynamodb = boto3.client("dynamodb", region_name=AWS_REGION)

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=24)

    lambda_invocations = _get_metric_sum(
        cw, "AWS/Lambda", "Invocations",
        [{"Name": "FunctionName", "Value": "rdp-api-pricing-cycles"}],
        start_time, end_time,
    )

    lambda_errors = _get_metric_sum(
        cw, "AWS/Lambda", "Errors",
        [{"Name": "FunctionName", "Value": "rdp-api-pricing-cycles"}],
        start_time, end_time,
    )

    lambda_duration_p90 = _get_metric_stat(
        cw, "AWS/Lambda", "Duration",
        [{"Name": "FunctionName", "Value": "rdp-api-pricing-cycles"}],
        start_time, end_time,
        stat="p90",
    )

    api_requests = _get_metric_sum(
        cw, "AWS/ApiGateway", "Count",
        [{"Name": "ApiName", "Value": "retail-dynamic-pricing-api"}],
        start_time, end_time,
    )

    api_5xx = _get_metric_sum(
        cw, "AWS/ApiGateway", "5XXError",
        [{"Name": "ApiName", "Value": "retail-dynamic-pricing-api"}],
        start_time, end_time,
    )

    api_latency_p90 = _get_metric_stat(
        cw, "AWS/ApiGateway", "Latency",
        [{"Name": "ApiName", "Value": "retail-dynamic-pricing-api"}],
        start_time, end_time,
        stat="p90",
    )

    dynamo_reads = _get_metric_sum(
        cw, "AWS/DynamoDB", "ConsumedReadCapacityUnits",
        [{"Name": "TableName", "Value": "Products"}],
        start_time, end_time,
    )

    dynamo_writes = _get_metric_sum(
        cw, "AWS/DynamoDB", "ConsumedWriteCapacityUnits",
        [{"Name": "TableName", "Value": "PricingCycles"}],
        start_time, end_time,
    )

    try:
        scan_result = dynamodb.scan(
            TableName="PricingCycles",
            Select="COUNT",
        )
        total_cycles = scan_result.get("Count", 0)
    except Exception:
        total_cycles = 0

    error_rate = 0.0
    if lambda_invocations > 0:
        error_rate = round((lambda_errors / lambda_invocations) * 100, 2)

    return {
        "period": "Last 24 hours",
        "timestamp": end_time.isoformat(),
        "lambda": {
            "invocations": int(lambda_invocations),
            "errors": int(lambda_errors),
            "errorRate": error_rate,
            "durationP90Ms": round(lambda_duration_p90, 1),
        },
        "apiGateway": {
            "requests": int(api_requests),
            "errors5xx": int(api_5xx),
            "latencyP90Ms": round(api_latency_p90, 1),
        },
        "dynamodb": {
            "readUnits": int(dynamo_reads),
            "writeUnits": int(dynamo_writes),
        },
        "business": {
            "totalCycles": total_cycles,
            "scenariosGenerated": total_cycles * 3,
        },
    }


def _get_metric_sum(
    cw, namespace: str, metric_name: str,
    dimensions: list[dict], start_time: datetime, end_time: datetime,
) -> float:
    """Get the sum of a CloudWatch metric over the time period."""
    try:
        response = cw.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=86400,
            Statistics=["Sum"],
        )
        datapoints = response.get("Datapoints", [])
        if datapoints:
            return datapoints[0].get("Sum", 0)
        return 0
    except Exception:
        return 0


def _get_metric_stat(
    cw, namespace: str, metric_name: str,
    dimensions: list[dict], start_time: datetime, end_time: datetime,
    stat: str = "p90",
) -> float:
    """Get an extended statistic (p50, p90, p99) for a CloudWatch metric."""
    try:
        response = cw.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=86400,
            ExtendedStatistics=[stat],
        )
        datapoints = response.get("Datapoints", [])
        if datapoints:
            return datapoints[0].get("ExtendedStatistics", {}).get(stat, 0)
        return 0
    except Exception:
        return 0


def _response(status_code: int, body: dict) -> dict[str, Any]:
    """Build API Gateway proxy response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
