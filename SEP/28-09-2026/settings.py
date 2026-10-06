"""Configuration for the MSC Direct Camoufox scraper.

Only values live here - no crawling or parsing logic.
"""

BASE_URL = "https://www.mscdirect.com"
START_URL = "https://www.mscdirect.com/"

PRODUCT_URL_TOKEN = "/product/details/"

PRODUCT_LIMIT = 120

LISTING_URLS = (
    "https://www.mscdirect.com/browse/Hand-Tools?navid=2102364",
    "https://www.mscdirect.com/browse/tn?searchterm=hand%20cleaner",
    "https://www.mscdirect.com/browse/Power-Tools?navid=2107244",
    "https://www.mscdirect.com/browse/Janitorial-Facility-Maintenance?navid=2106462",
    "https://www.mscdirect.com/browse/tn?searchterm=drill%20bit",
    "https://www.mscdirect.com/browse/Abrasives?navid=2100008",
    "https://www.mscdirect.com/browse/Fasteners?navid=2108705",
    "https://www.mscdirect.com/browse/Holemaking?navid=2106067",
    "https://www.mscdirect.com/browse/Measuring-Inspecting?navid=2107563",
    "https://www.mscdirect.com/browse/Safety?navid=2106309",
    "https://www.mscdirect.com/browse/Saw-Blades?navid=2105933",
    "https://www.mscdirect.com/browse/Threading?navid=2105963",
    "https://www.mscdirect.com/browse/Turning-Boring?navid=2105881",
    "https://www.mscdirect.com/browse/Material-Handling-Storage?navid=2105165",
    "https://www.mscdirect.com/browse/Lubricants-Coolants-Fluids?navid=2107390",
)

HEADLESS = False
BLOCK_IMAGES = False
HUMANIZE = False

PAGE_LOAD_TIMEOUT_MS = 90000
SELECTOR_TIMEOUT_MS = 60000
EXTRA_SELECTOR_TIMEOUT_MS = 8000
HOME_WAIT_MS = 8000
LISTING_WAIT_MS = 6000
DETAIL_SETTLE_MS = 1200
RETRY_WAIT_MS = 4000
MAX_PAGE_RETRIES = 2

DELAY_BETWEEN_PAGES_MS = (700, 1600)

BLOCK_PAGE_MARKERS = (
    "access denied",
    "pardon our interruption",
    "are you a human",
    "captcha",
    "unusual traffic",
    "request blocked",
    "verify you are a human",
    "security check",
)

OUTPUT_CSV = "msc_products.csv"

