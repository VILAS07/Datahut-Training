
"""
ASDA Grocery Product Ratings Collector
---------------------------------------
Collects ASDA grocery products from the public Algolia search index.

Extracts:
    Product ID, CIN, product name, brand, PDP URL,
    average rating, rating count, image ID, pack size,
    product type, category, department, aisle, shelf,
    taxonomy and price.

Requirements:
    pip install curl_cffi parsel

Run:
    python asda_ratings_crawler.py

Collect 100 grocery products:
    python asda_ratings_crawler.py --max-products 100

Collect 500 grocery products:
    python asda_ratings_crawler.py --max-products 500

Collect a specific primary category:
    python asda_ratings_crawler.py --category "Frozen Food"

Notes:
- Uses curl_cffi and parsel only.
- No Playwright.
- Uses read-only Algolia search requests.
- Filters products using grocery taxonomy.
- Request statistics measure Algolia requests.
- This script does not crawl PDP HTML or extract individual reviews.
"""

import argparse
import csv
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote

from curl_cffi import requests
from parsel import Selector


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

CATEGORY_PAGE = (
    "https://www.asda.com/groceries/chilled-food/"
    "milk-butter-cream-eggs/fresh-milk"
)

ALGOLIA_INDEX = "ASDA_PRODUCTS"

ALGOLIA_ENDPOINT_TEMPLATE = (
    "https://{app_id}-dsn.algolia.net/1/indexes/{index}/query"
)

OUTPUT_CSV = "asda_grocery_products_ratings.csv"
REQUEST_LOG_CSV = "asda_algolia_request_log.csv"
FAILED_REQUESTS_CSV = "asda_failed_requests.csv"

DEFAULT_HITS_PER_PAGE = 500
REQUEST_DELAY_SECONDS = 0.25
TIMEOUT_SECONDS = 30
MAX_RETRIES = 3


# --------------------------------------------------
# GROCERY CATEGORY FILTER
# --------------------------------------------------

GROCERY_CATEGORIES = {
    "food cupboard",
    "chilled food",
    "beer, wine & spirits",
    "drinks",
    "frozen food",
    "world food",
    "bakery",
    "meat, poultry & fish",
    "dietary & lifestyle",
    "fresh fruit, vegetables & flowers",
    "sweets, treats & snacks",
}


# --------------------------------------------------
# CSV FIELDS
# --------------------------------------------------

CSV_FIELDS = [
    "product_id",
    "cin",
    "product_name",
    "brand",
    "product_url",
    "average_rating",
    "rating_count",
    "image_id",
    "pack_size",
    "product_type",
    "display_online",
    "status",
    "primary_category",
    "primary_department",
    "primary_aisle",
    "primary_shelf",
    "page_taxonomy",
    "price_en_gbp",
    "collected_at_utc",
]


# --------------------------------------------------
# ALGOLIA CONFIGURATION
# --------------------------------------------------

def get_algolia_config(session):
    """
    Fetch the ASDA category page and read its
    frontend Algolia search configuration.
    """

    response = session.get(
        CATEGORY_PAGE,
        impersonate="chrome",
        timeout=TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    html = response.text

    app_match = re.search(
        r'"appId"\s*:\s*"([^"]+)"',
        html
    )

    key_match = re.search(
        r'"searchAPIKey"\s*:\s*"([^"]+)"',
        html
    )

    index_match = re.search(
        r'"productsIndex"\s*:\s*"([^"]+)"',
        html
    )

    if not app_match or not key_match:
        raise RuntimeError(
            "Could not find Algolia configuration."
        )

    app_id = app_match.group(1)
    api_key = key_match.group(1)

    index_name = (
        index_match.group(1)
        if index_match
        else ALGOLIA_INDEX
    )

    if not app_id or not api_key:
        raise RuntimeError(
            "Invalid Algolia configuration."
        )

    return (
        app_id,
        api_key,
        index_name,
        response.status_code,
    )


# --------------------------------------------------
# SAFE FLOAT CONVERSION
# --------------------------------------------------

def safe_float(value):
    """Convert numeric values into floats."""

    if value in (None, ""):
        return ""

    try:
        return float(value)

    except (TypeError, ValueError):
        return ""


# --------------------------------------------------
# PRODUCT ROW CONVERSION
# --------------------------------------------------

def record_to_row(hit, collected_at):
    """Convert an Algolia product hit into a CSV row."""

    taxonomy = hit.get("PRIMARY_TAXONOMY") or {}
    prices = hit.get("PRICES") or {}

    en_price = prices.get("EN") or {}

    object_id = str(
        hit.get("objectID")
        or hit.get("CIN")
        or ""
    ).strip()

    cin = str(
        hit.get("CIN")
        or object_id
    ).strip()

    if object_id:
        product_url = (
            "https://www.asda.com/groceries/product/"
            f"{quote(object_id)}"
        )
    else:
        product_url = ""

    return {
        "product_id": str(hit.get("ID") or ""),
        "cin": cin,
        "product_name": str(
            hit.get("NAME") or ""
        ).strip(),
        "brand": str(hit.get("BRAND") or ""),
        "product_url": product_url,
        "average_rating": safe_float(
            hit.get("AVG_RATING")
        ),
        "rating_count": safe_float(
            hit.get("RATING_COUNT")
        ),
        "image_id": str(
            hit.get("IMAGE_ID") or ""
        ),
        "pack_size": str(
            hit.get("PACK_SIZE") or ""
        ),
        "product_type": str(
            hit.get("PRODUCT_TYPE") or ""
        ),
        "display_online": hit.get(
            "DISPLAY_ONLINE", ""
        ),
        "status": str(
            hit.get("STATUS") or ""
        ),
        "primary_category": str(
            taxonomy.get("CAT_NAME") or ""
        ),
        "primary_department": str(
            taxonomy.get("DEPT_NAME") or ""
        ),
        "primary_aisle": str(
            taxonomy.get("AISLE_NAME") or ""
        ),
        "primary_shelf": str(
            taxonomy.get("SHELF_NAME") or ""
        ),
        "page_taxonomy": " | ".join(
            hit.get("PAGE_TAXONOMY") or []
        ),
        "price_en_gbp": safe_float(
            en_price.get("PRICE")
        ),
        "collected_at_utc": collected_at,
    }


# --------------------------------------------------
# GROCERY PRODUCT VALIDATION
# --------------------------------------------------

def is_grocery_product(hit, row):
    """
    Check the primary category and taxonomy paths.

    A product is accepted if its primary category
    or a taxonomy path contains a configured
    grocery category.
    """

    primary_category = (
        row["primary_category"]
        .strip()
        .casefold()
    )

    if primary_category in GROCERY_CATEGORIES:
        return True

    page_taxonomy = hit.get("PAGE_TAXONOMY") or []

    for path in page_taxonomy:

        categories = [
            part.strip().casefold()
            for part in str(path).split(">")
        ]

        if any(
            category in GROCERY_CATEGORIES
            for category in categories
        ):
            return True

    return False


# --------------------------------------------------
# CSV WRITER
# --------------------------------------------------

def write_csv(path, rows, fieldnames):

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


# --------------------------------------------------
# MAIN FUNCTION
# --------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Collect ASDA grocery products "
            "and ratings from Algolia."
        )
    )

    parser.add_argument(
        "--hits-per-page",
        type=int,
        default=DEFAULT_HITS_PER_PAGE,
    )

    parser.add_argument(
        "--max-products",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--category",
        default="",
        help=(
            "Optional primary category filter, "
            "for example Frozen Food."
        ),
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=REQUEST_DELAY_SECONDS,
    )

    args = parser.parse_args()

    if not 1 <= args.hits_per_page <= 1000:
        parser.error(
            "--hits-per-page must be between 1 and 1000."
        )

    if args.max_products < 0:
        parser.error(
            "--max-products cannot be negative."
        )

    if args.delay < 0:
        parser.error(
            "--delay cannot be negative."
        )

    # Create session
    session = requests.Session()

    session.headers.update({
        "Accept": "application/json"
    })

    print("=" * 64)
    print("ASDA GROCERY PRODUCT RATINGS COLLECTOR")
    print("=" * 64)

    # Read Algolia configuration
    try:

        (
            app_id,
            api_key,
            index_name,
            config_status,
        ) = get_algolia_config(session)

    except Exception as exc:

        print(f"CONFIGURATION ERROR: {exc}")
        sys.exit(1)

    print(
        f"ASDA configuration page: HTTP {config_status}"
    )

    print(f"Algolia index: {index_name}")
    print("Grocery category filtering: ENABLED")

    # Construct endpoint
    endpoint = ALGOLIA_ENDPOINT_TEMPLATE.format(
        app_id=app_id,
        index=quote(index_name, safe=""),
    )

    # Collection variables
    page = 0
    total_available = None

    all_rows = []
    seen_ids = set()

    request_log = []
    failed_requests = []

    request_successes = 0
    request_failures = 0

    parser_successes = 0
    parser_failures = 0

    grocery_hits = 0
    non_grocery_hits = 0

    collected_at = datetime.now(
        timezone.utc
    ).isoformat()

    # --------------------------------------------------
    # PAGINATED COLLECTION
    # --------------------------------------------------

    while True:

        payload = {
            "query": "",
            "page": page,
            "hitsPerPage": args.hits_per_page,
        }

        response = None
        error_message = ""
        attempt = 0

        # Request retry loop
        for attempt in range(
            1,
            MAX_RETRIES + 1,
        ):

            try:

                response = session.post(
                    endpoint,

                    headers={
                        "x-algolia-application-id": app_id,
                        "x-algolia-api-key": api_key,
                        "Content-Type": "application/json",
                    },

                    json=payload,
                    impersonate="chrome",
                    timeout=TIMEOUT_SECONDS,
                )

                if response.status_code == 200:
                    break

                error_message = (
                    f"HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )

            except Exception as exc:

                error_message = str(exc)

            if attempt < MAX_RETRIES:
                time.sleep(attempt * 2)

        # Handle failed request
        if (
            response is None
            or response.status_code != 200
        ):

            request_failures += 1

            log_row = {
                "page": page,
                "attempts": attempt,
                "http_status": (
                    response.status_code
                    if response is not None
                    else ""
                ),
                "request_status": "FAILED",
                "records_returned": 0,
                "error": error_message,
            }

            request_log.append(log_row)
            failed_requests.append(log_row)

            print(
                f"Page {page}: FAILED - "
                f"{error_message}"
            )

            break

        request_successes += 1

        # Parse JSON response
        try:

            result = response.json()

        except Exception as exc:

            request_failures += 1
            request_successes -= 1

            error_message = (
                f"Invalid JSON response: {exc}"
            )

            log_row = {
                "page": page,
                "attempts": attempt,
                "http_status": response.status_code,
                "request_status": "FAILED",
                "records_returned": 0,
                "error": error_message,
            }

            request_log.append(log_row)
            failed_requests.append(log_row)

            print(error_message)
            break

        hits = result.get("hits") or []

        # Total Algolia records
        if total_available is None:

            total_available = int(
                result.get("nbHits") or 0
            )

            print(
                f"\nAlgolia matching records: "
                f"{total_available:,}"
            )

            print(
                f"Records per page: "
                f"{args.hits_per_page}\n"
            )

        # Log successful request
        request_log.append({
            "page": page,
            "attempts": attempt,
            "http_status": response.status_code,
            "request_status": "SUCCESS",
            "records_returned": len(hits),
            "error": "",
        })

        # --------------------------------------------------
        # PROCESS EACH PRODUCT
        # --------------------------------------------------

        for hit in hits:

            row = record_to_row(
                hit,
                collected_at,
            )

            # Filter grocery products
            if not is_grocery_product(
                hit,
                row,
            ):

                non_grocery_hits += 1
                continue

            grocery_hits += 1

            unique_id = (
                row["cin"]
                or row["product_url"]
            )

            if (
                not unique_id
                or unique_id in seen_ids
            ):
                continue

            seen_ids.add(unique_id)

            # Parser success validation
            if (
                row["product_name"]
                and row["product_url"]
            ):

                parser_successes += 1

            else:

                parser_failures += 1

            # Optional primary category filter
            if args.category:

                if (
                    args.category.casefold()
                    not in row["primary_category"].casefold()
                ):
                    continue

            all_rows.append(row)

            # Stop after requested product count
            if (
                args.max_products
                and len(all_rows) >= args.max_products
            ):
                break

        print(
            f"Page {page + 1}: HTTP 200 | "
            f"Received: {len(hits)} | "
            f"Grocery matched: {grocery_hits} | "
            f"Saved: {len(all_rows)}"
        )

        # Maximum product limit reached
        if (
            args.max_products
            and len(all_rows) >= args.max_products
        ):

            print("\nReached product limit.")
            break

        # Pagination check
        nb_pages = int(
            result.get("nbPages") or 0
        )

        if (
            not hits
            or page + 1 >= nb_pages
        ):
            break

        page += 1

        if args.delay > 0:
            time.sleep(args.delay)

    # --------------------------------------------------
    # SAVE OUTPUT FILES
    # --------------------------------------------------

    write_csv(
        OUTPUT_CSV,
        all_rows,
        CSV_FIELDS,
    )

    request_fields = [
        "page",
        "attempts",
        "http_status",
        "request_status",
        "records_returned",
        "error",
    ]

    write_csv(
        REQUEST_LOG_CSV,
        request_log,
        request_fields,
    )

    write_csv(
        FAILED_REQUESTS_CSV,
        failed_requests,
        request_fields,
    )

    # --------------------------------------------------
    # CALCULATE STATISTICS
    # --------------------------------------------------

    total_requests = len(request_log)

    crawler_success_rate = (
        request_successes / total_requests * 100
        if total_requests
        else 0
    )

    crawler_failure_rate = (
        request_failures / total_requests * 100
        if total_requests
        else 0
    )

    parsed_total = (
        parser_successes + parser_failures
    )

    parser_success_rate = (
        parser_successes / parsed_total * 100
        if parsed_total
        else 0
    )

    parser_failure_rate = (
        parser_failures / parsed_total * 100
        if parsed_total
        else 0
    )

    # --------------------------------------------------
    # FINAL REPORT
    # --------------------------------------------------

    print("\n" + "=" * 64)
    print("ASDA GROCERY COLLECTION SUMMARY")
    print("=" * 64)

    print(
        f"Algolia records reported: "
        f"{total_available or 0:,}"
    )

    print(
        f"Grocery products matched: "
        f"{grocery_hits:,}"
    )

    print(
        f"Non-grocery products skipped: "
        f"{non_grocery_hits:,}"
    )

    print(
        f"Unique grocery products saved: "
        f"{len(all_rows):,}"
    )

    print(f"Output file: {OUTPUT_CSV}")

    print("\nCRAWLER REQUEST STATISTICS")

    print(f"Total requests: {total_requests}")
    print(f"Successful requests: {request_successes}")
    print(f"Failed requests: {request_failures}")

    print(
        f"Success rate: "
        f"{crawler_success_rate:.2f}%"
    )

    print(
        f"Failure rate: "
        f"{crawler_failure_rate:.2f}%"
    )

    print("\nPARSER STATISTICS")

    print(
        f"Total unique grocery records evaluated: "
        f"{parsed_total}"
    )

    print(f"Parser success: {parser_successes}")
    print(f"Parser failure: {parser_failures}")

    print(
        f"Success rate: "
        f"{parser_success_rate:.2f}%"
    )

    print(
        f"Failure rate: "
        f"{parser_failure_rate:.2f}%"
    )

    print("\nADDITIONAL FILES")

    print(f"- {REQUEST_LOG_CSV}")
    print(f"- {FAILED_REQUESTS_CSV}")

    print("\nNOTE:")
    print(
        "Request statistics measure Algolia page requests, "
        "not individual PDP requests."
    )

    print(
        "This script collects catalogue ratings and counts, "
        "not individual written reviews."
    )


if __name__ == "__main__":
    main()