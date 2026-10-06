from playwright.sync_api import sync_playwright


URL = (
    "https://www.sephora.sg/"
    "products/benefit-cosmetics-the-porefessional-concealer/"
    "v/1c-ready"
)


with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False
    )

    page = browser.new_page(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/139.0.0.0 Safari/537.36"
        )
    )

    print("Opening product page...")

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(5000)


    # ==================================================
    # BRAND
    # ==================================================

    print("\n========================================")
    print("              BRAND LINKS")
    print("========================================")

    brand_links = page.locator(
        'a[href*="/brands/"]'
    )

    print(
        "Total brand links:",
        brand_links.count()
    )

    for i in range(brand_links.count()):

        link = brand_links.nth(i)

        try:

            print("\n--- BRAND", i + 1, "---")

            print(
                "TEXT:",
                link.inner_text()
            )

            print(
                "HREF:",
                link.get_attribute("href")
            )

            print(
                "CLASS:",
                link.get_attribute("class")
            )

            print(
                "HTML:",
                link.evaluate(
                    "(element) => element.outerHTML"
                )
            )

        except Exception:
            pass


    # ==================================================
    # RATING
    # ==================================================

    print("\n========================================")
    print("              RATING AREA")
    print("========================================")

    rating_area = page.locator(
        '[data-bv-show="rating_summary"]'
    )

    print(
        "Rating containers:",
        rating_area.count()
    )

    if rating_area.count() > 0:

        print(
            rating_area.first.inner_text()
        )

        print("\n========== RATING HTML ==========")

        print(
            rating_area.first.evaluate(
                "(element) => element.outerHTML"
            )
        )


    # ==================================================
    # REVIEWS
    # ==================================================

    print("\n========================================")
    print("              REVIEW AREA")
    print("========================================")

    review_texts = page.locator(
        'text=/Reviews/i'
    )

    print(
        "Elements containing Reviews:",
        review_texts.count()
    )

    for i in range(
        min(review_texts.count(), 10)
    ):

        element = review_texts.nth(i)

        try:

            print("\n--- REVIEW ELEMENT", i + 1, "---")

            print(
                "TEXT:",
                element.inner_text()
            )

            print(
                "TAG:",
                element.evaluate(
                    "(element) => element.tagName"
                )
            )

            print(
                "CLASS:",
                element.get_attribute("class")
            )

            print(
                "HTML:",
                element.evaluate(
                    "(element) => element.outerHTML"
                )
            )

        except Exception:
            pass


    # ==================================================
    # CLOSE
    # ==================================================

    browser.close()