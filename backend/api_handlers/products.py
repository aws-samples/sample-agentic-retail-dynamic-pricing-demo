"""Lambda handler for product catalog endpoints (public, no auth).

Handles:
- GET /products: List all products in the catalog
- GET /products/{id}: Get a single product detail
"""

import json
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

import boto3

try:
    from log_config import configure_logging
except ImportError:
    from backend.api_handlers.log_config import configure_logging

logger = configure_logging(__name__)

PRODUCTS_TABLE = os.environ.get("PRODUCTS_TABLE", "Products")


def _get_dynamodb_table():
    """Get DynamoDB table resource."""
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(PRODUCTS_TABLE)


def _decimal_to_float(obj: Any) -> Any:
    """Recursively convert Decimal values to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_decimal_to_float(item) for item in obj]
    return obj


def _is_recently_updated(price_updated_at: str | None) -> bool:
    """Check if a product's price was updated within the last 24 hours."""
    if not price_updated_at:
        return False
    try:
        updated_time = datetime.fromisoformat(price_updated_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - updated_time) < timedelta(hours=24)
    except (ValueError, TypeError):
        return False


def _enrich_product(item: dict[str, Any]) -> dict[str, Any]:
    """Add recentlyUpdated indicator and convert Decimal values."""
    product = _decimal_to_float(item)
    product["recentlyUpdated"] = _is_recently_updated(product.get("priceUpdatedAt"))
    return product


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for product catalog endpoints."""
    http_method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_params = event.get("pathParameters") or {}

    logger.info("Products handler: %s %s", http_method, path)

    try:
        if http_method == "GET" and path_params.get("id"):
            product_id = path_params["id"]
            return _get_product(product_id)
        elif http_method == "GET" and "/products" in path and not path_params.get("id"):
            return _list_products()
        else:
            return _response(404, {"error": "Not found"})
    except Exception as e:
        logger.exception("Error handling request")
        return _response(500, {"error": str(e)})


def _list_products() -> dict[str, Any]:
    """Handle GET /products - list all products."""
    table = _get_dynamodb_table()
    response = table.scan()
    items = response.get("Items", [])

    # Handle pagination for large tables
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    products = [_enrich_product(item) for item in items]

    return _response(200, {
        "products": products,
        "count": len(products),
    })


def _get_product(product_id: str) -> dict[str, Any]:
    """Handle GET /products/{id} - get single product detail."""
    table = _get_dynamodb_table()
    response = table.get_item(Key={"productId": product_id})

    item = response.get("Item")
    if not item:
        return _response(404, {"error": f"Product not found: {product_id}"})

    product = _enrich_product(item)
    return _response(200, product)


def _response(status_code: int, body: dict) -> dict[str, Any]:
    """Build API Gateway proxy response with cache headers for storefront."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            # Cache product data for 30 seconds — balances freshness with performance
            # Prices update within 60s of approval; 30s cache is acceptable
            "Cache-Control": "public, max-age=30, stale-while-revalidate=60",
        },
        "body": json.dumps(body),
    }
