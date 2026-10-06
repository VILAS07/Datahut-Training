KEYWORDS = [
    "mini dress",
    "midi dress",
    "maxi dress",
    "summer dress",
    "knitted dress",
    "wide leg jeans",
    "straight leg jeans",
    "skinny jeans",
    "flared jeans",
    "high waist jeans",
    "fine-knit jumper",
    "fine-knit cardigan",
    "turtleneck jumper",
    "oversized jumper",
    "knitted top",
    "crop top",
    "tank top",
    "vest top",
    "long sleeve top",
]

PRODUCTS_PER_KEYWORD = 10

BASE_URL = "https://www.next.co.uk"

SEARCH_URL = BASE_URL + "/search?w={}"

HEADLESS = False

SEARCH_WAIT = 5000

PDP_WAIT = 3000

OUTPUT_FILE = "next_products.csv"