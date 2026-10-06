from playwright.sync_api import sync_playwright
from urllib.parse import quote


KEYWORD = "Mini dress"

SEARCH_URL = (
    "https://shop.mango.com/in/en/search/women/q/"
    + quote(KEYWORD)
)

TOP_N = 10


def main():

    print("Launching Playwright...")

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 900
            }
        )

        print("\nOpening search page:")
        print(SEARCH_URL)

        response = page.goto(
            SEARCH_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(5000)

        print("\n" + "=" * 80)
        print("MANGO KEYWORD SEARCH RESULT TEST")
        print("=" * 80)

        print("KEYWORD :", KEYWORD)
        print("STATUS  :", response.status if response else "UNKNOWN")
        print("FINAL URL:", page.url)
        print("TITLE   :", page.title())

        # --------------------------------------------------
        # CHECK FOR SECURITY / BLOCKING
        # --------------------------------------------------

        body_text = page.locator("body").inner_text()

        blocking_words = [
            "security checkpoint",
            "access denied",
            "captcha",
            "verify you are human",
            "too many requests",
            "temporarily blocked",
            "forbidden"
        ]

        detected = []

        body_lower = body_text.lower()

        for word in blocking_words:
            if word in body_lower:
                detected.append(word)

        if detected:

            print("\n" + "=" * 80)
            print("SECURITY / BLOCKING DETECTED")
            print("=" * 80)

            for item in detected:
                print("⚠", item)

            browser.close()
            return

        # --------------------------------------------------
        # FIND PRODUCT LINKS
        # --------------------------------------------------

        print("\n" + "=" * 80)
        print("SEARCHING FOR PRODUCT LINKS")
        print("=" * 80)

        links = page.locator("a")

        print("Total links found:", links.count())

        products = []
        seen_urls = set()

        for i in range(links.count()):

            link = links.nth(i)

            try:
                href = link.get_attribute("href")

                if not href:
                    continue

                # Mango PDP URLs contain /p/
                if "/p/" not in href:
                    continue

                # Convert relative URL to absolute
                if href.startswith("/"):
                    href = "https://shop.mango.com" + href

                # Avoid duplicates
                if href in seen_urls:
                    continue

                seen_urls.add(href)

                # Product text
                text = link.inner_text().strip()

                # Image information
                image_url = None

                img = link.locator("img").first

                if img.count() > 0:

                    image_url = (
                        img.get_attribute("src")
                        or img.get_attribute("data-src")
                        or img.get_attribute("data-lazy-src")
                    )

                # Image alt
                image_alt = None

                if img.count() > 0:
                    image_alt = img.get_attribute("alt")

                products.append(
                    {
                        "url": href,
                        "text": text,
                        "image_url": image_url,
                        "image_alt": image_alt
                    }
                )

                if len(products) >= TOP_N:
                    break

            except Exception:
                continue

        # --------------------------------------------------
        # OUTPUT
        # --------------------------------------------------

        print("\n" + "=" * 80)
        print("TOP PRODUCTS")
        print("=" * 80)

        if not products:

            print("\n❌ No Mango product links found.")

            print("\nFirst part of page text:")
            print(body_text[:3000])

        else:

            for rank, product in enumerate(products, start=1):

                print("\n" + "-" * 80)

                print("RANK       :", rank)
                print("PRODUCT TEXT:", product["text"] or "NOT FOUND")
                print("IMAGE ALT  :", product["image_alt"] or "NOT FOUND")
                print("IMAGE URL  :", product["image_url"] or "NOT FOUND")
                print("PDP URL    :", product["url"])

        # --------------------------------------------------
        # SUMMARY
        # --------------------------------------------------

        print("\n" + "=" * 80)
        print("SEARCH RESULT SUMMARY")
        print("=" * 80)

        print("Keyword          :", KEYWORD)
        print("Products found   :", len(products))
        print("Requested        :", TOP_N)

        if len(products) >= TOP_N:
            print("Result           : ✓ TOP 10 FOUND")
        elif products:
            print("Result           : ⚠ FEWER THAN 10 FOUND")
        else:
            print("Result           : ✗ NO PRODUCTS FOUND")

        browser.close()


if __name__ == "__main__":
    main()