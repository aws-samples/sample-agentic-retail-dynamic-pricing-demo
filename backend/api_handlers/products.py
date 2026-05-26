"""Lambda handler for product catalog endpoints (public, no auth).

Handles:
- GET /products: List all products in the catalog
- GET /products/{id}: Get a single product detail
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PRODUCTS_TABLE = os.environ.get("PRODUCTS_TABLE", "Products")


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
        elif http_method == "GET" and path == "/products":
            return _list_products()
        else:
            return _response(404, {"error": "Not found"})
    except Exception as e:
        logger.exception("Error handling request")
        return _response(500, {"error": str(e)})


def _list_products() -> dict[str, Any]:
    """Handle GET /products - list all products."""
    # TODO: Scan Products DynamoDB table
    return _response(200, {
        "products": [],
        "count": 0,
    })


def _get_product(product_id: str) -> dict[str, Any]:
    """Handle GET /products/{id} - get single product detail."""
    # TODO: Query Products DynamoDB table by productId
    return _response(200, {
        "productId": product_id,
        "name": "",
        "description": "",
        "imageUrl": "",
        "category": "",
        "currentPrice": 0.0,
        "previousPrice": 0.0,
        "priceUpdatedAt": None,
    })


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
