from playwright.sync_api import sync_playwright
from urllib.parse import quote


KEYWORD = "Mini dress"

SEARCH_URL = (
    "https://shop.mango.com/in/en/search/women/q/"
    + quote(KEYWORD)
)


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

        print("\nOpening:")
        print(SEARCH_URL)

        response = page.goto(
            SEARCH_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(5000)

        print("\n" + "=" * 90)
        print("MANGO PRODUCT LINK DEBUG")
        print("=" * 90)

        print("STATUS:", response.status if response else "UNKNOWN")
        print("TITLE :", page.title())

        # --------------------------------------------------
        # ALL LINKS
        # --------------------------------------------------

        links = page.locator("a")

        print("\nTOTAL <a> TAGS:", links.count())

        product_count = 0

        for i in range(links.count()):

            link = links.nth(i)

            try:

                href = link.get_attribute("href")

                if not href:
                    continue

                if "/p/" not in href:
                    continue

                product_count += 1

                text = link.inner_text().strip()

                aria = link.get_attribute("aria-label")

                class_name = link.get_attribute("class")

                # --------------------------------------------------
                # IMAGE
                # --------------------------------------------------

                image_url = None
                image_alt = None

                img = link.locator("img").first

                if img.count() > 0:

                    image_url = (
                        img.get_attribute("src")
                        or img.get_attribute("data-src")
                        or img.get_attribute("data-lazy-src")
                    )

                    image_alt = img.get_attribute("alt")

                print("\n" + "-" * 90)

                print("PRODUCT CANDIDATE:", product_count)

                print("HREF:")
                print(href)

                print("\nTEXT:")
                print(text or "EMPTY")

                print("\nARIA:")
                print(aria or "EMPTY")

                print("\nCLASS:")
                print(class_name or "EMPTY")

                print("\nIMAGE ALT:")
                print(image_alt or "EMPTY")

                print("\nIMAGE URL:")
                print(image_url or "EMPTY")

                # --------------------------------------------------
                # PARENT HTML
                # --------------------------------------------------

                try:

                    parent_html = link.evaluate(
                        "(el) => el.parentElement.outerHTML"
                    )

                    print("\nPARENT HTML:")
                    print(parent_html[:1500])

                except Exception as e:

                    print("\nPARENT HTML ERROR:", e)

            except Exception as e:

                print(
                    f"\nERROR processing link {i}: {e}"
                )

        print("\n" + "=" * 90)
        print("SUMMARY")
        print("=" * 90)

        print("Total <a> tags      :", links.count())
        print("Product candidates  :", product_count)

        browser.close()


if __name__ == "__main__":
    main()