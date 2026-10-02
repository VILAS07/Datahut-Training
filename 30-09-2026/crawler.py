from urllib.parse import quote

from camoufox.sync_api import Camoufox

from settings import (
    KEYWORDS,
    PRODUCTS_PER_KEYWORD,
    BASE_URL,
    SEARCH_URL,
    HEADLESS,
    SEARCH_WAIT,
    PDP_WAIT,
)

from parser import parse_product

from export import export_csv


def collect_products(page, keyword):

    search_url = SEARCH_URL.format(
        quote(keyword)
    )

    print()
    print("=" * 70)
    print(f"KEYWORD: {keyword}")
    print("=" * 70)

    print(
        f"Search URL: {search_url}"
    )

    try:

        page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(
            SEARCH_WAIT
        )

    except Exception as error:

        print(
            f"Search page failed: {error}"
        )

        return []

    cards = page.locator(
        '[data-testid="product_summary_image_media"]'
    )

    card_count = cards.count()

    print(
        f"Product cards found: {card_count}"
    )

    products = []

    seen_urls = set()

    for index in range(card_count):

        if len(products) >= PRODUCTS_PER_KEYWORD:
            break

        try:

            card = cards.nth(index)

            href = card.get_attribute(
                "href",
                timeout=10000,
            )

            title = card.get_attribute(
                "title",
                timeout=10000,
            )

            if not href:
                continue

            if href.startswith("/"):
                href = BASE_URL + href

            pdp_url = href.split("#")[0]

            if pdp_url in seen_urls:
                continue

            seen_urls.add(pdp_url)

            image_url = ""

            try:

                image = card.locator(
                    "img"
                ).first

                image_url = image.get_attribute(
                    "src",
                    timeout=10000,
                ) or ""

            except Exception:
                pass

            products.append({
                "title": title or "",
                "pdp_url": pdp_url,
                "image_url": image_url,
            })

        except Exception as error:

            print(
                f"Card {index + 1} failed: "
                f"{error}"
            )

    print(
        f"Unique products selected: "
        f"{len(products)}"
    )

    return products


def crawl():

    all_items = []

    with Camoufox(
        headless=HEADLESS
    ) as browser:

        page = browser.new_page()

        # -------------------------------------------------
        # KEYWORD LOOP
        # -------------------------------------------------

        for keyword in KEYWORDS:

            # -------------------------------------------------
            # GET PRODUCT URLS FIRST
            # -------------------------------------------------

            products = collect_products(
                page,
                keyword,
            )

            # -------------------------------------------------
            # PDP LOOP
            # -------------------------------------------------

            for rank, product in enumerate(
                products,
                start=1,
            ):

                pdp_url = product[
                    "pdp_url"
                ]

                image_url = product[
                    "image_url"
                ]

                title = product[
                    "title"
                ]

                print()
                print(
                    f"[{rank}/"
                    f"{len(products)}] "
                    f"{title}"
                )

                print(
                    f"PDP: {pdp_url}"
                )

                try:

                    page.goto(
                        pdp_url,
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )

                    page.wait_for_timeout(
                        PDP_WAIT
                    )

                    item = parse_product(
                        page=page,
                        keyword=keyword,
                        rank=rank,
                        pdp_url=pdp_url,
                        image_url=image_url,
                    )

                    all_items.append(item)

                    print(
                        f"Product: "
                        f"{item['product_name']}"
                    )

                    print(
                        f"Price: "
                        f"{item['price']}"
                    )

                    print(
                        f"Colour: "
                        f"{item['colour']}"
                    )

                except Exception as error:

                    print(
                        f"PDP failed: {error}"
                    )

    # -----------------------------------------------------
    # EXPORT
    # -----------------------------------------------------

    export_csv(
        all_items
    )

    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    expected = (
        len(KEYWORDS)
        * PRODUCTS_PER_KEYWORD
    )

    print()
    print("=" * 70)
    print("CRAWL COMPLETED")
    print("=" * 70)

    print(
        f"Keywords: {len(KEYWORDS)}"
    )

    print(
        f"Products per keyword: "
        f"{PRODUCTS_PER_KEYWORD}"
    )

    print(
        f"Expected maximum records: "
        f"{expected}"
    )

    print(
        f"Actual records collected: "
        f"{len(all_items)}"
    )


if __name__ == "__main__":
    crawl()