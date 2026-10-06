from playwright.sync_api import sync_playwright

from parser import SephoraParser


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
    # GET HTML
    # ==================================================

    html = page.content()

    # ==================================================
    # TEST PARSER
    # ==================================================

    parser = SephoraParser()

    product = parser.parse_product_page(
        html,
        URL
    )

    print("\n")
    print("========================================")
    print("        PARSED PRODUCT")
    print("========================================")

    for key, value in product.items():

        print(f"\n{key.upper()}:")
        print(value)

    print("\n")
    print("========================================")
    print("        RAW PAGE INSPECTION")
    print("========================================")


    # ==================================================
    # H1 PARENT STRUCTURE
    # ==================================================

    h1 = page.locator("h1").first

    print("\n========== H1 HTML ==========")

    if h1.count() > 0:

        print(
            h1.evaluate(
                "(element) => element.parentElement.outerHTML"
            )
        )


    # ==================================================
    # PRODUCT IMAGE
    # ==================================================

    image = page.locator(
        "img.product-header-image"
    ).first

    print("\n========== PRODUCT IMAGE ==========")

    if image.count() > 0:

        print(
            "SRC:",
            image.get_attribute("src")
        )

        print(
            "ALT:",
            image.get_attribute("alt")
        )

        print(
            "CLASS:",
            image.get_attribute("class")
        )

    else:

        print("Product header image not found.")


    # ==================================================
    # DESCRIPTION
    # ==================================================

    description_heading = page.locator(
        "h3.product-detail-title"
    ).filter(
        has_text="DESCRIPTION"
    ).first

    print("\n========== DESCRIPTION HTML ==========")

    if description_heading.count() > 0:

        print(
            description_heading.evaluate(
                "(element) => element.parentElement.outerHTML"
            )
        )

    else:

        print("Description section not found.")


    # ==================================================
    # INGREDIENTS
    # ==================================================

    ingredients_heading = page.locator(
        "h3.product-detail-title"
    ).filter(
        has_text="INGREDIENTS"
    ).first

    print("\n========== INGREDIENTS HTML ==========")

    if ingredients_heading.count() > 0:

        print(
            ingredients_heading.evaluate(
                "(element) => element.parentElement.outerHTML"
            )
        )

    else:

        print("Ingredients section not found.")


    # ==================================================
    # HOW TO
    # ==================================================

    how_to_heading = page.locator(
        "h3.product-detail-title"
    ).filter(
        has_text="HOW TO"
    ).first

    print("\n========== HOW TO HTML ==========")

    if how_to_heading.count() > 0:

        print(
            how_to_heading.evaluate(
                "(element) => element.parentElement.outerHTML"
            )
        )

    else:

        print("How To section not found.")


    # ==================================================
    # CLOSE
    # ==================================================

    browser.close()