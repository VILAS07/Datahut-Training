import asyncio
import re
import shutil

from playwright.async_api import async_playwright

from settings import (
    CATEGORY_URLS,
    HEADLESS,
    BROWSER_ARGS,
    PAGE_TIMEOUT,
    USER_AGENT,
    MAX_PRODUCTS,
)

from parser import parse_product
from export import MongoExporter


def is_product_url(url):
    if not url:
        return False

    return bool(
        re.search(r"/p\d+(?:$|[?#])", url)
    )


def normalize_url(url):
    if not url:
        return ""

    url = url.split("#")[0]
    url = url.split("?")[0]

    return url.rstrip("/")


async def extract_product_urls(page):

    links = await page.locator("a").evaluate_all(
        """
        elements => elements.map(a => ({
            href: a.href,
            text: a.innerText
        }))
        """
    )

    product_urls = []

    for item in links:

        url = item.get("href")

        if not url:
            continue

        url = normalize_url(url)

        if not is_product_url(url):
            continue

        if url not in product_urls:
            product_urls.append(url)

    return product_urls


async def scrape_product(
    page,
    url,
    index,
    total,
    exporter,
):

    print()
    print("=" * 70)

    if total:
        print(f"PRODUCT {index}/{total}")
    else:
        print(f"PRODUCT {index}")

    print(url)
    print("=" * 70)

    try:

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )

        await page.wait_for_timeout(3000)

        title = await page.title()

        html = await page.content()

        print(f"TITLE: {title}")
        print(f"HTML SIZE: {len(html)}")

        product = parse_product(
            html,
            url,
        )

        if not product:
            print("Parser returned no data.")
            return False

        print()
        print("PRODUCT DATA")
        print("-" * 70)

        print(
            f"Product ID : {product.get('product_id')}"
        )

        print(
            f"Name       : {product.get('name')}"
        )

        print(
            f"Brand      : {product.get('brand')}"
        )

        print(
            f"Price      : {product.get('price')}"
        )

        print(
            f"Currency   : {product.get('currency')}"
        )

        print(
            f"Availability: {product.get('availability')}"
        )

        print(
            f"Images     : {len(product.get('images', []))}"
        )

        print(
            f"Sizes      : {product.get('sizes')}"
        )

        saved = exporter.save(product)

        if saved:
            print()
            print("✓ SAVED TO MONGODB")
            return True

        print()
        print("✗ FAILED TO SAVE")

        return False

    except Exception as e:

        print()
        print("PRODUCT ERROR")
        print("-" * 70)
        print(
            f"{type(e).__name__} : {e}"
        )

        return False


async def main():

    browser = None
    exporter = None

    try:

        async with async_playwright() as p:

            print(
                "Starting installed Google Chrome..."
            )

            chrome_path = shutil.which(
                "google-chrome"
            )

            if not chrome_path:
                chrome_path = shutil.which(
                    "google-chrome-stable"
                )

            if not chrome_path:
                chrome_path = shutil.which(
                    "chromium"
                )

            if not chrome_path:
                raise RuntimeError(
                    "Google Chrome/Chromium not found."
                )

            browser = await p.chromium.launch(
                executable_path=chrome_path,
                headless=HEADLESS,
                args=BROWSER_ARGS,
            )

            print("Chrome started.")

            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={
                    "width": 1440,
                    "height": 900,
                },
                locale="en-GB",
            )

            page = await context.new_page()

            page.set_default_timeout(
                PAGE_TIMEOUT
            )

            exporter = MongoExporter()

            all_product_urls = []

            # ==================================================
            # CATEGORY PAGES
            # ==================================================

            for page_number, category_url in enumerate(
                CATEGORY_URLS,
                start=1,
            ):

                print()
                print("=" * 70)
                print(
                    f"CATEGORY PAGE {page_number}"
                )
                print(category_url)
                print("=" * 70)

                await page.goto(
                    category_url,
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT,
                )

                await page.wait_for_timeout(3000)

                title = await page.title()

                print(
                    f"Title: {title}"
                )

                urls = await extract_product_urls(
                    page
                )

                print(
                    f"Found {len(urls)} product URLs"
                )

                for url in urls:

                    if url not in all_product_urls:
                        all_product_urls.append(url)

            # ==================================================
            # APPLY LIMIT ONLY IF SET
            # ==================================================

            if MAX_PRODUCTS is not None:

                all_product_urls = (
                    all_product_urls[:MAX_PRODUCTS]
                )

            # ==================================================
            # PRODUCT LIST
            # ==================================================

            print()
            print("=" * 70)
            print("PRODUCT URLS")
            print("=" * 70)

            for number, url in enumerate(
                all_product_urls,
                start=1,
            ):

                print(
                    f"{number}. {url}"
                )

            print()
            print(
                f"TOTAL PRODUCTS: "
                f"{len(all_product_urls)}"
            )

            # ==================================================
            # SCRAPE ALL PRODUCTS
            # ==================================================

            success_count = 0
            failed_count = 0

            total = len(all_product_urls)

            for index, product_url in enumerate(
                all_product_urls,
                start=1,
            ):

                success = await scrape_product(
                    page,
                    product_url,
                    index,
                    total,
                    exporter,
                )

                if success:
                    success_count += 1
                else:
                    failed_count += 1

                # Return to category page
                # before opening next product.

                if index < total:

                    print()
                    print(
                        "Returning to category page..."
                    )

                    await page.goto(
                        CATEGORY_URLS[0],
                        wait_until="domcontentloaded",
                        timeout=PAGE_TIMEOUT,
                    )

                    await page.wait_for_timeout(
                        1500
                    )

            # ==================================================
            # SUMMARY
            # ==================================================

            print()
            print("=" * 70)
            print("SCRAPING COMPLETE")
            print("=" * 70)

            print(
                f"Product URLs found : {total}"
            )

            print(
                f"Products scraped   : {success_count}"
            )

            print(
                f"Products failed    : {failed_count}"
            )

            print("=" * 70)

            await context.close()

    except KeyboardInterrupt:

        print()
        print("Stopped by user.")

    except Exception as e:

        print()
        print("FATAL ERROR")
        print("-" * 70)

        print(
            f"{type(e).__name__} : {e}"
        )

    finally:

        if exporter:

            try:
                exporter.close()
            except Exception:
                pass

        if browser:

            try:
                await browser.close()
                print("Chrome closed.")
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())