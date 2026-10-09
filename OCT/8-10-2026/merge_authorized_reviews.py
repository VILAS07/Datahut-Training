#!/usr/bin/env python3
"""Normalize an authorized review export and merge it with the 50-product catalog.

Supported input: provider/client-authorized CSV, JSON array/object, or JSONL.
Only the required review fields are written. Reviewer names and other personal
fields from source exports are deliberately discarded.

This script does not request Amazon pages or retrieve reviews itself.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

PRODUCTS_JSON_DEFAULT = Path("amazon_products_50.json")
OUT_JSON_DEFAULT = Path("amazon_reviews_50_merged.json")
OUT_CSV_DEFAULT = Path("amazon_reviews_50_merged.csv")

ALIASES = {
    "asin": ("asin", "product_asin", "productAsin", "product_id", "productId", "parent_asin", "parentAsin"),
    "product_name": ("product_name", "productName", "product_title", "productTitle", "item_name", "itemName"),
    "product_url": ("product_url", "productUrl", "url", "detail_page_url", "detailPageURL", "product_link"),
    "review_id": ("review_id", "reviewId", "id", "review_identifier", "reviewIdentifier"),
    "rating": ("rating", "review_rating", "reviewRating", "star_rating", "starRating", "stars"),
    "review_title": ("review_title", "reviewTitle", "title", "headline", "review_headline"),
    "review_text": ("review_text", "reviewText", "text", "body", "content", "review_body", "reviewBody", "review"),
    "review_date": ("review_date", "reviewDate", "date", "published_at", "publishedAt", "created_at", "createdAt", "date_published"),
    "verified_purchase": ("verified_purchase", "verifiedPurchase", "is_verified_purchase", "isVerifiedPurchase", "verified", "purchase_verified"),
    "review_date_label": ("review_date_label", "reviewDateLabel", "date_label", "dateLabel"),
}

PRODUCT_COLUMNS = [
    "asin", "product_name", "product_url", "average_rating", "total_ratings",
    "one_star_percent", "two_star_percent", "three_star_percent",
    "four_star_percent", "five_star_percent", "review_count_in_import",
]
REVIEW_COLUMNS = [
    "product_asin", "product_name", "product_url", "average_rating", "total_ratings",
    "one_star_percent", "two_star_percent", "three_star_percent",
    "four_star_percent", "five_star_percent", "review_id", "rating",
    "review_title", "review_text", "review_date", "review_date_label",
    "verified_purchase",
]


def normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def first_value(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    lookup = {normalized_key(str(k)): v for k, v in row.items()}
    for alias in aliases:
        value = lookup.get(normalized_key(alias))
        if value is not None and str(value).strip() != "":
            return value
    return None


def load_records(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return [dict(row) for row in csv.DictReader(f)]
    if suffix in (".jsonl", ".ndjson"):
        rows = []
        with path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    item = json.loads(line)
                    if isinstance(item, dict):
                        rows.append(item)
                    else:
                        raise ValueError(f"JSONL line {line_num} is not an object")
        return rows
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        # Common envelopes used by exports/APIs.
        for key in ("reviews", "results", "records", "data", "items", "customer_reviews"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        # A single record is still accepted.
        if any(normalized_key(k) in {normalized_key(a) for a in ALIASES["review_text"]} for k in data):
            return [data]
    raise ValueError("Unsupported JSON shape: expected a list or an object containing a review list")


def load_products(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected {path} to contain a JSON array of product records")
    return [x for x in data if isinstance(x, dict)]


def parse_bool(value: Any) -> bool | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, bool):
        return value
    val = str(value).strip().lower()
    if val in {"true", "yes", "y", "1", "verified", "verified purchase", "verified_purchase"}:
        return True
    if val in {"false", "no", "n", "0", "unverified", "not verified"}:
        return False
    return None


def parse_rating(value: Any) -> float | None:
    if value is None:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", str(value))
    if not match:
        return None
    try:
        rating = float(match.group(1))
    except ValueError:
        return None
    return rating if 0 <= rating <= 5 else None


def get_asin(row: dict[str, Any]) -> str | None:
    value = first_value(row, ALIASES["asin"])
    if value:
        return str(value).strip().upper()
    url = first_value(row, ALIASES["product_url"])
    if url:
        match = re.search(r"(?:/dp/|/product-reviews/|/gp/product/)([A-Z0-9]{10})", str(url), re.I)
        if match:
            return match.group(1).upper()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge an authorized review export with amazon_products_50.json")
    parser.add_argument("--input", required=True, help="Path to authorized review export (.json, .jsonl, .ndjson, or .csv)")
    parser.add_argument("--products", default=str(PRODUCTS_JSON_DEFAULT), help="Product catalog JSON path")
    parser.add_argument("--reviews-json", default=str(OUT_JSON_DEFAULT), help="Output normalized reviews JSON")
    parser.add_argument("--reviews-csv", default=str(OUT_CSV_DEFAULT), help="Output normalized reviews CSV")
    parser.add_argument("--products-csv", default="amazon_products_50_with_review_counts.csv", help="Output product CSV with imported review counts")
    args = parser.parse_args()

    source_path = Path(args.input).expanduser()
    products_path = Path(args.products).expanduser()
    if not source_path.is_file():
        print(f"ERROR: review export not found: {source_path}", file=sys.stderr)
        return 2
    if not products_path.is_file():
        print(f"ERROR: product catalog not found: {products_path}", file=sys.stderr)
        return 2

    source_rows = load_records(source_path)
    products = load_products(products_path)

    by_asin: dict[str, dict[str, Any]] = {}
    for product in products:
        asin = str(product.get("asin", "")).strip().upper()
        if asin:
            by_asin[asin] = product

    normalized_reviews: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    skipped_no_asin = 0
    skipped_no_text = 0

    for raw in source_rows:
        asin = get_asin(raw)
        if not asin:
            skipped_no_asin += 1
            continue
        # Only accept reviews for products in the current 50-product catalog.
        product = by_asin.get(asin)
        if product is None:
            continue

        review_text = first_value(raw, ALIASES["review_text"])
        if review_text is None or not str(review_text).strip():
            skipped_no_text += 1
            continue

        review_id_value = first_value(raw, ALIASES["review_id"])
        review_id = str(review_id_value).strip() if review_id_value else None
        dedupe_key = (asin, review_id) if review_id else (asin, str(review_text).strip())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        star_distribution = product.get("star_distribution") or {}
        def star_pct(n: int) -> Any:
            # Catalog output stores keys in star_distribution as "1_star_percent" etc.
            return star_distribution.get(f"{n}_star_percent")

        normalized_reviews.append({
            "product_asin": asin,
            "product_name": product.get("product_name") or first_value(raw, ALIASES["product_name"]),
            "product_url": product.get("product_url") or first_value(raw, ALIASES["product_url"]),
            "average_rating": product.get("average_rating"),
            "total_ratings": product.get("total_ratings"),
            "one_star_percent": star_pct(1),
            "two_star_percent": star_pct(2),
            "three_star_percent": star_pct(3),
            "four_star_percent": star_pct(4),
            "five_star_percent": star_pct(5),
            "review_id": review_id,
            "rating": parse_rating(first_value(raw, ALIASES["rating"])),
            "review_title": first_value(raw, ALIASES["review_title"]),
            "review_text": str(review_text).strip(),  # Keep source text unchanged; no translation.
            "review_date": first_value(raw, ALIASES["review_date"]),
            "review_date_label": first_value(raw, ALIASES["review_date_label"]),
            "verified_purchase": parse_bool(first_value(raw, ALIASES["verified_purchase"])),
        })

    # Product-level file: exact catalog data plus counts of imported reviews.
    review_counts: dict[str, int] = {}
    for review in normalized_reviews:
        review_counts[review["product_asin"]] = review_counts.get(review["product_asin"], 0) + 1

    product_rows: list[dict[str, Any]] = []
    for product in products:
        dist = product.get("star_distribution") or {}
        product_rows.append({
            "asin": product.get("asin"),
            "product_name": product.get("product_name"),
            "product_url": product.get("product_url"),
            "average_rating": product.get("average_rating"),
            "total_ratings": product.get("total_ratings"),
            "one_star_percent": dist.get("1_star_percent"),
            "two_star_percent": dist.get("2_star_percent"),
            "three_star_percent": dist.get("3_star_percent"),
            "four_star_percent": dist.get("4_star_percent"),
            "five_star_percent": dist.get("5_star_percent"),
            "review_count_in_import": review_counts.get(str(product.get("asin", "")).upper(), 0),
        })

    out_json = Path(args.reviews_json).expanduser()
    out_csv = Path(args.reviews_csv).expanduser()
    products_csv = Path(args.products_csv).expanduser()
    out_json.write_text(json.dumps(normalized_reviews, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for path, rows, columns in (
        (out_csv, normalized_reviews, REVIEW_COLUMNS),
        (products_csv, product_rows, PRODUCT_COLUMNS),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    print(f"Source records: {len(source_rows)}")
    print(f"Catalog products: {len(products)}")
    print(f"Imported matching reviews: {len(normalized_reviews)}")
    print(f"Products with imported reviews: {len(review_counts)}")
    print(f"Records skipped (no ASIN): {skipped_no_asin}")
    print(f"Records skipped (no review text): {skipped_no_text}")
    print("Reviewer names and other unrequested personal fields were not exported.")
    print(f"Reviews JSON: {out_json}")
    print(f"Reviews CSV: {out_csv}")
    print(f"Product CSV: {products_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
