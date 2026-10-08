import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_URL = "https://www.calvinklein.us"
CATEGORY_URL = "https://www.calvinklein.us/en/women/apparel"

# Already downloaded HTML from the first page.
SEED_HTML = Path("calvin_klein_women_category.html")

OUTPUT_CSV = Path("calvin_klein_women_reviews.csv")
LOG_FILE = Path("calvin_klein_women_crawler.log")

REQUEST_TIMEOUT = 40
REQUEST_DELAY = 0.8

BATCH_SIZE = 16

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:128.0) "
        "Gecko/20100101 Firefox/128.0"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.5",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "no-cache",
}


# =============================================================================
# GLOBAL COUNTERS
# =============================================================================

crawler_requests = []
parser_requests = []

crawler_depths = []
parser_depths = []

crawler_success = 0
crawler_failure = 0

parser_success = 0
parser_failure = 0

blocking_checked_urls = []
blocking_success = 0
blocking_failure = 0

category_pages = 0
products_discovered = set()
products_scraped = set()

records = []


# =============================================================================
# LOGGING
# =============================================================================

def log(message=""):
    print(message)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def separator(char="=", length=100):
    log(char * length)


# =============================================================================
# URL NORMALIZATION
# =============================================================================

def normalize_url(url):
    if not url:
        return ""

    return urljoin(BASE_URL, url)


def normalize_product_url(url):
    """
    Remove tracking query parameters such as:

        ?journey=Tier_0000021
        ?journey=sadie-sink

    This prevents the same product from being scraped multiple times.
    """

    url = normalize_url(url)

    parsed = urlparse(url)

    clean = parsed._replace(
        query="",
        fragment=""
    )

    return urlunparse(clean)


# =============================================================================
# WOMEN PRODUCT VALIDATION
# =============================================================================

def is_women_product_url(url):
    """
    Only allow Calvin Klein Women's PDP URLs.
    """

    parsed = urlparse(url)

    path = parsed.path.lower()

    if not path.startswith("/en/women/"):
        return False

    if not path.endswith(".html"):
        return False

    # Calvin Klein product URLs normally end with a style/color code.
    filename = path.rstrip("/").split("/")[-1]

    # Example:
    # 44F665G-UB1.html
    # 47H935G-46E.html
    if not re.search(r"/[A-Z0-9]{5,12}-[A-Z0-9]{2,8}\.html$", path, re.I):
        return False

    return True


# =============================================================================
# PRODUCT URL EXTRACTION
# =============================================================================

def extract_product_urls(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    found = set()

    # Primary selector discovered in the downloaded HTML.
    for a in soup.select("a.ds-product-name[href]"):

        href = a.get("href")

        if not href:
            continue

        url = normalize_product_url(href)

        if is_women_product_url(url):
            found.add(url)

    # Fallback: scan every anchor.
    if not found:

        for a in soup.find_all("a", href=True):

            href = a.get("href")

            url = normalize_product_url(href)

            if is_women_product_url(url):
                found.add(url)

    return found


# =============================================================================
# CATEGORY PAGE / PAGINATION
# =============================================================================

def build_pagination_url(start):
    """
    Calvin Klein uses:

    Search-UpdateGrid
        ?cgid=Tier_0000021
        &srule=featured
        &start=16
        &sz=16
    """

    return (
        f"{BASE_URL}/on/demandware.store/"
        f"Sites-PVHCKUS-Site/en_US/Search-UpdateGrid"
        f"?cgid=Tier_0000021"
        f"&srule=featured"
        f"&start={start}"
        f"&sz={BATCH_SIZE}"
    )


def crawler_get(session, url, depth):
    global crawler_success
    global crawler_failure

    request_number = len(crawler_requests) + 1

    try:

        response = session.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

        crawler_requests.append({
            "number": request_number,
            "url": url,
            "status": response.status_code,
            "depth": depth,
            "size": len(response.content)
        })

        crawler_depths.append(depth)

        if response.status_code == 200:
            crawler_success += 1
        else:
            crawler_failure += 1

        log()
        log("=" * 100)
        log(f"[CRAWLER REQUEST #{request_number}]")
        log(f"[DEPTH] {depth}")
        log(f"[URL] {url}")
        log(f"[STATUS] {response.status_code}")
        log(f"[SIZE] {len(response.content):,} bytes")
        log(f"[FINAL URL] {response.url}")
        log("=" * 100)

        return response

    except Exception as e:

        crawler_failure += 1

        crawler_requests.append({
            "number": request_number,
            "url": url,
            "status": None,
            "depth": depth,
            "size": 0,
            "error": str(e)
        })

        crawler_depths.append(depth)

        log()
        log("=" * 100)
        log(f"[CRAWLER REQUEST #{request_number}]")
        log(f"[DEPTH] {depth}")
        log(f"[URL] {url}")
        log("[STATUS] REQUEST FAILED")
        log(f"[ERROR] {e}")
        log("=" * 100)

        return None


# =============================================================================
# BLOCKING CHECK
# =============================================================================

def check_blocking_url(session, url):
    """
    Check the URLs that are actually used by the crawler/parser.

    This does not try to bypass Cloudflare/Akamai.
    It simply records whether the URL is successfully reachable.
    """

    global blocking_success
    global blocking_failure

    if url in blocking_checked_urls:
        return

    blocking_checked_urls.append(url)

    try:

        response = session.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

        status = response.status_code

        blocking_text = response.text[:50000].lower()

        blocked_signals = [
            "access denied",
            "request blocked",
            "temporarily blocked",
            "captcha",
            "verify you are human",
            "attention required",
            "cloudflare ray id",
            "datadome",
            "akamai bot manager",
        ]

        detected_block = any(
            signal in blocking_text
            for signal in blocked_signals
        )

        if 200 <= status < 400 and not detected_block:
            blocking_success += 1
            result = "SUCCESS"
        else:
            blocking_failure += 1
            result = "BLOCKED / FAILED"

        log(
            f"[BLOCK CHECK] {result} | "
            f"{status} | {url}"
        )

    except Exception as e:

        blocking_failure += 1

        log(
            f"[BLOCK CHECK] FAILED | "
            f"{url} | {e}"
        )


# =============================================================================
# JSON-LD
# =============================================================================

def get_jsonld(soup):
    blocks = []

    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    ):

        raw = script.string or script.get_text()

        if not raw:
            continue

        raw = raw.strip()

        try:
            data = json.loads(raw)

            if isinstance(data, list):
                blocks.extend(data)
            else:
                blocks.append(data)

        except Exception:
            continue

    return blocks


def find_product_jsonld(jsonld):
    for item in jsonld:

        if not isinstance(item, dict):
            continue

        item_type = item.get("@type")

        if item_type == "Product":
            return item

        if isinstance(item_type, list) and "Product" in item_type:
            return item

    return {}


# =============================================================================
# PRICE HELPERS
# =============================================================================

def clean_value(value):
    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return ""

    return str(value).strip()


def extract_price(product):
    offers = product.get("offers")

    if isinstance(offers, list):
        offers = offers[0] if offers else {}

    if not isinstance(offers, dict):
        return "", ""

    price = clean_value(offers.get("price"))

    low_price = clean_value(offers.get("lowPrice"))

    return price, low_price


# =============================================================================
# REVIEW COUNT
# =============================================================================

def extract_review_count(product, soup, html_content):
    """
    Primary:
        JSON-LD aggregateRating.reviewCount

    Fallback:
        Search page HTML for review-count patterns.
    """

    aggregate = product.get("aggregateRating")

    if isinstance(aggregate, dict):

        count = (
            aggregate.get("reviewCount")
            or aggregate.get("ratingCount")
        )

        if count is not None:
            return str(count)

    patterns = [
        r'"reviewCount"\s*:\s*"?(\\d+)"?',
        r'"review_count"\s*:\s*"?(\\d+)"?',
        r'"ratingCount"\s*:\s*"?(\\d+)"?',
        r'"reviewcount"\s*:\s*"?(\\d+)"?',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html_content,
            re.I
        )

        if match:
            return match.group(1)

    return ""


# =============================================================================
# STAR COUNTS
# =============================================================================

def extract_star_counts(html_content):
    """
    Calvin Klein's downloaded PDP HTML did not expose reliable
    1-5 star counts in the tested GET response.

    We therefore only populate these fields if explicit values
    can be found in the HTML/embedded JSON.
    """

    result = {
        "1_star": "",
        "2_star": "",
        "3_star": "",
        "4_star": "",
        "5_star": "",
    }

    patterns = {
        "1_star": [
            r'"1_star"\s*:\s*"?(\\d+)"?',
            r'"oneStar"\s*:\s*"?(\\d+)"?',
        ],
        "2_star": [
            r'"2_star"\s*:\s*"?(\\d+)"?',
            r'"twoStar"\s*:\s*"?(\\d+)"?',
        ],
        "3_star": [
            r'"3_star"\s*:\s*"?(\\d+)"?',
            r'"threeStar"\s*:\s*"?(\\d+)"?',
        ],
        "4_star": [
            r'"4_star"\s*:\s*"?(\\d+)"?',
            r'"fourStar"\s*:\s*"?(\\d+)"?',
        ],
        "5_star": [
            r'"5_star"\s*:\s*"?(\\d+)"?',
            r'"fiveStar"\s*:\s*"?(\\d+)"?',
        ],
    }

    for field, field_patterns in patterns.items():

        for pattern in field_patterns:

            match = re.search(
                pattern,
                html_content,
                re.I
            )

            if match:
                result[field] = match.group(1)
                break

    return result


# =============================================================================
# REVIEW URL
# =============================================================================

def find_review_url(html_content):
    candidate = (
        f"{BASE_URL}/on/demandware.store/"
        f"Sites-PVHCKUS-Site/en_US/Adyen-CheckoutReview"
    )

    if "Adyen-CheckoutReview" in html_content:
        return candidate

    return ""


# =============================================================================
# PDP PARSER
# =============================================================================

def parser_get(session, url, depth=1):
    global parser_success
    global parser_failure

    request_number = len(parser_requests) + 1

    try:

        response = session.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

        parser_requests.append({
            "number": request_number,
            "url": url,
            "status": response.status_code,
            "depth": depth,
            "size": len(response.content)
        })

        parser_depths.append(depth)

        if response.status_code == 200:
            parser_success += 1
        else:
            parser_failure += 1

        return response

    except Exception as e:

        parser_failure += 1

        parser_requests.append({
            "number": request_number,
            "url": url,
            "status": None,
            "depth": depth,
            "size": 0,
            "error": str(e)
        })

        parser_depths.append(depth)

        log(f"[PARSER ERROR] {url} -> {e}")

        return None


def parse_product(session, url, index, total):
    log()
    separator()
    log(f"PRODUCT {index}/{total}")
    separator()

    log()
    log(f"[PDP PARSER REQUEST #{len(parser_requests) + 1}]")
    log(f"[DEPTH] 1")
    log(f"[URL] {url}")

    response = parser_get(session, url, depth=1)

    if response is None:
        log("[PDP] FAILED")
        return None

    log(f"[STATUS] {response.status_code}")
    log(f"[SIZE] {len(response.content):,} bytes")
    log(f"[FINAL URL] {response.url}")

    if response.status_code != 200:
        log("[PDP] FAILED HTTP STATUS")
        return None

    html_content = response.text

    soup = BeautifulSoup(
        html_content,
        "html.parser"
    )

    jsonld = get_jsonld(soup)

    product = find_product_jsonld(jsonld)

    name = clean_value(product.get("name"))
    sku = clean_value(
        product.get("sku")
        or product.get("mpn")
        or product.get("productID")
    )

    brand = product.get("brand", "")

    if isinstance(brand, dict):
        brand = brand.get("name", "")

    brand = clean_value(brand)

    sale_price, low_price = extract_price(product)

    # Try visible price fallbacks.
    if not sale_price:

        price_selectors = [
            "[data-testid='price']",
            ".price",
            ".sales",
            ".product-price",
        ]

        for selector in price_selectors:

            node = soup.select_one(selector)

            if node:

                text = " ".join(node.stripped_strings)

                match = re.search(
                    r"\$?\s*([0-9]+(?:\.[0-9]{2})?)",
                    text
                )

                if match:
                    sale_price = match.group(1)
                    break

    original_price = ""

    # Look for compare-at/original price in JSON.
    if isinstance(product.get("offers"), dict):

        offers = product["offers"]

        original_price = clean_value(
            offers.get("highPrice")
            or offers.get("listPrice")
            or offers.get("originalPrice")
        )

    category = ""

    breadcrumbs = []

    for item in soup.select(
        "nav.breadcrumb a, "
        ".breadcrumb a, "
        "[aria-label='breadcrumb'] a"
    ):

        text = " ".join(item.stripped_strings)

        if text:
            breadcrumbs.append(text)

    if breadcrumbs:
        category = " > ".join(breadcrumbs)

    if not category:

        category_value = product.get("category")

        if isinstance(category_value, list):
            category = " > ".join(
                str(x) for x in category_value
            )

        else:
            category = clean_value(category_value)

    if not category:

        path_parts = urlparse(url).path.split("/")

        path_parts = [
            x for x in path_parts
            if x and x.lower() not in ["en", "women", "apparel"]
        ]

        if path_parts:

            category = (
                "Women > Apparel > "
                + " > ".join(
                    x.replace("-", " ").title()
                    for x in path_parts[:-1]
                )
            )

    total_reviews = extract_review_count(
        product,
        soup,
        html_content
    )

    star_counts = extract_star_counts(
        html_content
    )

    review_url = find_review_url(
        html_content
    )

    record = {
        "url": url,
        "product_sku": sku,
        "product_name": name,
        "brand": brand,
        "original_price": original_price,
        "sale_price": sale_price,
        "category": category,
        "total_number_of_reviews": total_reviews,

        "1_star": star_counts["1_star"],
        "2_star": star_counts["2_star"],
        "3_star": star_counts["3_star"],
        "4_star": star_counts["4_star"],
        "5_star": star_counts["5_star"],

        "date_of_purchase": "",
        "place_of_purchase": "",
        "review_title": "",
        "review_text": "",

        "review_url": review_url,
    }

    log()
    log("PRODUCT DETAILS")
    log(f"URL                : {record['url']}")
    log(f"Product Name       : {record['product_name']}")
    log(f"SKU                : {record['product_sku']}")
    log(f"Brand              : {record['brand']}")
    log(f"Original Price     : {record['original_price']}")
    log(f"Sale Price         : {record['sale_price']}")
    log(f"Category           : {record['category']}")
    log(f"Total Reviews      : {record['total_number_of_reviews']}")
    log(f"1 Star             : {record['1_star']}")
    log(f"2 Star             : {record['2_star']}")
    log(f"3 Star             : {record['3_star']}")
    log(f"4 Star             : {record['4_star']}")
    log(f"5 Star             : {record['5_star']}")
    log(f"Date of Purchase   : {record['date_of_purchase']}")
    log(f"Place of Purchase  : {record['place_of_purchase']}")
    log(f"Review Title       : {record['review_title']}")
    log(f"Review Text        : {record['review_text']}")

    if review_url:
        log()
        log(f"REVIEW URL: {review_url}")

    return record


# =============================================================================
# CSV
# =============================================================================

CSV_FIELDS = [
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
    "date_of_purchase",
    "place_of_purchase",
    "review_title",
    "review_text",
    "review_url",
]


def save_csv():
    with open(
        OUTPUT_CSV,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=CSV_FIELDS
        )

        writer.writeheader()

        for row in records:
            writer.writerow(row)

    log()
    log(f"[CSV SAVED] {OUTPUT_CSV}")


# =============================================================================
# MAIN CRAWLER
# =============================================================================

def main():

    global category_pages

    # Clear previous log.
    LOG_FILE.write_text(
        "",
        encoding="utf-8"
    )

    separator()

    log("CALVIN KLEIN - WOMEN FULL PRODUCT CRAWLER")

    separator()

    log(f"START URL       : {CATEGORY_URL}")
    log(f"METHOD          : GET")
    log(f"SCOPE           : WOMEN ONLY")
    log(f"BATCH SIZE      : {BATCH_SIZE}")
    log(f"PRODUCT LIMIT   : UNLIMITED")
    log(f"SEED HTML       : {SEED_HTML}")

    separator()

    session = requests.Session()

    session.headers.update(HEADERS)

    # =========================================================================
    # STEP 1 - LOAD SAVED FIRST PAGE
    # =========================================================================

    if SEED_HTML.exists():

        log()
        log("[SEED] Reading previously downloaded HTML")
        log(f"[SEED FILE] {SEED_HTML}")

        first_html = SEED_HTML.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        first_products = extract_product_urls(
            first_html
        )

        products_discovered.update(
            first_products
        )

        category_pages += 1

        log(
            f"[SEED PRODUCTS] "
            f"{len(first_products)}"
        )

    else:

        log()
        log("[SEED] HTML file not found.")
        log("[SEED] Downloading first category page using GET.")

        response = crawler_get(
            session,
            CATEGORY_URL,
            depth=0
        )

        if response is None:
            log("Initial category request failed.")
            return

        first_html = response.text

        first_products = extract_product_urls(
            first_html
        )

        products_discovered.update(
            first_products
        )

        category_pages += 1

    log(
        f"[TOTAL UNIQUE PRODUCTS] "
        f"{len(products_discovered)}"
    )

    # =========================================================================
    # STEP 2 - PAGINATION
    # =========================================================================

    start = BATCH_SIZE

    consecutive_empty_pages = 0

    while True:

        pagination_url = build_pagination_url(
            start
        )

        log()
        separator("-")
        log(f"[PAGINATION] START = {start}")
        log(f"[PAGINATION URL] {pagination_url}")
        separator("-")

        response = crawler_get(
            session,
            pagination_url,
            depth=0
        )

        if response is None:

            log(
                "[PAGINATION] Request failed. "
                "Stopping crawler."
            )

            break

        if response.status_code != 200:

            log(
                "[PAGINATION] HTTP failure. "
                "Stopping crawler."
            )

            break

        page_html = response.text

        page_products = extract_product_urls(
            page_html
        )

        old_count = len(products_discovered)

        products_discovered.update(
            page_products
        )

        new_count = (
            len(products_discovered)
            - old_count
        )

        category_pages += 1

        log(
            f"[PAGINATION] Products on this page : "
            f"{len(page_products)}"
        )

        log(
            f"[PAGINATION] New unique products   : "
            f"{new_count}"
        )

        log(
            f"[PAGINATION] Total unique products : "
            f"{len(products_discovered)}"
        )

        # No products means the catalogue has ended.
        if not page_products:

            log()
            log(
                "[PAGINATION FINISHED] "
                "No products returned."
            )

            break

        # If page returns only duplicates, we've reached
        # the end of the available product catalogue.
        if new_count == 0:

            consecutive_empty_pages += 1

        else:

            consecutive_empty_pages = 0

        if consecutive_empty_pages >= 2:

            log()
            log(
                "[PAGINATION FINISHED] "
                "Two consecutive pages returned no new products."
            )

            break

        start += BATCH_SIZE

        time.sleep(
            REQUEST_DELAY
        )

    # =========================================================================
    # STEP 3 - BLOCKING CHECK FOR CATEGORY/PAGINATION URLS
    # =========================================================================

    log()
    separator()
    log("BLOCKING CHECK")
    separator()

    # Check every URL that was actually requested by crawler.
    for item in crawler_requests:

        check_blocking_url(
            session,
            item["url"]
        )

    # =========================================================================
    # STEP 4 - PARSE ALL PRODUCTS UNTIL FINISHED
    # =========================================================================

    product_urls = sorted(
        products_discovered
    )

    total_products = len(product_urls)

    log()
    separator()
    log("STARTING PRODUCT PARSING")
    log(f"TOTAL UNIQUE PRODUCTS : {total_products}")
    separator()

    for index, product_url in enumerate(
        product_urls,
        start=1
    ):

        if product_url in products_scraped:
            continue

        record = parse_product(
            session,
            product_url,
            index,
            total_products
        )

        if record:

            records.append(
                record
            )

            products_scraped.add(
                product_url
            )

            # Check PDP blocking after actual parser request.
            check_blocking_url(
                session,
                product_url
            )

        save_csv()

        time.sleep(
            REQUEST_DELAY
        )

    # =========================================================================
    # STEP 5 - FINAL METRICS
    # =========================================================================

    crawler_total = len(crawler_requests)

    parser_total = len(parser_requests)

    crawler_success_rate = (
        crawler_success / crawler_total * 100
        if crawler_total
        else 0
    )

    crawler_failure_rate = (
        crawler_failure / crawler_total * 100
        if crawler_total
        else 0
    )

    parser_success_rate = (
        parser_success / parser_total * 100
        if parser_total
        else 0
    )

    parser_failure_rate = (
        parser_failure / parser_total * 100
        if parser_total
        else 0
    )

    blocking_total = len(
        blocking_checked_urls
    )

    blocking_success_rate = (
        blocking_success / blocking_total * 100
        if blocking_total
        else 0
    )

    blocking_failure_rate = (
        blocking_failure / blocking_total * 100
        if blocking_total
        else 0
    )

    max_crawler_depth = (
        max(crawler_depths)
        if crawler_depths
        else 0
    )

    max_parser_depth = (
        max(parser_depths)
        if parser_depths
        else 0
    )

    # =========================================================================
    # FINAL FEASIBILITY REPORT
    # =========================================================================

    log()
    separator()
    log("FINAL FEASIBILITY REPORT")
    separator()

    log()
    log(f"Record count             : {len(records)}")
    log(f"Request count            : {crawler_total + parser_total}")
    log(f"Crawler request count    : {crawler_total}")
    log(f"Parser request count     : {parser_total}")
    log(f"Requests depth           : {max(max_crawler_depth, max_parser_depth)}")
    log(f"Crawler maximum depth    : {max_crawler_depth}")
    log(f"Parser maximum depth     : {max_parser_depth}")
    log(f"Category pages crawled   : {category_pages}")
    log(f"Unique products found    : {len(products_discovered)}")
    log(f"Products scraped         : {len(records)}")
    log(f"Failed crawler requests  : {crawler_failure}")
    log(f"Failed parser requests   : {parser_failure}")
    log(f"CSV records              : {len(records)}")
    log(f"CSV file                 : {OUTPUT_CSV}")

    # =========================================================================
    # CRAWLER BLOCKING
    # =========================================================================

    log()
    separator()
    log("Crawler Blocking:")
    log(f"total_requests: {crawler_total}")
    log(
        f"success_rate_percent: "
        f"{crawler_success_rate:.1f}"
    )
    log(
        f"failure_rate_percent: "
        f"{crawler_failure_rate:.1f}"
    )

    # =========================================================================
    # PARSER BLOCKING
    # =========================================================================

    log()
    separator()
    log("Parser Blocking:")
    log(f"total_requests: {parser_total}")
    log(
        f"success_rate_percent: "
        f"{parser_success_rate:.1f}"
    )
    log(
        f"failure_rate_percent: "
        f"{parser_failure_rate:.1f}"
    )

    # =========================================================================
    # BLOCK CHECK
    # =========================================================================

    log()
    separator()
    log("Block Checked URLs:")
    log(f"count: {blocking_total}")
    log(
        f"success_rate_percent: "
        f"{blocking_success_rate:.1f}"
    )
    log(
        f"failure_rate_percent: "
        f"{blocking_failure_rate:.1f}"
    )

    # =========================================================================
    # FINAL SCOPE
    # =========================================================================

    log()
    separator()
    log("CRAWLER SCOPE")
    separator()

    log("REQUEST METHOD      : GET")
    log("PRODUCT SCOPE       : WOMEN ONLY")
    log("PRODUCT LIMIT       : UNLIMITED")
    log("PAGINATION          : Search-UpdateGrid")
    log("PAGINATION SIZE     : 16")
    log("DEDUPLICATION       : CANONICAL PRODUCT URL")
    log("TRACKING PARAMETER  : REMOVED")
    log(f"OUTPUT              : {OUTPUT_CSV}")

    separator()
    log("DONE.")


# =============================================================================
# RUN
# =============================================================================

if __name__ == "__main__":
    main()