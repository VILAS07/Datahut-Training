from playwright.sync_api import sync_playwright
from urllib.parse import quote
import re
import time


BASE_URL = "https://shop.mango.com/gb/en"

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


def get_search_url(keyword):
    return f"{BASE_URL}/search/women/q/{quote(keyword)}"


def check_keyword(page, keyword):

    url = get_search_url(keyword)

    print()
    print("=" * 70)
    print(f"Checking: {keyword}")
    print(f"URL: {url}")
    print("=" * 70)

    try:
        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(5000)

        status = response.status if response else None

        print("STATUS:", status)
        print("FINAL URL:", page.url)
        print("TITLE:", page.title())

        # -------------------------------------------------
        # BODY TEXT
        # -------------------------------------------------

        body_text = page.locator("body").inner_text(
            timeout=15000
        )

        # -------------------------------------------------
        # RECORD COUNT
        # -------------------------------------------------

        record_count = "NOT FOUND"

        patterns = [
            r"(\d[\d.,]*)\s+results?",
            r"(\d[\d.,]*)\s+items?",
            r"(\d[\d.,]*)\s+products?",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                body_text,
                re.IGNORECASE
            )

            if match:
                record_count = match.group(1)
                break

        print("RECORD COUNT:", record_count)

        # -------------------------------------------------
        # FIND PRODUCT LINKS
        # -------------------------------------------------

        links = page.locator("a[href]")

        product_urls = []

        for i in range(min(links.count(), 2000)):

            try:

                href = links.nth(i).get_attribute(
                    "href"
                )

                if not href:
                    continue

                href_lower = href.lower()

                # Mango product URLs commonly contain
                # /p/ or /products/
                if "/p/" in href_lower or "/products/" in href_lower:

                    if href.startswith("/"):
                        href = "https://shop.mango.com" + href

                    href = href.split("?")[0]

                    if href not in product_urls:
                        product_urls.append(href)

            except Exception:
                continue

        print(
            "PRODUCT LINKS FOUND:",
            len(product_urls)
        )

        # -------------------------------------------------
        # SHOW FIRST 10 PRODUCT URLS
        # -------------------------------------------------

        print()
        print("FIRST PRODUCT URLS:")

        for index, product_url in enumerate(
            product_urls[:10],
            start=1
        ):

            print(
                f"{index}. {product_url}"
            )

        # -------------------------------------------------
        # IMAGE URLS
        # -------------------------------------------------

        images = page.locator("img")

        image_count = images.count()

        print()
        print(
            "IMAGE ELEMENTS:",
            image_count
        )

        # -------------------------------------------------
        # REQUEST INFORMATION
        # -------------------------------------------------

        print()
        print("REQUEST COUNT: 1")
        print("REQUEST DEPTH: 1")

        # -------------------------------------------------
        # BLOCK CHECK
        # -------------------------------------------------

        blocked = False

        blocked_text = [
            "access denied",
            "forbidden",
            "captcha",
            "verify you are human",
            "blocked",
            "unusual traffic",
        ]

        body_lower = body_text.lower()

        for text in blocked_text:

            if text in body_lower:
                blocked = True
                break

        if status and status >= 400:
            blocked = True

        if blocked:

            print("RESULT: BLOCKED")

        else:

            print("RESULT: ACCESSIBLE")

        return {
            "keyword": keyword,
            "url": url,
            "status": status,
            "record_count": record_count,
            "product_links": len(product_urls),
            "blocked": blocked,
        }

    except Exception as error:

        print(
            "ERROR:",
            error
        )

        return {
            "keyword": keyword,
            "url": url,
            "status": "ERROR",
            "record_count": "NOT FOUND",
            "product_links": 0,
            "blocked": True,
        }


def main():

    results = []

    with sync_playwright() as playwright:

        print("Launching Playwright...")

        browser = playwright.chromium.launch(
            headless=False
        )

        page = browser.new_page(
            viewport={
                "width": 1366,
                "height": 900
            },
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0.0.0 "
                "Safari/537.36"
            ),
        )

        for keyword in KEYWORDS:

            result = check_keyword(
                page,
                keyword
            )

            results.append(result)

            # Small cooldown between searches
            print()
            print("Cooldown: 3 seconds...")
            time.sleep(3)

        browser.close()

    # =====================================================
    # FINAL SUMMARY
    # =====================================================

    print()
    print()
    print("=" * 90)
    print("FINAL MANGO FEASIBILITY SUMMARY")
    print("=" * 90)

    print(
        f"{'KEYWORD':<25}"
        f"{'STATUS':<10}"
        f"{'RECORD COUNT':<15}"
        f"{'PRODUCT LINKS':<15}"
        f"BLOCKED"
    )

    print("-" * 90)

    blocked_count = 0

    for result in results:

        if result["blocked"]:
            blocked_count += 1

        print(
            f"{result['keyword']:<25}"
            f"{str(result['status']):<10}"
            f"{str(result['record_count']):<15}"
            f"{str(result['product_links']):<15}"
            f"{'YES' if result['blocked'] else 'NO'}"
        )

    print()
    print("=" * 90)
    print(
        "URLS CHECKED :",
        len(results)
    )
    print(
        "URLS BLOCKED :",
        blocked_count
    )
    print(
        "URLS ACCESSIBLE :",
        len(results) - blocked_count
    )
    print("=" * 90)


if __name__ == "__main__":
    main()