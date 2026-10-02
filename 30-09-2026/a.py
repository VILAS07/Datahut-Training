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

    checked = 0
    blocked = 0

    for keyword in KEYWORDS:
        url = f"https://www.next.co.uk/search?w={quote(keyword)}"

        print(f"\nChecking: {keyword}")
        print(f"URL: {url}")

        try:
            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            page.wait_for_timeout(3000)

            status = response.status if response else "UNKNOWN"
            title = page.title()

            checked += 1

            if status == 200 and "Access Denied" not in title:
                print(f"STATUS: {status}")
                print("RESULT: ACCESSIBLE")
            else:
                blocked += 1
                print(f"STATUS: {status}")
                print("RESULT: BLOCKED")

        except Exception as e:
            checked += 1
            blocked += 1
            print("RESULT: BLOCKED / ERROR")
            print(f"ERROR: {e}")

    print("\n==============================")
    print(f"URLs CHECKED : {checked}")
    print(f"URLs BLOCKED : {blocked}")
    print(f"URLs ACCESSIBLE : {checked - blocked}")
    print("==============================")

    