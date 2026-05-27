"""Seed script to populate the Products DynamoDB table with sample retail products.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/seed_products.py
    PYTHONPATH=. .venv/bin/python scripts/seed_products.py --local

The --local flag uses a local DynamoDB instance at http://localhost:8000.

Validates: Requirements 6.1
"""

import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3

TABLE_NAME = "Products"

DEMO_PRODUCTS: list[dict[str, Any]] = [
    # ─── Electronics ───────────────────────────────────────────────────────────
    {
        "productId": "prod-elec-001",
        "name": "ProSound Wireless Earbuds",
        "description": "Active noise-cancelling true wireless earbuds with 8-hour battery life and IPX5 water resistance.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Wireless+Earbuds",
        "category": "Electronics",
        "subCategory": "Audio",
        "productFamily": "ProSound Audio",
        "currentPrice": 79.99,
        "previousPrice": 89.99,
        "priceUpdatedAt": "2024-12-01T10:00:00Z",
        "totalUnitCost": 48.00,
        "mapPrice": 69.99,
        "channels": ["online", "retail_store", "marketplace"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    {
        "productId": "prod-elec-002",
        "name": "SoundWave Portable Bluetooth Speaker",
        "description": "360-degree sound portable speaker with 12-hour playtime and rugged waterproof design.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=BT+Speaker",
        "category": "Electronics",
        "subCategory": "Audio",
        "productFamily": "SoundWave Audio",
        "currentPrice": 49.99,
        "previousPrice": 54.99,
        "priceUpdatedAt": "2024-11-28T14:30:00Z",
        "totalUnitCost": 30.00,
        "mapPrice": 44.99,
        "channels": ["online", "retail_store", "marketplace"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    {
        "productId": "prod-elec-003",
        "name": "FitTrack Pro Smartwatch",
        "description": "Advanced fitness smartwatch with heart rate monitoring, GPS, and 5-day battery life.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Smartwatch",
        "category": "Electronics",
        "subCategory": "Wearables",
        "productFamily": "FitTrack Wearables",
        "currentPrice": 199.99,
        "previousPrice": 219.99,
        "priceUpdatedAt": "2024-11-15T09:00:00Z",
        "totalUnitCost": 120.00,
        "mapPrice": 179.99,
        "channels": ["online", "retail_store"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    {
        "productId": "prod-elec-004",
        "name": "TabletX 10-inch Display",
        "description": "10.1-inch HD tablet with 64GB storage, quad-core processor, and all-day battery.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Tablet+10in",
        "category": "Electronics",
        "subCategory": "Tablets",
        "productFamily": "TabletX Computing",
        "currentPrice": 249.99,
        "previousPrice": 279.99,
        "priceUpdatedAt": "2024-11-20T16:00:00Z",
        "totalUnitCost": 155.00,
        "mapPrice": 229.99,
        "channels": ["online", "marketplace"],
        "regions": ["us-east", "us-west"],
    },
    {
        "productId": "prod-elec-005",
        "name": "StudioMax Over-Ear Headphones",
        "description": "Premium over-ear headphones with adaptive noise cancellation and 30-hour battery.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Headphones",
        "category": "Electronics",
        "subCategory": "Audio",
        "productFamily": "StudioMax Audio",
        "currentPrice": 149.99,
        "previousPrice": 149.99,
        "priceUpdatedAt": "2024-10-01T08:00:00Z",
        "totalUnitCost": 90.00,
        "mapPrice": 129.99,
        "channels": ["online", "retail_store", "marketplace"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    {
        "productId": "prod-elec-006",
        "name": "QuickCharge USB-C Power Bank",
        "description": "20000mAh portable charger with 65W USB-C fast charging and dual output ports.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Power+Bank",
        "category": "Electronics",
        "subCategory": "Accessories",
        "productFamily": "QuickCharge Power",
        "currentPrice": 39.99,
        "previousPrice": 44.99,
        "priceUpdatedAt": "2024-12-05T11:00:00Z",
        "totalUnitCost": 24.00,
        "mapPrice": None,
        "channels": ["online", "marketplace"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    # ─── Grocery ───────────────────────────────────────────────────────────────
    {
        "productId": "prod-groc-001",
        "name": "Farm Fresh Whole Milk (1 Gallon)",
        "description": "Grade A pasteurized whole milk from local dairy farms, vitamin D fortified.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Whole+Milk",
        "category": "Grocery",
        "subCategory": "Dairy",
        "productFamily": "Farm Fresh Dairy",
        "currentPrice": 4.49,
        "previousPrice": 3.99,
        "priceUpdatedAt": "2024-12-10T06:00:00Z",
        "totalUnitCost": 2.80,
        "mapPrice": None,
        "channels": ["retail_store"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    {
        "productId": "prod-groc-002",
        "name": "Mountain Roast Premium Coffee (12 oz)",
        "description": "Single-origin medium roast Arabica coffee beans, ethically sourced from Colombia.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Coffee+Beans",
        "category": "Grocery",
        "subCategory": "Beverages",
        "productFamily": "Mountain Roast Coffee",
        "currentPrice": 12.99,
        "previousPrice": 11.99,
        "priceUpdatedAt": "2024-12-08T07:00:00Z",
        "totalUnitCost": 7.80,
        "mapPrice": None,
        "channels": ["online", "retail_store", "marketplace"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    {
        "productId": "prod-groc-003",
        "name": "Artisan Sourdough Bread Loaf",
        "description": "Freshly baked sourdough bread with a crispy crust and soft interior, no preservatives.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Sourdough+Bread",
        "category": "Grocery",
        "subCategory": "Bakery",
        "productFamily": "Artisan Bakery",
        "currentPrice": 5.99,
        "previousPrice": 5.49,
        "priceUpdatedAt": "2024-12-12T05:30:00Z",
        "totalUnitCost": 3.20,
        "mapPrice": None,
        "channels": ["retail_store"],
        "regions": ["us-east", "us-central"],
    },
    {
        "productId": "prod-groc-004",
        "name": "Greek Style Yogurt Variety Pack (6 ct)",
        "description": "Low-fat Greek yogurt cups in strawberry, blueberry, and vanilla flavors.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Greek+Yogurt",
        "category": "Grocery",
        "subCategory": "Dairy",
        "productFamily": "Farm Fresh Dairy",
        "currentPrice": 6.49,
        "previousPrice": 5.99,
        "priceUpdatedAt": "2024-12-09T08:00:00Z",
        "totalUnitCost": 3.90,
        "mapPrice": None,
        "channels": ["retail_store", "online"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    {
        "productId": "prod-groc-005",
        "name": "Free Range Large Eggs (Dozen)",
        "description": "USDA Grade AA free-range eggs from cage-free hens, naturally rich in omega-3.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Free+Range+Eggs",
        "category": "Grocery",
        "subCategory": "Dairy",
        "productFamily": "Farm Fresh Dairy",
        "currentPrice": 5.29,
        "previousPrice": 4.79,
        "priceUpdatedAt": "2024-12-11T06:30:00Z",
        "totalUnitCost": 3.40,
        "mapPrice": None,
        "channels": ["retail_store"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    {
        "productId": "prod-groc-006",
        "name": "Organic Green Tea (20 bags)",
        "description": "Premium Japanese sencha green tea bags, individually wrapped for freshness.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Green+Tea",
        "category": "Grocery",
        "subCategory": "Beverages",
        "productFamily": "Mountain Roast Coffee",
        "currentPrice": 7.99,
        "previousPrice": 7.49,
        "priceUpdatedAt": "2024-12-06T09:00:00Z",
        "totalUnitCost": 4.50,
        "mapPrice": None,
        "channels": ["online", "retail_store"],
        "regions": ["us-east", "us-west"],
    },
    # ─── Home & Garden ─────────────────────────────────────────────────────────
    {
        "productId": "prod-home-001",
        "name": "LumiGlow Smart LED Floor Lamp",
        "description": "Dimmable smart floor lamp with color temperature control and voice assistant compatibility.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=LED+Lamp",
        "category": "Home & Garden",
        "subCategory": "Lighting",
        "productFamily": "LumiGlow Smart Home",
        "currentPrice": 89.99,
        "previousPrice": 99.99,
        "priceUpdatedAt": "2024-11-25T12:00:00Z",
        "totalUnitCost": 54.00,
        "mapPrice": 79.99,
        "channels": ["online", "retail_store", "marketplace"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    {
        "productId": "prod-home-002",
        "name": "CleanForce Cordless Stick Vacuum",
        "description": "Lightweight cordless vacuum with HEPA filtration, 45-minute runtime, and wall mount.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Stick+Vacuum",
        "category": "Home & Garden",
        "subCategory": "Cleaning",
        "productFamily": "CleanForce Appliances",
        "currentPrice": 299.99,
        "previousPrice": 349.99,
        "priceUpdatedAt": "2024-11-22T10:00:00Z",
        "totalUnitCost": 180.00,
        "mapPrice": 269.99,
        "channels": ["online", "retail_store"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    {
        "productId": "prod-home-003",
        "name": "PureAir HEPA Air Purifier",
        "description": "True HEPA air purifier for rooms up to 500 sq ft with auto air quality sensor.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Air+Purifier",
        "category": "Home & Garden",
        "subCategory": "Air Quality",
        "productFamily": "PureAir Home",
        "currentPrice": 179.99,
        "previousPrice": 199.99,
        "priceUpdatedAt": "2024-11-18T14:00:00Z",
        "totalUnitCost": 108.00,
        "mapPrice": 159.99,
        "channels": ["online", "retail_store", "marketplace"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    {
        "productId": "prod-home-004",
        "name": "EcoTemp Smart Thermostat",
        "description": "Wi-Fi enabled programmable thermostat with energy usage reports and geofencing.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Smart+Thermostat",
        "category": "Home & Garden",
        "subCategory": "Climate Control",
        "productFamily": "EcoTemp Smart Home",
        "currentPrice": 129.99,
        "previousPrice": 139.99,
        "priceUpdatedAt": "2024-11-30T09:00:00Z",
        "totalUnitCost": 78.00,
        "mapPrice": 119.99,
        "channels": ["online", "retail_store"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    {
        "productId": "prod-home-005",
        "name": "PowerDrill 20V Cordless Drill Kit",
        "description": "20V lithium-ion cordless drill with 2 batteries, charger, and 30-piece bit set.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Cordless+Drill",
        "category": "Home & Garden",
        "subCategory": "Tools",
        "productFamily": "PowerDrill Tools",
        "currentPrice": 119.99,
        "previousPrice": 129.99,
        "priceUpdatedAt": "2024-12-02T11:00:00Z",
        "totalUnitCost": 72.00,
        "mapPrice": 99.99,
        "channels": ["online", "retail_store", "marketplace"],
        "regions": ["us-east", "us-west", "us-central"],
    },
    {
        "productId": "prod-home-006",
        "name": "GardenPro Automatic Sprinkler Timer",
        "description": "6-zone programmable sprinkler controller with rain sensor and smartphone app.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Sprinkler+Timer",
        "category": "Home & Garden",
        "subCategory": "Garden",
        "productFamily": "GardenPro Outdoor",
        "currentPrice": 59.99,
        "previousPrice": 64.99,
        "priceUpdatedAt": "2024-11-10T08:00:00Z",
        "totalUnitCost": 36.00,
        "mapPrice": None,
        "channels": ["online", "retail_store"],
        "regions": ["us-east", "us-west"],
    },
    {
        "productId": "prod-home-007",
        "name": "ComfortPlus Memory Foam Pillow (2-Pack)",
        "description": "Cooling gel-infused memory foam pillows with removable bamboo covers.",
        "imageUrl": "https://placehold.co/400x400/EEE/333?text=Memory+Foam+Pillow",
        "category": "Home & Garden",
        "subCategory": "Bedding",
        "productFamily": "ComfortPlus Sleep",
        "currentPrice": 44.99,
        "previousPrice": 49.99,
        "priceUpdatedAt": "2024-12-03T13:00:00Z",
        "totalUnitCost": 27.00,
        "mapPrice": None,
        "channels": ["online", "marketplace"],
        "regions": ["us-east", "us-west", "us-central"],
    },
]


def _convert_to_dynamodb_item(product: dict[str, Any]) -> dict[str, Any]:
    """Convert a product dict to DynamoDB item format."""
    item: dict[str, Any] = {}
    for key, value in product.items():
        if value is None:
            # Skip None values (DynamoDB doesn't store nulls well with resource API)
            continue
        elif isinstance(value, str):
            item[key] = value
        elif isinstance(value, (int, float)):
            item[key] = Decimal(str(value))
        elif isinstance(value, list):
            item[key] = value
        else:
            item[key] = value
    return item


def seed_products(local: bool = False) -> None:
    """Seed the Products DynamoDB table with demo data.

    Args:
        local: If True, connect to local DynamoDB at http://localhost:8000.
    """
    if local:
        dynamodb = boto3.resource(
            "dynamodb",
            endpoint_url="http://localhost:8000",
            region_name="us-east-1",
            aws_access_key_id="local",
            aws_secret_access_key="local",
        )
    else:
        dynamodb = boto3.resource("dynamodb")

    table = dynamodb.Table(TABLE_NAME)

    print(f"Seeding {len(DEMO_PRODUCTS)} products into '{TABLE_NAME}' table...")

    for i, product in enumerate(DEMO_PRODUCTS, 1):
        item = _convert_to_dynamodb_item(product)
        table.put_item(Item=item)
        print(f"  [{i}/{len(DEMO_PRODUCTS)}] {product['name']} (${product['currentPrice']:.2f})")

    print(f"\nDone! {len(DEMO_PRODUCTS)} products seeded successfully.")
    _print_summary()


def _print_summary() -> None:
    """Print a summary of seeded products by category."""
    categories: dict[str, int] = {}
    for product in DEMO_PRODUCTS:
        cat = product["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print("\nSummary by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count} products")

    price_range = (
        min(p["currentPrice"] for p in DEMO_PRODUCTS),
        max(p["currentPrice"] for p in DEMO_PRODUCTS),
    )
    print(f"\nPrice range: ${price_range[0]:.2f} - ${price_range[1]:.2f}")

    map_count = sum(1 for p in DEMO_PRODUCTS if p["mapPrice"] is not None)
    print(f"Products with MAP price: {map_count}/{len(DEMO_PRODUCTS)}")


def main() -> None:
    """Main entry point for the seed script."""
    parser = argparse.ArgumentParser(
        description="Seed the Products DynamoDB table with demo retail products."
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local DynamoDB instance at http://localhost:8000",
    )
    args = parser.parse_args()

    try:
        seed_products(local=args.local)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        print(
            "Make sure the Products table exists and AWS credentials are configured.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
