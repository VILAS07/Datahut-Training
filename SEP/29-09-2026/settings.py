"""Configuration for the John Lewis scraper."""

MONGO_URI = "mongodb://localhost:27017/"
MONGO_DATABASE = "johnlewis_db"
MONGO_COLLECTION = "products"

CATEGORY_URLS = [
    "https://www.johnlewis.com/browse/men/mens-coats-jackets/_/N-ea9",
]

HEADLESS = True

BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]

PAGE_TIMEOUT = 60000

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)

MAX_PRODUCTS = None