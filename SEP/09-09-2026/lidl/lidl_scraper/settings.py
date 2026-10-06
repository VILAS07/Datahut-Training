BOT_NAME = "lidl_scraper"

SPIDER_MODULES = [
    "lidl_scraper.spiders"
]

NEWSPIDER_MODULE = (
    "lidl_scraper.spiders"
)


# ==========================================================
# ROBOTS
# ==========================================================

ROBOTSTXT_OBEY = False


# ==========================================================
# REQUEST SETTINGS
# ==========================================================

CONCURRENT_REQUESTS = 2

CONCURRENT_REQUESTS_PER_DOMAIN = 2

DOWNLOAD_DELAY = 1.0


# ==========================================================
# AUTOTHROTTLE
# ==========================================================

AUTOTHROTTLE_ENABLED = True

AUTOTHROTTLE_START_DELAY = 1.0

AUTOTHROTTLE_MAX_DELAY = 5.0

AUTOTHROTTLE_TARGET_CONCURRENCY = 1.5


# ==========================================================
# RETRIES
# ==========================================================

RETRY_ENABLED = True

RETRY_TIMES = 2


# ==========================================================
# DOWNLOAD
# ==========================================================

DOWNLOAD_TIMEOUT = 30


# ==========================================================
# USER AGENT
# ==========================================================

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


# ==========================================================
# REQUEST HEADERS
# ==========================================================

DEFAULT_REQUEST_HEADERS = {
    "Accept": (
        "text/html,"
        "application/xhtml+xml,"
        "application/xml;q=0.9,"
        "*/*;q=0.8"
    ),
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
}


# ==========================================================
# CSV OUTPUT
# ==========================================================

FEEDS = {
    "output/lidl_products.csv": {
        "format": "csv",
        "encoding": "utf8",
        "overwrite": True,
        "store_empty": False,
    }
}


# ==========================================================
# PIPELINES
# ==========================================================

ITEM_PIPELINES = {
    "lidl_scraper.pipelines.DedupeByUrlPipeline": 100,
    "lidl_scraper.pipelines.RequiredFieldsPipeline": 200,
}


# ==========================================================
# LOGGING
# ==========================================================

LOG_LEVEL = "INFO"

LOG_FILE = "logs/lidl_run.log"