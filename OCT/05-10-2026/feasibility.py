from curl_cffi import requests
from scrapy import Selector
import json
import csv
import time
from urllib.parse import urljoin


# =============================================================================
# SETTINGS
# =============================================================================

BASE_URL = "https://noragardner.com"

COLLECTION_URL = (
    "https://noragardner.com/collections/dresses"
)

TARGET_RECORDS = 500

PRODUCTS_PER_PAGE = 24

REVIEW_LIMIT = 100

OUTPUT_FILE = "nora_gardner_reviews.csv"

PROXY_STRING = ""


# =============================================================================
# PROXY
# =============================================================================

proxies = None

if PROXY_STRING.strip():

    proxies = {
        "http": "http://" + PROXY_STRING,
        "https": "http://" + PROXY_STRING,
    }


# =============================================================================
# HEADERS
# =============================================================================

headers = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:128.0) "
        "Gecko/20100101 Firefox/128.0"
    ),

    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/png,*/*;q=0.8"
    ),

    "Accept-Language": "en-US,en;q=0.5",

    "Connection": "keep-alive",

    "Upgrade-Insecure-Requests": "1",
}


# =============================================================================
# REQUEST STATISTICS
# =============================================================================

request_count = 0

record_count = 0

request_depth = 0

block_checked_urls = set()


# =============================================================================
# GET FUNCTION
# =============================================================================

def get(url, headers=headers, params=None, depth=0):

    global request_count
    global request_depth
    global block_checked_urls

    request_count += 1

    # Track deepest request made
    request_depth = max(
        request_depth,
        depth
    )

    print()
    print(
        "[GET]",
        "request =", request_count,
        "| depth =", depth
    )

    print(
        "[URL]",
        url
    )

    try:

        response = requests.get(
            url,
            headers=headers,
            params=params,
            proxies=proxies,
            timeout=30,
            impersonate="chrome",
        )

        print(
            "[STATUS]",
            response.status_code
        )

        # -------------------------------------------------------------
        # BLOCK CHECK
        # -------------------------------------------------------------

        block_checked_urls.add(url)

        if response.status_code in [401, 403, 406, 429]:

            print(
                "[BLOCKED]",
                response.status_code,
                url
            )

        return response

    except Exception as e:

        print(
            "[ERROR]",
            url
        )

        print(e)

        return None


# =============================================================================
# CRAWLER
# =============================================================================

print("=" * 80)

print("CRAWLER")

print("=" * 80)


product_urls = []

seen_urls = set()

page = 1


while True:

    page_url = COLLECTION_URL

    if page > 1:

        page_url = (
            COLLECTION_URL
            + "?page="
            + str(page)
        )

    print()

    print(
        "[CRAWLER PAGE]",
        page
    )

    print(
        "[+] URL :",
        page_url
    )


    response = get(
        page_url,
        depth=0
    )


    if response is None:

        print(
            "[ERROR] No response"
        )

        break


    print(
        "[CRAWLER STATUS]",
        response.status_code
    )


    if response.status_code != 200:

        print(
            "[ERROR] Crawler failed"
        )

        break


    selector = Selector(
        text=response.text
    )


    # -------------------------------------------------------------------------
    # PRODUCT LINKS
    # -------------------------------------------------------------------------

    links = selector.xpath(
        "//a[contains(@href,'/products/')]/@href"
    ).getall()


    new_products = 0


    for link in links:

        full_url = urljoin(
            BASE_URL,
            link
        )


        # Remove query string

        full_url = full_url.split("?")[0]


        # Skip gift card

        if "/products/gift-card" in full_url:

            continue


        if full_url not in seen_urls:

            seen_urls.add(full_url)

            product_urls.append(full_url)

            new_products += 1


    print(
        "[+] New products :",
        new_products
    )


    print(
        "[+] Total unique products :",
        len(product_urls)
    )


    # -------------------------------------------------------------------------
    # STOP IF NO NEW PRODUCTS
    # -------------------------------------------------------------------------

    if new_products == 0:

        print(
            "[+] No new products found."
        )

        break


    page += 1


    # Safety

    if page > 100:

        print(
            "[+] Maximum crawler pages reached."
        )

        break


    time.sleep(1)


# =============================================================================
# CRAWLER RESULT
# =============================================================================

print()

print("=" * 80)

print("CRAWLER RESULT")

print("=" * 80)


print(
    "Unique Product URL count :",
    len(product_urls)
)


for url in product_urls:

    print(url)


# =============================================================================
# PARSER + RATING
# =============================================================================

all_review_rows = []

processed_products = 0


for product_index, product_url in enumerate(
    product_urls,
    start=1
):

    print()

    print("=" * 80)

    print(
        "PRODUCT",
        f"{product_index}/{len(product_urls)}"
    )

    print(product_url)

    print("=" * 80)


    # -------------------------------------------------------------------------
    # PRODUCT PAGE
    # -------------------------------------------------------------------------

    response = get(
        product_url,
        depth=1
    )


    if response is None:

        print(
            "[ERROR] Product request failed"
        )

        continue


    print(
        "[PRODUCT STATUS]",
        response.status_code
    )


    if response.status_code != 200:

        print(
            "[ERROR] Product page failed"
        )

        continue


    selector = Selector(
        text=response.text
    )


    # -------------------------------------------------------------------------
    # SHOPIFY JSON
    # -------------------------------------------------------------------------

    product_json_url = (
        product_url.rstrip("/")
        + ".js"
    )


    print()

    print(
        "[+] Shopify JSON"
    )


    print(
        "[+] Shopify URL :",
        product_json_url
    )


    shopify_response = get(
        product_json_url,
        depth=1
    )


    if shopify_response is None:

        continue


    print(
        "[SHOPIFY RESPONSE]",
        shopify_response.status_code
    )


    if shopify_response.status_code != 200:

        print(
            "[ERROR] Shopify JSON failed"
        )

        continue


    try:

        product_data = shopify_response.json()

    except Exception:

        print(
            "[ERROR] Invalid Shopify JSON"
        )

        continue


    # -------------------------------------------------------------------------
    # PRODUCT INFORMATION
    # -------------------------------------------------------------------------

    shopify_id = product_data.get(
        "id",
        ""
    )


    product_name = product_data.get(
        "title",
        ""
    )


    vendor = product_data.get(
        "vendor",
        ""
    )


    sku = ""


    variants = product_data.get(
        "variants",
        []
    )


    if variants:

        sku = variants[0].get(
            "sku",
            ""
        )


    # Shopify price is normally in dollars
    # Keeping your existing *100 structure

    original_price = ""

    sale_price = ""


    if variants:

        variant = variants[0]


        price = variant.get(
            "price"
        )


        compare_price = variant.get(
            "compare_at_price"
        )


        try:

            sale_price = (
                float(price) * 100
                if price
                else ""
            )

        except Exception:

            sale_price = price


        try:

            original_price = (
                float(compare_price) * 100
                if compare_price
                else sale_price
            )

        except Exception:

            original_price = compare_price


    # -------------------------------------------------------------------------
    # CATEGORY FROM XPATH
    # -------------------------------------------------------------------------

    category = selector.xpath(
        "//nav[contains(@class,'breadcrumb')]"
        "//a/text()"
    ).getall()


    category = [
        x.strip()
        for x in category
        if x.strip()
    ]


    if category:

        category = category[-1]

    else:

        category = ""


    print()

    print(
        "[SHOPIFY ID]",
        shopify_id
    )


    print()

    print(
        "[PRODUCT DATA]"
    )


    print(
        "product_sku    :",
        sku
    )


    print(
        "product_name   :",
        product_name
    )


    print(
        "brand          :",
        vendor
    )


    print(
        "original_price :",
        original_price
    )


    print(
        "sale_price     :",
        sale_price
    )


    print(
        "category       :",
        category
    )


    # -------------------------------------------------------------------------
    # REVIEW API
    # -------------------------------------------------------------------------

    print()

    print(
        "[+] Getting reviews for product",
        shopify_id
    )


    offset = 0

    product_review_count = 0


    while True:


        review_url = (
            "https://fast.a.klaviyo.com/"
            "reviews/api/client_reviews/"
            + str(shopify_id)
            + "/"
        )


        params = {

            "product_id": str(shopify_id),

            "company_id": "HWxMF4",

            "limit": REVIEW_LIMIT,

            "offset": offset,

            "sort": 3,

            "filter": "",

            "type": "reviews",

            "media": "false",

            "kl_review_uuid": "",

            "preferred_country": "US",

            "tz": "America/New_York",
        }


        print()

        print(
            "[+] REVIEW API :",
            review_url
        )


        print(
            "[REVIEW API] offset =",
            offset
        )


        review_response = get(
            review_url,
            params=params,
            depth=2
        )


        if review_response is None:

            break


        print(
            "[REVIEW STATUS]",
            review_response.status_code
        )


        if review_response.status_code != 200:

            print(
                "[ERROR] Review API failed"
            )

            break


        try:

            review_json = review_response.json()

        except Exception:

            print(
                "[ERROR] Invalid review JSON"
            )

            break


        # ---------------------------------------------------------------------
        # FIND REVIEWS
        # ---------------------------------------------------------------------

        reviews = []


        if isinstance(
            review_json,
            dict
        ):


            results = review_json.get(
                "results",
                []
            )


            for result in results:


                if not isinstance(
                    result,
                    dict
                ):

                    continue


                result_reviews = result.get(
                    "reviews",
                    []
                )


                if result_reviews:

                    reviews.extend(
                        result_reviews
                    )


        print(
            "[+] Reviews returned :",
            len(reviews)
        )


        # ---------------------------------------------------------------------
        # NO REVIEWS
        # ---------------------------------------------------------------------

        if not reviews:

            print(
                "[+] No more reviews"
            )

            break


        # ---------------------------------------------------------------------
        # PROCESS REVIEWS
        # ---------------------------------------------------------------------

        for review in reviews:


            details = review.get(
                "details",
                {}
            )


            metrics = review.get(
                "metrics",
                {}
            )


            review_row = {

                "url": product_url,

                "product_sku": sku,

                "product_name": product_name,

                "brand": vendor,

                "original_price": original_price,

                "sale_price": sale_price,

                "category": category,

                "total_number_of_reviews": "",

                "1_star": 0,

                "2_star": 0,

                "3_star": 0,

                "4_star": 0,

                "5_star": 0,

                "stars": metrics.get(
                    "rating",
                    ""
                ),

                "date_of_purchase": details.get(
                    "updated_date",
                    ""
                ),

                "place_of_purchase": details.get(
                    "location",
                    ""
                ),

                "review_title": details.get(
                    "title",
                    ""
                ),

                "review_text": details.get(
                    "text",
                    ""
                ),
            }


            # -------------------------------------------------------------
            # STAR COUNT
            # -------------------------------------------------------------

            rating = metrics.get(
                "rating"
            )


            try:

                rating_int = int(
                    float(rating)
                )


                if rating_int in range(1, 6):

                    review_row[
                        f"{rating_int}_star"
                    ] = 1

            except Exception:

                pass


            # -------------------------------------------------------------
            # ADD RECORD
            # -------------------------------------------------------------

            all_review_rows.append(
                review_row
            )


            product_review_count += 1


            global_record_count = len(
                all_review_rows
            )


            print()

            print(
                "  REVIEW"
            )


            print(
                "  stars              :",
                review_row["stars"]
            )


            print(
                "  review_title       :",
                review_row["review_title"]
            )


            print(
                "  review_text        :",
                review_row["review_text"]
            )


            print(
                "  date_of_purchase   :",
                review_row["date_of_purchase"]
            )


            print(
                "  place_of_purchase  :",
                review_row["place_of_purchase"]
            )


            print()

            print(
                "  [RECORD COUNT]",
                global_record_count,
                "/",
                TARGET_RECORDS
            )


            # -------------------------------------------------------------
            # TARGET REACHED
            # -------------------------------------------------------------

            if len(all_review_rows) >= TARGET_RECORDS:

                print()

                print(
                    "[+] TARGET RECORD COUNT REACHED"
                )

                break


        # ---------------------------------------------------------------------
        # STOP TARGET
        # ---------------------------------------------------------------------

        if len(all_review_rows) >= TARGET_RECORDS:

            break


        # ---------------------------------------------------------------------
        # PAGINATION
        # ---------------------------------------------------------------------

        if len(reviews) < REVIEW_LIMIT:

            print(
                "[+] Last review page reached"
            )

            break


        offset += REVIEW_LIMIT


        print()

        print(
            "[+] PAGINATION"
        )

        print(
            "[+] Next offset :",
            offset
        )


        time.sleep(1)


    print()

    print(
        "[+] TOTAL REVIEWS:",
        product_review_count
    )


    processed_products += 1


    # -------------------------------------------------------------------------
    # LIVE REQUEST STATISTICS
    # -------------------------------------------------------------------------

    print()

    print(
        "[LIVE REQUEST STATISTICS]"
    )

    print(
        "record count       :",
        len(all_review_rows)
    )

    print(
        "request depth      :",
        request_depth
    )

    print(
        "request count      :",
        request_count
    )

    print(
        "block checked URLs :",
        len(block_checked_urls)
    )


    # -------------------------------------------------------------------------
    # GLOBAL TARGET
    # -------------------------------------------------------------------------

    if len(all_review_rows) >= TARGET_RECORDS:

        print()

        print(
            "=" * 80
        )

        print(
            "[+] TARGET OF",
            TARGET_RECORDS,
            "RECORDS REACHED"
        )

        print(
            "=" * 80
        )

        break


    time.sleep(1)


# =============================================================================
# TOTAL REVIEW COUNT
# =============================================================================

record_count = len(
    all_review_rows
)


# =============================================================================
# CSV
# =============================================================================

print()

print("=" * 80)

print("SAVING CSV")

print("=" * 80)


fieldnames = [

    "url",

    "product_sku",

    "product_name",

    "brand",

    "original_price",

    "sale_price",

    "category",

    "total_number_of_reviews",

    "1_star",

    "2_star",

    "3_star",

    "4_star",

    "5_star",

    "stars",

    "date_of_purchase",

    "place_of_purchase",

    "review_title",

    "review_text",
]


with open(
    OUTPUT_FILE,
    "w",
    newline="",
    encoding="utf-8"
) as file:


    writer = csv.DictWriter(
        file,
        fieldnames=fieldnames
    )


    writer.writeheader()


    writer.writerows(
        all_review_rows
    )


print(
    "[+] Review rows :",
    record_count
)


print(
    "[+] CSV :",
    OUTPUT_FILE
)


# =============================================================================
# FIELD REPORT
# =============================================================================

print()

print("=" * 80)

print("FIELD REPORT")

print("=" * 80)


print(
    "available: url, product_sku, product_name, "
    "brand, original_price, sale_price, category, "
    "total_number_of_reviews, 1_star, 2_star, "
    "3_star, 4_star, 5_star, stars, review_title, "
    "review_text, date_of_purchase"
)


print(
    "not available: place_of_purchase"
)


# =============================================================================
# REQUEST STATISTICS
# =============================================================================

print()

print("=" * 80)

print("REQUEST STATISTICS")

print("=" * 80)


print(
    "record count        :",
    record_count
)


print(
    "request depth       :",
    request_depth
)


print(
    "request count       :",
    request_count
)


print(
    "block checked URLs  :",
    len(block_checked_urls)
)


print(
    "products processed  :",
    processed_products
)


print(
    "products discovered :",
    len(product_urls)
)


# =============================================================================
# DONE
# =============================================================================

print()

print("=" * 80)

print("DONE")

print("=" * 80)