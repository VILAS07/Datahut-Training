from datetime import datetime
import logging
import pytz

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# basic details
PROJECT = "fragrantica"
CLIENT_NAME = ""
PROJECT_NAME = "fragrantica"
FREQUENCY = "one_time"
BASE_URL = "https://www.fragrantica.fr"
WEBSITE = "Fragrantica"

datetime_obj = datetime.now(pytz.timezone("Asia/Kolkata"))
iteration = datetime_obj.strftime("%Y_%m_%d")
EXTRACTION_DATE = datetime_obj.strftime("%Y-%m-%d")

FILE_NAME = f"fragrantica_{iteration}"
FILE_NAME_PRODUCTS = "fragrantica_products.csv"   # no date in the name, so a re-run resumes
FILE_NAME_REVIEWS = "fragrantica_reviews.csv"
USE_MONGO = False   # False = write straight to the csv files (no MongoDB needed)

# Mongo db and collections
MONGO_URI = "mongodb://localhost:27017"
MONGO_MOCK = False   # True = in-memory fake Mongo (pip install mongomock) for a quick test without a server
MONGO_DB = f"fragrantica_{iteration}"
MONGO_COL_URL = f"{PROJECT_NAME}_url"
MONGO_COL_URL_FAILED = f"{PROJECT_NAME}_url_failed"
MONGO_COLLECTION_DATA = f"{PROJECT_NAME}_data"

# crawler (Algolia) details
ALGOLIA_APP_ID = "FGVI612DFZ"
ALGOLIA_KEY = "M2Y3M2M0YmEwYWExZDQyOTk0YWNiNTNmMmRlYWI5YWRkYjk1ZTA4ZmY3Y2NlOGJiMTZhMjU1OTJiMjRkMWFlZHZhbGlkVW50aWw9MTc5NDIxNzI4Ng=="
ALGOLIA_INDEX = "fragrantica_perfumes"
URLS_FILE = "urls.csv"          # written by crawler.py: id,pdp_url

# proxy (leave empty for none)
PROXY = ""
PROXIES = {"http": f"http://{PROXY}", "https": f"http://{PROXY}"} if PROXY else None

# request details
DELAY = 10           # seconds between product page requests (grows by itself after a 429)
COOLDOWN = 180       # first wait after a 429; each next wait is longer (180, 360, 540 ... max 1800)
MAX_COOLDOWNS = 10   # after this many cooldowns in a row the parser stops (exit code 2)
RETRIES = 4
TIMEOUT = 40
FETCH_AMAZON_PRICE = True

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}

SHARD_COLLECTION = [
    {'col': MONGO_COL_URL, 'unique': True, 'indexfield': "url"},
]

# CSV headers: one row per product
FILE_HEADERS = [
    "website",
    "extraction_date",
    "product_id",
    "pdp_url",
    "product_name",
    "brand",
    "brand_url",
    "brand_logo",
    "gender",
    "launch_year",
    "fragrance_family",
    "perfumer",
    "description",
    "main_image",
    "main_accords",
    "top_notes",
    "middle_notes",
    "base_notes",
    "rating_value",
    "rating_count",
    "review_count",
    "reviews_scraped",
    "also_like",
    "amazon_title",
    "amazon_price",
    "amazon_currency",
    "amazon_url",
]

# CSV headers: one row per review
REVIEW_HEADERS = [
    "website",
    "extraction_date",
    "product_id",
    "pdp_url",
    "product_name",
    "review_id",
    "reviewer",
    "reviewer_url",
    "review_date",
    "review_datetime_text",
    "review_text",
    "reviewer_rating",
    "winter",
    "spring",
    "summer",
    "autumn",
    "day",
    "night",
    "longevity",
    "sillage",
    "gender",
    "relation",
]