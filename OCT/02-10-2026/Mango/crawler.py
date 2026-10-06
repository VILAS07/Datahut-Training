from cloakbrowser import launch
from urllib.parse import urljoin, quote
import time

from parser import parse_product


# ==========================================================
# CONFIG
# ==========================================================

BASE_URL = "https://www.next.co.uk"

KEYWORD = "mini dress"

TOP_N = 10

HOME_WAIT = 5000
SEARCH_WAIT = 5000
PDP_WAIT = 3000

NAVIGATION_TIMEOUT = 60000

BLOCKED_TEXT = [
    "Access Denied",
    "access denied",
    "Request blocked",
    "request blocked",
    "Forbidden",
    "403 Forbidden",
]


# ==========================================================
# SEARCH URL
# ==========================================================

def get_search_url(keyword):
    return f"{BASE_URL}/search?w={quote(keyword)}"


# ==========================================================
# BLOCK CHECK
# ==========================================================

def is_blocked(page):
    """
    Check whether the current page appears to be blocked.
    """

    try:
        body_text = page.locator("body").inner_text(
            timeout=10000
        )

        for text in BLOCKED_TEXT:

            if text in body_text:
                return True

    except Exception:
        pass

    return False


# ==========================================================
# PRODUCT URL EXTRACTION
# ==========================================================

def get_product_urls(page, limit=10):
    """
    Extract unique Next product PDP URLs
    from the search results page.
    """

    selectors = [
        'a[data-testid="product_summary_image_media"]',
        'a[href*="/style/"]',
    ]

    urls = []

    for selector in selectors:

        try:

            elements = page.locator(selector)

            count = elements.count()

            print(
                f"SELECTOR: {selector} | COUNT: {count}"
            )

            for i in range(count):

                try:

                    href = elements.nth(i).get_attribute(
                        "href"
                    )

                except Exception:
                    continue

                if not href:
                    continue

                href = urljoin(
                    BASE_URL,
                    href,
                )

                # Remove fragment
                href = href.split("#")[0]

                # Only Next PDP
                if "/style/" not in href:
                    continue

                # Remove duplicate
                if href in urls:
                    continue

                urls.append(href)

                if len(urls) >= limit:
                    return urls

        except Exception as exc:

            print(
                f"ERROR selector {selector}: {exc}"
            )

    return urls


# ==========================================================
# PRODUCT PRINT
# ==========================================================

def print_product(product):

    print("\n" + "=" * 75)
    print("PARSED PRODUCT")
    print("=" * 75)

    fields = [
        "keyword",
        "rank",
        "product_name",
        "size",
        "description",
        "category",
        "price",
        "main_image_url",
        "pdp_url",
        "colour",
        "gender",
        "material",
        "fit",
        "occasion",
    ]

    for field in fields:

        value = product.get(field, "")

        print(f"{field}: {value}")


# ==========================================================
# RUN
# ==========================================================

def run():

    browser = None

    stats = {
        "search_requests": 0,
        "product_urls_found": 0,
        "block_checked_urls": 0,
        "blocked_urls": 0,
        "parsed_products": 0,
        "failed_products": 0,
    }

    try:

        # ==================================================
        # START CLOAKBROWSER
        # ==================================================

        print("\n" + "=" * 75)
        print("STARTING CLOAKBROWSER")
        print("=" * 75)

        browser = launch(
            headless=False
        )

        page = browser.new_page()

        # ==================================================
        # HOME
        # ==================================================

        print("\n========== HOME ==========")

        response = page.goto(
            BASE_URL,
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT,
        )

        page.wait_for_timeout(
            HOME_WAIT
        )

        if response:
            print(
                "STATUS:",
                response.status,
            )

        print(
            "URL:",
            page.url,
        )

        print(
            "TITLE:",
            page.title(),
        )

        # ==================================================
        # SEARCH
        # ==================================================

        search_url = get_search_url(
            KEYWORD
        )

        print("\n========== SEARCH ==========")

        print(
            "KEYWORD:",
            KEYWORD,
        )

        print(
            "SEARCH URL:",
            search_url,
        )

        response = page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT,
        )

        stats["search_requests"] += 1

        page.wait_for_timeout(
            SEARCH_WAIT
        )

        print(
            "FINAL URL:",
            page.url,
        )

        if response:
            print(
                "SEARCH STATUS:",
                response.status,
            )

        print(
            "SEARCH TITLE:",
            page.title(),
        )

        # ==================================================
        # CHECK SEARCH BLOCK
        # ==================================================

        stats["block_checked_urls"] += 1

        print(
            "\nBLOCK CHECKED URL:",
            stats["block_checked_urls"],
        )

        if is_blocked(page):

            stats["blocked_urls"] += 1

            print(
                "\n========== SEARCH BLOCKED =========="
            )

            print(
                page.locator("body").inner_text(
                    timeout=10000
                )[:1000]
            )

            return

        print(
            "SEARCH BLOCK STATUS: NOT BLOCKED"
        )

        # ==================================================
        # EXTRACT PRODUCT URLS
        # ==================================================

        print(
            "\n========== PRODUCT URL EXTRACTION =========="
        )

        product_urls = get_product_urls(
            page,
            TOP_N,
        )

        stats["product_urls_found"] = len(
            product_urls
        )

        print(
            "PRODUCT COUNT:",
            len(product_urls),
        )

        if not product_urls:

            print(
                "\nNO PRODUCT URLS FOUND"
            )

            return

        for rank, url in enumerate(
            product_urls,
            1,
        ):

            print(
                f"RANK {rank}: {url}"
            )

        # ==================================================
        # OPEN PDPs
        # ==================================================

        for rank, product_url in enumerate(
            product_urls,
            1,
        ):

            print("\n")
            print("=" * 75)
            print(
                f"OPENING PDP - RANK {rank}"
            )
            print("=" * 75)

            print(
                "PDP URL:",
                product_url,
            )

            try:

                # ------------------------------------------
                # NAVIGATE
                # ------------------------------------------

                response = page.goto(
                    product_url,
                    wait_until="domcontentloaded",
                    timeout=NAVIGATION_TIMEOUT,
                )

                page.wait_for_timeout(
                    PDP_WAIT
                )

                status = (
                    response.status
                    if response
                    else None
                )

                print(
                    "PDP STATUS:",
                    status,
                )

                print(
                    "PDP FINAL URL:",
                    page.url,
                )

                print(
                    "PDP TITLE:",
                    page.title(),
                )

                # ------------------------------------------
                # BLOCK CHECK
                # ------------------------------------------

                stats[
                    "block_checked_urls"
                ] += 1

                print(
                    "BLOCK CHECKED URL:",
                    stats[
                        "block_checked_urls"
                    ],
                )

                if is_blocked(page):

                    stats[
                        "blocked_urls"
                    ] += 1

                    print(
                        "\nPDP BLOCKED"
                    )

                    try:

                        body_text = (
                            page.locator(
                                "body"
                            ).inner_text(
                                timeout=10000
                            )
                        )

                        print(
                            body_text[:500]
                        )

                    except Exception:
                        pass

                    continue

                print(
                    "PDP BLOCK STATUS: NOT BLOCKED"
                )

                # ------------------------------------------
                # PARSE PRODUCT
                # ------------------------------------------

                print(
                    "\nPARSING PRODUCT..."
                )

                product = parse_product(
                    page=page,
                    keyword=KEYWORD,
                    rank=rank,
                    pdp_url=product_url,
                )

                print_product(
                    product
                )

                stats[
                    "parsed_products"
                ] += 1

                # ------------------------------------------
                # DELAY
                # ------------------------------------------

                time.sleep(2)

            except Exception as exc:

                stats[
                    "failed_products"
                ] += 1

                print(
                    f"\nERROR processing rank {rank}:"
                )

                print(
                    exc
                )

                continue

    finally:

        # ==================================================
        # CLOSE BROWSER
        # ==================================================

        if browser:

            try:

                browser.close()

            except Exception:
                pass

        # ==================================================
        # FINAL STATS
        # ==================================================

        print("\n")
        print("=" * 75)
        print("CRAWLER SUMMARY")
        print("=" * 75)

        print(
            "Keyword:",
            KEYWORD,
        )

        print(
            "Search Requests:",
            stats["search_requests"],
        )

        print(
            "Product URLs Found:",
            stats["product_urls_found"],
        )

        print(
            "Block Checked URLs:",
            stats["block_checked_urls"],
        )

        print(
            "Blocked URLs:",
            stats["blocked_urls"],
        )

        print(
            "Parsed Products:",
            stats["parsed_products"],
        )

        print(
            "Failed Products:",
            stats["failed_products"],
        )

        print("=" * 75)


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    run()