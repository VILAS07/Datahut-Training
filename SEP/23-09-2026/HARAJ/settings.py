# =========================================================
# HARAj SCRAPER SETTINGS
# =========================================================

# Main starting page
START_URL = "https://haraj.com.sa/en/"


# Base URL
BASE_URL = "https://haraj.com.sa"


# Browser headers
HEADERS = {

    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),

    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),

    "Accept-Language": (
        "en-US,en;q=0.9"
    ),

    "Connection": "keep-alive",
}


# Request timeout
REQUEST_TIMEOUT = 60


# Output file
OUTPUT_FILE = "output.csv"