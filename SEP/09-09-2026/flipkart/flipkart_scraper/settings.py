BOT_NAME = "flipkart_scraper"

SPIDER_MODULES = ["flipkart_scraper.spiders"]
NEWSPIDER_MODULE = "flipkart_scraper.spiders"


# ==========================================================
# ROBOTS
# ==========================================================

ROBOTSTXT_OBEY = False


# ==========================================================
# SCRAPY-PLAYWRIGHT
# ==========================================================

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

TWISTED_REACTOR = (
    "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
)

PLAYWRIGHT_BROWSER_TYPE = "chromium"

PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ],
}

PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 90_000


# ==========================================================
# REQUEST SETTINGS
# ==========================================================

# Serial requests to reduce load and avoid aggressive traffic.

CONCURRENT_REQUESTS = 1

CONCURRENT_REQUESTS_PER_DOMAIN = 1

DOWNLOAD_DELAY = 1.5

AUTOTHROTTLE_ENABLED = False


# ==========================================================
# SCRAPER LIMITS
# ==========================================================

# No item-count limit.
# The spider will continue pagination until no new products
# are found.

# Maximum runtime: 60 minutes.
CLOSESPIDER_TIMEOUT = 3600


# ==========================================================
# RETRIES
# ==========================================================

RETRY_ENABLED = True

RETRY_TIMES = 2


# ==========================================================
# CSV OUTPUT
# ==========================================================

FEEDS = {
    "output/flipkart_products.csv": {
        "format": "csv",
        "encoding": "utf8",
        "overwrite": True,
        "store_empty": False,
    }
}


# ==========================================================
# USER AGENT
# ==========================================================

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


# ==========================================================
# REQUEST HEADERS
# ==========================================================

DEFAULT_REQUEST_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
}


# ==========================================================
# ITEM PIPELINES
# ==========================================================

ITEM_PIPELINES = {
    "flipkart_scraper.pipelines.DedupeByUrlPipeline": 100,
    "flipkart_scraper.pipelines.RequiredFieldsPipeline": 200,
}


# ==========================================================
# LOGGING
# ==========================================================

LOG_LEVEL = "INFO"

LOG_FILE = "logs/flipkart_run.log"


# ==========================================================
# REQUEST FINGERPRINT
# ==========================================================

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"