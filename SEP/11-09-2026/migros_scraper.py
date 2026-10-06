from playwright.sync_api import sync_playwright
from urllib.parse import urljoin, urlparse
import csv
import time


START_URL = "https://www.migros.ch/en/category/fruits-vegetables"
BASE_DOMAIN = "https://www.migros.ch"

OUTPUT_FILE = "products.csv"


def clean_text(text):
    if not text:
        return None

    return " ".join(text.split()).strip()


def get_text(page, selector, timeout=5000):
    try:
        locator = page.locator(selector).first
        return clean_text(locator.inner_text(timeout=timeout))
    except:
        return None


def get_attribute(page, selector, attribute, timeout=5000):
    try:
        locator = page.locator(selector).first
        return locator.get_attribute(attribute, timeout=timeout)
    except:
        return None


def is_category_url(url):
    parsed = urlparse(url)

    return (
        parsed.netloc == "www.migros.ch"
        and parsed.path.startswith("/en/category/fruits-vegetables")
    )


def is_product_url(url):
    parsed = urlparse(url)

    return (
        parsed.netloc == "www.migros.ch"
        and parsed.path.startswith("/en/product/")
    )


def normalize_category_url(url):
    parsed = urlparse(url)

    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def collect_page_links(page):
    """
    Collect category links, pagination links and product links
    from the currently loaded page.
    """

    return page.locator("a[href]").evaluate_all(
        """
        elements => elements.map(e => ({
            href: e.href,
            text: e.innerText.trim()
        }))
        """
    )


def collect_products_from_listing(page):
    """
    Scroll through the listing and collect unique product URLs.
    """

    product_urls = set()
    last_count = 0
    stable_rounds = 0

    for _ in range(30):

        links = page.locator('a[href*="/en/product/"]').evaluate_all(
            """
            elements => elements.map(e => e.href)
            """
        )

        for url in links:
            if is_product_url(url):
                product_urls.add(url)

        print(f"      Products found: {len(product_urls)}")

        # Scroll down
        page.evaluate(
            "window.scrollTo(0, document.body.scrollHeight)"
        )

        page.wait_for_timeout(2000)

        # Check whether new products appeared
        if len(product_urls) == last_count:
            stable_rounds += 1
        else:
            stable_rounds = 0

        last_count = len(product_urls)

        if stable_rounds >= 2:
            break

    return product_urls


def get_next_page(page):
    """
    Discover the next-page URL from the rendered page.
    No page number is hardcoded.
    """

    links = page.locator("a[href]").evaluate_all(
        """
        elements => elements.map(e => ({
            href: e.href,
            text: e.innerText.trim()
        }))
        """
    )

    for link in links:

        text = link["text"].lower()

        if (
            "next" in text
            and "product" in text
            and is_category_url(link["href"])
        ):
            return link["href"]

    return None


def scrape_product(page, url):
    print(f"\n    Opening product:")
    print(f"    {url}")

    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(3000)

        # Click See online offer if available
        online_button = page.get_by_role(
            "button",
            name="See online offer"
        )

        if online_button.count() > 0:

            try:
                online_button.first.click(timeout=5000)
                page.wait_for_timeout(3000)
                print("    Clicked: See online offer")

            except:
                print("    Could not click See online offer")

        # Product Name
        try:
            product_name = clean_text(
                page.locator(
                    "mo-product-subtitle"
                ).first.text_content(timeout=5000)
            )

            if product_name:
                product_name = product_name.rstrip(",")

        except:
            product_name = None

        # Quantity
        try:
            quantity = clean_text(
                page.locator(
                    'span[data-testid$="-weight"]'
                ).first.text_content(timeout=5000)
            )

            if quantity and "The weight" in quantity:
                quantity = quantity.split("The weight")[0].strip()

        except:
            quantity = None

        product = {
            "Product URL": page.url,

            "Product Name": product_name,

            "Price": get_text(
                page,
                'span[data-testid="default-actual-price"]'
            ),

            "Quantity / Size": quantity,

            "Unit Price": get_text(
                page,
                'span[data-testid="price-unit"]'
            ),

            "Brand": get_attribute(
                page,
                'img[data-testid="product-detail-brand-label"]',
                "alt"
            ),

            "Rating": get_attribute(
                page,
                '[aria-label*="out of 5 stars"]',
                "aria-label"
            ),

            "Review Count": get_text(
                page,
                'a:has-text("ratings on Migipedia")'
            ),

            "Country of Origin": get_text(
                page,
                'dd[id*="origin"]'
            ),

            "Description": get_attribute(
                page,
                'meta[itemprop="description"]',
                "content"
            ),
        }

        print("    Product Name:", product["Product Name"])
        print("    Price:", product["Price"])

        return product

    except Exception as e:

        print(f"    ERROR: {e}")

        return None


with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)

    page = browser.new_page(
        viewport={
            "width": 1440,
            "height": 900
        }
    )

    # ==========================================================
    # STEP 1: DISCOVER CATEGORY PAGES
    # ==========================================================

    print("\n========================================")
    print("DISCOVERING MIGROS CATEGORIES")
    print("========================================\n")

    categories_to_visit = [START_URL]
    visited_categories = set()

    while categories_to_visit:

        category_url = categories_to_visit.pop(0)

        category_url = normalize_category_url(category_url)

        if category_url in visited_categories:
            continue

        if not is_category_url(category_url):
            continue

        visited_categories.add(category_url)

        print(f"\nCategory {len(visited_categories)}:")
        print(category_url)

        try:

            page.goto(
                category_url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            page.wait_for_timeout(4000)

            links = collect_page_links(page)

            for link in links:

                href = link["href"]

                if is_category_url(href):

                    clean_url = normalize_category_url(href)

                    if clean_url not in visited_categories:
                        categories_to_visit.append(clean_url)

            print(
                f"Discovered categories: "
                f"{len(visited_categories) + len(categories_to_visit)}"
            )

        except Exception as e:

            print(f"Category error: {e}")

    print("\n========================================")
    print(f"TOTAL CATEGORIES: {len(visited_categories)}")
    print("========================================\n")


    # ==========================================================
    # STEP 2: COLLECT PRODUCT URLS
    # ==========================================================

    print("\n========================================")
    print("COLLECTING PRODUCT URLS")
    print("========================================\n")

    all_product_urls = set()

    for category_number, category_url in enumerate(
        sorted(visited_categories),
        start=1
    ):

        print(
            f"\n[{category_number}/{len(visited_categories)}]"
        )
        print(category_url)

        current_page_url = category_url
        visited_pages = set()

        while current_page_url:

            current_page_url = normalize_category_url(
                current_page_url
            )

            if current_page_url in visited_pages:
                break

            visited_pages.add(current_page_url)

            try:

                page.goto(
                    current_page_url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                page.wait_for_timeout(4000)

                # Scroll and collect products
                products = collect_products_from_listing(page)

                before = len(all_product_urls)

                all_product_urls.update(products)

                after = len(all_product_urls)

                print(
                    f"      New products: {after - before}"
                )

                print(
                    f"      Total unique products: {after}"
                )

                # Find dynamically discovered next page
                next_page = get_next_page(page)

                if next_page:

                    print(
                        f"      Next page found:"
                    )
                    print(
                        f"      {next_page}"
                    )

                    current_page_url = next_page

                else:

                    current_page_url = None

            except Exception as e:

                print(
                    f"      Listing error: {e}"
                )

                current_page_url = None

    print("\n========================================")
    print(
        f"TOTAL UNIQUE PRODUCTS: "
        f"{len(all_product_urls)}"
    )
    print("========================================\n")


    # ==========================================================
    # STEP 3: SCRAPE EVERY PRODUCT
    # ==========================================================

    print("\n========================================")
    print("SCRAPING PRODUCTS")
    print("========================================\n")

    results = []

    product_urls = sorted(all_product_urls)

    for index, product_url in enumerate(
        product_urls,
        start=1
    ):

        print(
            f"\n[{index}/{len(product_urls)}]"
        )

        product = scrape_product(
            page,
            product_url
        )

        if product:

            results.append(product)

        # Small delay between products
        time.sleep(1)


    # ==========================================================
    # STEP 4: SAVE CSV
    # ==========================================================

    fields = [
        "Product URL",
        "Product Name",
        "Price",
        "Quantity / Size",
        "Unit Price",
        "Brand",
        "Rating",
        "Review Count",
        "Country of Origin",
        "Description",
    ]

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()

        writer.writerows(results)


    print("\n========================================")
    print("SCRAPING COMPLETE")
    print("========================================")

    print(
        f"Products scraped: {len(results)}"
    )

    print(
        f"CSV saved as: {OUTPUT_FILE}"
    )

    print("========================================\n")


    input("Press ENTER to close browser...")

    browser.close()