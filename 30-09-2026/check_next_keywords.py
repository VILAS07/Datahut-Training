from camoufox.sync_api import Camoufox
from urllib.parse import quote

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

with Camoufox(headless=False) as browser:
    page = browser.new_page()

    for keyword in KEYWORDS:
        url = f"https://www.next.co.uk/search?w={quote(keyword)}"

        print(f"\nChecking: {keyword}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        # Find the result count from the page heading
        text = page.locator("body").inner_text()

        import re

        pattern = rf'"{re.escape(keyword.upper())}"\s*\((\d+)\)'
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            record_count = match.group(1)
        else:
            record_count = "NOT FOUND"

        # Product cards currently loaded
        product_cards = page.locator(
            '[data-testid="product_summary_image_media"]'
        ).count()

        print(f"Record Count : {record_count}")
        print(f"Loaded Cards : {product_cards}")
        print(f"Request Count: 1")
        print(f"Request Depth: 1")

    browser.close()