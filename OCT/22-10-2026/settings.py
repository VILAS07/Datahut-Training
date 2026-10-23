from datetime import datetime
import calendar
import logging
import pytz

from curl_cffi import requests as cffi_requests  # curl based, browser TLS fingerprint

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# basic details
PROJECT = "zalando"
CLIENT_NAME = ""
PROJECT_NAME = "zalando_uk"
FREQUENCY = ""
BASE_URL = "https://www.zalando.co.uk"

# top level categories (start points)
START_URLS = {
    "Women": f"{BASE_URL}/women-home/",
    "Men": f"{BASE_URL}/men-home/",      # verify
    "Kids": f"{BASE_URL}/kids-home/",    # verify
}

datetime_obj = datetime.now(pytz.timezone("Asia/Kolkata"))

iteration = datetime_obj.strftime("%Y_%m_%d")
YEAR = datetime_obj.strftime("%Y")
MONTH = datetime_obj.strftime("%m")
DAY = datetime_obj.strftime("%d")
MONTH_VALUE = calendar.month_abbr[int(MONTH.lstrip("0"))]
WEEK = (int(DAY) - 1) // 7 + 1
EXTRACTION_DATE = datetime_obj.strftime("%Y-%m-%d")

OUTPUT_DIR = "output"
FILE_NAME = f"{OUTPUT_DIR}/zalando_{iteration}.csv"
SNAPSHOT_DIR = f"{OUTPUT_DIR}/product_html_{iteration}"

# output files (no database - csv only)
CATEGORY_FILE = f"{OUTPUT_DIR}/category_urls.csv"
SUBCATEGORY_FILE = f"{OUTPUT_DIR}/subcategory_urls.csv"
PRODUCT_URL_FILE = f"{OUTPUT_DIR}/product_urls.csv"
DONE_FILE = f"{OUTPUT_DIR}/done_pages.csv"        # resume support
FAILED_FILE = f"{OUTPUT_DIR}/failed_urls.csv"

# proxy (UK proxy recommended)
PROXY = ""
PROXIES = {"http": f"http://{PROXY}", "https": f"http://{PROXY}"} if PROXY else None

# pagination
PAGE_PARAM = "p"          # listing pages use ?p=2
MAX_PAGES = 200           # safety cap (site shows ~94 pages max per listing)
RETRIES = 5
MAX_DELAY = 30            # adaptive delay never goes above this (seconds)
DELAY = 3                 # base seconds between requests (random jitter added)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Priority": "u=0, i",
}

# CSV columns
FILE_HEADERS = [
    "extraction_date", "website", "category", "subcategory", "gender", "product_type", "product_url",
    "product_name", "brand", "sku", "colour", "currency", "selling_price",
    "regular_price", "percentage_discount", "badge", "availability", "sizes",
    "rating", "review_count", "description", "material_and_care", "details", "size_and_fit", "fit", "occasion_style",
    "breadcrumbs", "images",
]


_current_delay = DELAY  # adaptive: grows after 429/timeouts, shrinks back after successes


def get_response(url, headers=None, retries=RETRIES):
    """GET with retry + adaptive backoff (429 / timeouts). Returns response or None."""
    global _current_delay
    from random import uniform
    from time import sleep
    for attempt in range(1, retries + 1):
        try:
            response = cffi_requests.get(
                url, headers=headers or HEADERS, proxies=PROXIES,
                impersonate="chrome", timeout=40)
            if response.status_code == 200:
                sleep(_current_delay + uniform(0, 1.5))
                _current_delay = max(DELAY, _current_delay * 0.9)  # recover slowly
                return response
            logging.warning(f"{response.status_code} for {url} (try {attempt})")
            if response.status_code == 404:
                return None
            if response.status_code in (403, 429):
                _current_delay = min(_current_delay * 1.5, MAX_DELAY)  # slow down for everything after
                sleep(30 * attempt)
                continue
        except Exception as e:
            logging.warning(f"{e} for {url} (try {attempt})")
            _current_delay = min(_current_delay * 1.3, MAX_DELAY)
        sleep(attempt * 5)
    return None