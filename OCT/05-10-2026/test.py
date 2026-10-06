import asyncio
import csv
import json
import re
import time
from urllib.parse import urlparse

from cloakbrowser import launch_async


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://noragardner.com"

COMPANY_ID = "HWxMF4"

OUTPUT_CSV = "nora_gardner_reviews.csv"

PRODUCT_URLS = [
    "https://noragardner.com/collections/dresses/products/clea-dress-magenta",
    "https://noragardner.com/collections/dresses/products/evelyn-dress-magenta",
    "https://noragardner.com/collections/dresses/products/evelyn-dress-espresso",
    "https://noragardner.com/collections/dresses/products/evelyn-dress-light-grey-wool",
    "https://noragardner.com/collections/dresses/products/alyssa-dress-navy",
    "https://noragardner.com/collections/dresses/products/dinah-dress-beige-boucle",
    "https://noragardner.com/products/gift-card",
]


# ============================================================
# CSV FIELDS
# ============================================================

CSV_FIELDS = [
    "url",
    "product_sku",
    "product_name",
    "brand",
    "original_price",
    "sale_price",
    "category",
    "total_number_of_reviews",
    "stars",
    "date_of_purchase",
    "place_of_purchase",
    "review_title",
    "review_text",
]


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    value = str(value)

    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def first_value(data, *keys):
    """
    Recursively search dictionary/list for the first matching key.
    """

    if isinstance(data, dict):

        for key in keys:
            if key in data and data[key] not in (None, ""):
                return data[key]

        for value in data.values():

            result = first_value(value, *keys)

            if result not in (None, ""):
                return result

    elif isinstance(data, list):

        for item in data:

            result = first_value(item, *keys)

            if result not in (None, ""):
                return result

    return ""


def recursive_find_all(data, target_key):

    results = []

    if isinstance(data, dict):

        for key, value in data.items():

            if key.lower() == target_key.lower():
                results.append(value)

            results.extend(
                recursive_find_all(value, target_key)
            )

    elif isinstance(data, list):

        for item in data:

            results.extend(
                recursive_find_all(item, target_key)
            )

    return results


def extract_product_slug(url):

    path = urlparse(url).path.rstrip("/")

    return path.split("/")[-1]


def print_field(name, value):

    if value in (None, ""):
        display = "NOT FOUND"
    else:
        display = value

    print(f"{name:<25}: {display}")


# ============================================================
# SHOPIFY PRODUCT
# ============================================================

async def get_shopify_product(context, product_url):

    slug = extract_product_slug(product_url)

    json_url = f"{BASE_URL}/products/{slug}.js"

    print(f"[+] Shopify JSON: {json_url}")

    for attempt in range(1, 4):

        try:

            response = await context.request.get(
                json_url,
                timeout=30000,
                headers={
                    "Accept": "application/json",
                    "Referer": product_url,
                },
            )

            print(
                f"[SHOPIFY RESPONSE] HTTP {response.status}"
            )

            if response.status == 200:

                data = await response.json()

                return data

            if response.status == 429:

                wait_time = attempt * 5

                print(
                    f"[429] Shopify rate limit."
                    f" Waiting {wait_time}s..."
                )

                await asyncio.sleep(wait_time)

                continue

            print(
                f"[ERROR] Shopify HTTP {response.status}"
            )

        except Exception as e:

            print(
                f"[ERROR] Shopify request failed: {e}"
            )

            await asyncio.sleep(2)

    return None


# ============================================================
# PRODUCT DATA
# ============================================================

def extract_product_data(product, product_url):

    if not product:
        return None

    product_id = product.get("id", "")

    title = clean_text(
        product.get("title", "")
    )

    vendor = clean_text(
        product.get("vendor", "")
    )

    product_type = clean_text(
        product.get("product_type", "")
    )

    tags = product.get("tags", [])

    if isinstance(tags, list):
        tags = ", ".join(
            clean_text(x) for x in tags
        )
    else:
        tags = clean_text(tags)

    variants = product.get("variants", [])

    variant = variants[0] if variants else {}

    sku = clean_text(
        variant.get("sku", "")
    )

    sale_price = variant.get(
        "price", ""
    )

    compare_price = variant.get(
        "compare_at_price", ""
    )

    try:
        if sale_price not in ("", None):
            sale_price = float(sale_price)
            sale_price *= 100
    except Exception:
        pass

    try:
        if compare_price not in ("", None):
            compare_price = float(compare_price)
            compare_price *= 100
    except Exception:
        pass

    # Shopify price values are dollars.
    # Convert to cents because previous output showed
    # 32800 = $328.00.

    if compare_price in ("", None, 0):
        original_price = sale_price
    else:
        original_price = compare_price

    # If there is no discount, sale_price should still
    # represent current price.

    return {
        "url": product_url,
        "product_sku": sku,
        "product_name": title,
        "brand": vendor,
        "original_price": original_price,
        "sale_price": sale_price,
        "category": product_type,
        "shopify_id": str(product_id),
        "tags": tags,
    }


# ============================================================
# KLAVIYO REVIEW API
# ============================================================

async def get_reviews(
    context,
    product_id,
    product_url
):

    print(
        f"[+] Getting reviews for product "
        f"{product_id}"
    )

    all_reviews = []

    offset = 0
    limit = 100

    while True:

        review_url = (
            "https://fast.a.klaviyo.com/"
            "reviews/api/client_reviews/"
            f"{product_id}/"
            f"?product_id={product_id}"
            f"&company_id={COMPANY_ID}"
            f"&limit={limit}"
            f"&offset={offset}"
            "&sort=3"
            "&filter="
            "&type=reviews"
            "&media=false"
            "&kl_review_uuid="
            "&preferred_country=US"
            "&tz=America/New_York"
        )

        print(
            f"[+] REVIEW API offset={offset}"
        )

        try:

            response = await context.request.get(
                review_url,
                timeout=30000,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Referer": product_url,
                    "Origin": BASE_URL,
                },
            )

            print(
                f"[REVIEW RESPONSE] HTTP "
                f"{response.status}"
            )

            if response.status == 429:

                print(
                    "[429] Klaviyo rate limit."
                )

                await asyncio.sleep(5)

                continue

            if response.status != 200:

                print(
                    "[ERROR] Review HTTP status:",
                    response.status
                )

                break

            try:

                data = await response.json()

            except Exception:

                text = await response.text()

                print(
                    "[ERROR] Review response "
                    "was not JSON."
                )

                print(
                    text[:1000]
                )

                break

            # ------------------------------------------------
            # Find review list
            # ------------------------------------------------

            reviews = []

            if isinstance(data, dict):

                for key in [
                    "reviews",
                    "data",
                    "results",
                    "items",
                ]:

                    value = data.get(key)

                    if isinstance(value, list):

                        reviews = value
                        break

                    if (
                        isinstance(value, dict)
                        and isinstance(
                            value.get("reviews"),
                            list
                        )
                    ):

                        reviews = value["reviews"]
                        break

            elif isinstance(data, list):

                reviews = data

            print(
                f"[+] Retrieved "
                f"{len(reviews)} reviews"
            )

            if not reviews:
                break

            all_reviews.extend(reviews)

            if len(reviews) < limit:
                break

            offset += limit

            await asyncio.sleep(1)

        except Exception as e:

            print(
                "[ERROR] Review request failed:",
                e
            )

            break

    print(
        f"[+] TOTAL REVIEWS: "
        f"{len(all_reviews)}"
    )

    return all_reviews


# ============================================================
# REVIEW FIELD EXTRACTION
# ============================================================

def extract_review(review):

    # --------------------------------------------------------
    # STAR RATING
    # --------------------------------------------------------

    stars = first_value(
        review,
        "rating",
        "stars",
        "score",
        "star_rating",
        "review_rating",
    )

    if isinstance(stars, dict):

        stars = first_value(
            stars,
            "value",
            "rating",
            "score"
        )

    if stars != "":
        try:
            stars = float(stars)

            if stars.is_integer():
                stars = int(stars)

        except Exception:
            pass

    # --------------------------------------------------------
    # REVIEW TITLE
    # --------------------------------------------------------

    title = first_value(
        review,
        "title",
        "review_title",
        "headline",
    )

    # --------------------------------------------------------
    # REVIEW TEXT
    # --------------------------------------------------------

    text = first_value(
        review,
        "body",
        "review_text",
        "content",
        "text",
        "description",
    )

    # --------------------------------------------------------
    # PURCHASE DATE
    # --------------------------------------------------------

    purchase_date = first_value(
        review,
        "order_purchase_date",
        "purchase_date",
        "date_of_purchase",
        "order_date",
    )

    # --------------------------------------------------------
    # PLACE OF PURCHASE
    # --------------------------------------------------------

    place_of_purchase = first_value(
        review,
        "place_of_purchase",
        "purchase_location",
        "store",
        "store_name",
        "purchase_place",
    )

    # --------------------------------------------------------
    # FALLBACK REVIEW DATE
    # --------------------------------------------------------

    review_date = first_value(
        review,
        "created_at",
        "published_at",
        "date",
        "created",
    )

    return {
        "stars": stars,
        "date_of_purchase": clean_text(
            purchase_date
        ),
        "place_of_purchase": clean_text(
            place_of_purchase
        ),
        "review_title": clean_text(
            title
        ),
        "review_text": clean_text(
            text
        ),
        "review_date": clean_text(
            review_date
        ),
    }


# ============================================================
# PRINT REVIEW
# ============================================================

def print_review_fields(review_data):

    print()
    print("-" * 70)
    print("REVIEW DATA")
    print("-" * 70)

    print_field(
        "stars",
        review_data["stars"]
    )

    print_field(
        "date_of_purchase",
        review_data["date_of_purchase"]
    )

    print_field(
        "place_of_purchase",
        review_data["place_of_purchase"]
    )

    print_field(
        "review_title",
        review_data["review_title"]
    )

    print_field(
        "review_text",
        review_data["review_text"]
    )

    print("-" * 70)


# ============================================================
# PRODUCT PROCESSING
# ============================================================

async def process_product(
    context,
    product_url,
    index,
    total
):

    print()
    print("=" * 80)

    print(
        f"PRODUCT {index}/{total}"
    )

    print(product_url)

    print("=" * 80)

    # --------------------------------------------------------
    # OPEN PRODUCT PAGE
    # --------------------------------------------------------

    page = await context.new_page()

    try:

        print(
            "[+] Opening product page..."
        )

        await page.goto(
            product_url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        await page.wait_for_timeout(2000)

        print(
            "[+] Page loaded:",
            page.url
        )

    except Exception as e:

        print(
            "[ERROR] Page load failed:",
            e
        )

        await page.close()

        return []

    # --------------------------------------------------------
    # SHOPIFY
    # --------------------------------------------------------

    product = await get_shopify_product(
        context,
        product_url
    )

    if not product:

        print(
            "[ERROR] Product information unavailable"
        )

        await page.close()

        return []

    print(
        "[SHOPIFY ID]",
        product.get("id")
    )

    product_data = extract_product_data(
        product,
        product_url
    )

    print()
    print("[PRODUCT DATA]")

    print_field(
        "product_sku",
        product_data["product_sku"]
    )

    print_field(
        "product_name",
        product_data["product_name"]
    )

    print_field(
        "brand",
        product_data["brand"]
    )

    print_field(
        "original_price",
        product_data["original_price"]
    )

    print_field(
        "sale_price",
        product_data["sale_price"]
    )

    print_field(
        "category",
        product_data["category"]
    )

    print_field(
        "shopify_id",
        product_data["shopify_id"]
    )

    # --------------------------------------------------------
    # REVIEWS
    # --------------------------------------------------------

    reviews = await get_reviews(
        context,
        product_data["shopify_id"],
        product_url
    )

    total_reviews = len(reviews)

    print()
    print(
        "[PRODUCT REVIEW COUNT]",
        total_reviews
    )

    rows = []

    # --------------------------------------------------------
    # NO REVIEWS
    # --------------------------------------------------------

    if not reviews:

        print(
            "[!] No reviews found."
        )

        await page.close()

        return []

    # --------------------------------------------------------
    # PROCESS EACH REVIEW
    # --------------------------------------------------------

    for review_number, review in enumerate(
        reviews,
        start=1
    ):

        review_data = extract_review(
            review
        )

        print()
        print(
            f"[REVIEW "
            f"{review_number}/{total_reviews}]"
        )

        print_review_fields(
            review_data
        )

        row = {
            "url": product_data["url"],

            "product_sku":
                product_data["product_sku"],

            "product_name":
                product_data["product_name"],

            "brand":
                product_data["brand"],

            "original_price":
                product_data["original_price"],

            "sale_price":
                product_data["sale_price"],

            "category":
                product_data["category"],

            "total_number_of_reviews":
                total_reviews,

            "stars":
                review_data["stars"],

            "date_of_purchase":
                review_data[
                    "date_of_purchase"
                ],

            "place_of_purchase":
                review_data[
                    "place_of_purchase"
                ],

            "review_title":
                review_data[
                    "review_title"
                ],

            "review_text":
                review_data[
                    "review_text"
                ],
        }

        rows.append(row)

    await page.close()

    return rows


# ============================================================
# SAVE CSV
# ============================================================

def save_csv(rows):

    print()
    print("=" * 80)
    print("SAVING CSV")
    print("=" * 80)

    with open(
        OUTPUT_CSV,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=CSV_FIELDS,
            extrasaction="ignore",
        )

        writer.writeheader()

        writer.writerows(rows)

    print(
        f"[+] Review rows: {len(rows)}"
    )

    print(
        f"[+] CSV: {OUTPUT_CSV}"
    )


# ============================================================
# FIELD REPORT
# ============================================================

def field_report(rows):

    print()
    print("=" * 80)
    print("FINAL FIELD REPORT")
    print("=" * 80)

    for field in CSV_FIELDS:

        found = False

        for row in rows:

            value = row.get(field)

            if value not in (
                "",
                None,
            ):

                found = True
                break

        if found:
            status = "✓"
        else:
            status = "⚠"

        print(
            f"{field:<30}: {status}"
        )

    print()

    purchase_dates = sum(
        1
        for row in rows
        if row.get("date_of_purchase")
    )

    purchase_places = sum(
        1
        for row in rows
        if row.get("place_of_purchase")
    )

    stars = sum(
        1
        for row in rows
        if row.get("stars")
        not in ("", None)
    )

    print(
        "Reviews with stars       :",
        stars
    )

    print(
        "Reviews with purchase date :",
        purchase_dates
    )

    print(
        "Reviews with place of purchase :",
        purchase_places
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    print()
    print("=" * 80)
    print("NORA GARDNER REVIEW SCRAPER")
    print("Playwright + CloakBrowser")
    print("=" * 80)

    print()
    print("[1] Starting CloakBrowser...")

    browser = await launch_async(
        headless=False,
        stealth_args=True,
        humanize=True,
        timezone="America/New_York",
        locale="en-US",
    )

    print(
        "[+] CloakBrowser started"
    )

    context = await browser.new_context(
        viewport={
            "width": 1440,
            "height": 900,
        },
        locale="en-US",
        timezone_id="America/New_York",
        extra_http_headers={
            "Accept-Language":
                "en-US,en;q=0.9",
        },
    )

    print(
        "[+] Playwright context created"
    )

    all_rows = []

    total = len(PRODUCT_URLS)

    try:

        for index, product_url in enumerate(
            PRODUCT_URLS,
            start=1
        ):

            rows = await process_product(
                context,
                product_url,
                index,
                total,
            )

            all_rows.extend(rows)

            # Small delay between products
            await asyncio.sleep(2)

    finally:

        print()
        print(
            "[+] Closing browser..."
        )

        await context.close()

        await browser.close()

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    save_csv(all_rows)

    field_report(all_rows)

    print()
    print("=" * 80)
    print("DONE")
    print("=" * 80)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())