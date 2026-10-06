from cloakbrowser import launch
from urllib.parse import urljoin
import re


BASE_URL = "https://www.next.co.uk"
KEYWORD = "mini dress"
TOP_N = 10


def clean(text):
    if not text:
        return ""
    return " ".join(text.split()).strip()


def first_text(page, selectors):
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            if loc.count() > 0 and loc.is_visible():
                text = clean(loc.inner_text())
                if text:
                    return text
        except Exception:
            pass
    return ""


def first_attr(page, selectors, attribute):
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            if loc.count() > 0:
                value = loc.get_attribute(attribute)
                if value:
                    return clean(value)
        except Exception:
            pass
    return ""


def get_price(text):
    match = re.search(r"£\s?[\d,.]+", text)
    return match.group(0) if match else ""


def main():

    browser = launch(headless=False)

    try:
        page = browser.new_page()

        # =========================================================
        # 1. OPEN NEXT
        # =========================================================

        response = page.goto(
            BASE_URL,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        print("HOME STATUS:", response.status if response else None)
        print("HOME TITLE:", page.title())

        page.wait_for_timeout(5000)

        # =========================================================
        # 2. SEARCH KEYWORD
        # =========================================================

        search = page.locator(
            '[data-testid="header-search-bar-text-input"]'
        )

        if search.count() == 0:
            raise RuntimeError("Search input not found")

        search.fill(KEYWORD)
        search.press("Enter")

        page.wait_for_timeout(5000)

        print("\nSEARCH URL:", page.url)
        print("SEARCH TITLE:", page.title())

        # =========================================================
        # 3. GET TOP 10 PRODUCT LINKS
        # =========================================================

        products = page.locator(
            '[data-testid="product_summary_image_media"]'
        )

        count = products.count()

        print("\nPRODUCTS FOUND:", count)

        product_urls = []

        for i in range(min(count, TOP_N)):

            product = products.nth(i)

            href = product.get_attribute("href")

            if not href:
                continue

            href = urljoin(BASE_URL, href)

            product_urls.append(href)

            print(
                f"Rank {i + 1}: {href}"
            )

        # =========================================================
        # 4. VISIT EACH PDP
        # =========================================================

        for rank, product_url in enumerate(product_urls, start=1):

            print("\n")
            print("=" * 80)
            print(f"PRODUCT RANK: {rank}")
            print("=" * 80)

            pdp = browser.new_page()

            try:

                response = pdp.goto(
                    product_url,
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

                pdp.wait_for_timeout(3000)

                print("PDP STATUS:",
                      response.status if response else None)

                print("PDP URL:", pdp.url)
                print("PDP TITLE:", pdp.title())

                # =================================================
                # PRODUCT NAME
                # =================================================

                product_name = first_text(
                    pdp,
                    [
                        "h1",
                        '[data-testid*="product-name"]',
                        '[data-testid*="product_title"]',
                    ],
                )

                # =================================================
                # PRICE
                # =================================================

                price = first_text(
                    pdp,
                    [
                        '[data-testid*="price"]',
                        '[class*="price"]',
                    ],
                )

                if not price:
                    price = get_price(pdp.title())

                # =================================================
                # MAIN IMAGE
                # =================================================

                image_url = first_attr(
                    pdp,
                    [
                        'img[data-testid*="product"]',
                        'img[alt*="Black"]',
                        'img',
                    ],
                    "src",
                )

                # =================================================
                # DESCRIPTION
                # =================================================

                description = first_text(
                    pdp,
                    [
                        '[data-testid*="description"]',
                        '[class*="description"]',
                        '[id*="description"]',
                    ],
                )

                # =================================================
                # CATEGORY / PRODUCT TYPE
                # =================================================

                category = first_text(
                    pdp,
                    [
                        '[data-testid*="category"]',
                        '[class*="category"]',
                        '[id*="category"]',
                    ],
                )

                # =================================================
                # COLOUR
                # =================================================

                colour = first_text(
                    pdp,
                    [
                        '[data-testid*="colour"]',
                        '[data-testid*="color"]',
                        '[class*="colour"]',
                        '[class*="color"]',
                    ],
                )

                # =================================================
                # SIZE
                # =================================================

                sizes = []

                size_selectors = [
                    '[data-testid*="size"]',
                    '[class*="size"] button',
                    'button[aria-label*="size" i]',
                ]

                for selector in size_selectors:

                    try:

                        loc = pdp.locator(selector)

                        for j in range(loc.count()):

                            value = clean(
                                loc.nth(j).inner_text()
                            )

                            if value and value not in sizes:
                                sizes.append(value)

                    except Exception:
                        pass

                # =================================================
                # MATERIAL / FABRIC
                # =================================================

                material = first_text(
                    pdp,
                    [
                        '[data-testid*="material"]',
                        '[data-testid*="fabric"]',
                        '[class*="material"]',
                        '[class*="fabric"]',
                    ],
                )

                # =================================================
                # FIT / SIZING
                # =================================================

                fit = first_text(
                    pdp,
                    [
                        '[data-testid*="fit"]',
                        '[class*="fit"]',
                    ],
                )

                # =================================================
                # OCCASION / STYLE
                # =================================================

                occasion = first_text(
                    pdp,
                    [
                        '[data-testid*="occasion"]',
                        '[data-testid*="style"]',
                        '[class*="occasion"]',
                    ],
                )

                # =================================================
                # PRINT FIELDS
                # =================================================

                print("\n--- PRODUCT DATA ---")

                print("Keyword       :", KEYWORD)
                print("Rank          :", rank)
                print("Product Name  :", product_name)
                print("Price         :", price)
                print("Description   :", description)
                print("Category      :", category)
                print("Colour        :", colour)
                print("Gender        : Women")
                print("Material      :", material)
                print("Fit/Sizing    :", fit)
                print("Occasion/Style:", occasion)
                print("Sizes         :", sizes)
                print("Main Image    :", image_url)
                print("PDP URL       :", pdp.url)

                # =================================================
                # DEBUG: SHOW PDP TEXT IF SOME FIELDS ARE EMPTY
                # =================================================

                if not description or not material:

                    print("\n--- PDP TEXT SAMPLE ---")

                    body = clean(
                        pdp.locator("body").inner_text()
                    )

                    print(body[:4000])

            except Exception as e:

                print(
                    f"ERROR processing rank {rank}: {e}"
                )

            finally:

                pdp.close()

    finally:

        browser.close()


if __name__ == "__main__":
    main()
