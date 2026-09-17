from playwright.sync_api import sync_playwright
import csv
import os
import time

from parser import SephoraParser


BASE_URL = "https://www.sephora.sg/categories/makeup"
OUTPUT_FILE = "sephora_makeup.csv"


class SephoraCrawler:

    def __init__(self):

        self.parser = SephoraParser()

        self.seen_urls = set()
        self.products = []

    # ==========================================
    # SAVE PRODUCT TO CSV
    # ==========================================

    def save_product(self, product):

        file_exists = os.path.exists(OUTPUT_FILE)

        fieldnames = [
            "url",
            "name",
            "brand",
            "price",
            "rating",
            "reviews",
            "image",
            "category",
            "product_size",
            "shades",
            "description",
            "ingredients",
            "how_to"
        ]

        with open(
            OUTPUT_FILE,
            "a",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )

            if not file_exists:
                writer.writeheader()

            writer.writerow(product)

    # ==========================================
    # GET CATEGORY PRODUCT URLS
    # ==========================================

    def collect_product_urls(self, page):

        product_urls = []
        seen_urls = set()

        page_number = 1
        current_url = BASE_URL

        while True:

            print("\n========================================")
            print(f"COLLECTING CATEGORY PAGE {page_number}")
            print("========================================")

            print("URL:", current_url)

            try:

                page.goto(
                    current_url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

            except Exception as e:

                print("Page loading error:", e)
                break

            page.wait_for_timeout(3000)

            html = page.content()

            products = self.parser.parse_products(html)

            print("Products found:", len(products))

            if not products:

                print("No products found.")
                break

            new_products = 0

            for product in products:

                url = product.get("url", "").strip()

                if not url:
                    continue

                if url.startswith("/"):

                    url = (
                        "https://www.sephora.sg"
                        + url
                    )

                if url not in seen_urls:

                    seen_urls.add(url)
                    product_urls.append(url)

                    new_products += 1

            print("New URLs:", new_products)
            print("Total unique URLs:", len(product_urls))

            # Find next page

            next_url = None

            links = page.locator("a").all()

            for link in links:

                try:

                    href = link.get_attribute("href")

                    if not href:
                        continue

                    if href.startswith("/"):

                        full_href = (
                            "https://www.sephora.sg"
                            + href
                        )

                    else:

                        full_href = href

                    if "/categories/makeup?page=" in full_href:

                        try:

                            next_page_number = int(
                                full_href
                                .split("?page=")[1]
                                .split("&")[0]
                            )

                            if (
                                next_page_number
                                == page_number + 1
                            ):

                                next_url = full_href
                                break

                        except ValueError:

                            pass

                except Exception:

                    continue

            if not next_url:

                print("\nNo next category page.")
                break

            current_url = next_url
            page_number += 1

        print("\n========================================")
        print("URL COLLECTION COMPLETED")
        print("========================================")
        print("Category pages:", page_number)
        print("Unique product URLs:", len(product_urls))

        return product_urls

    # ==========================================
    # SCRAPE PRODUCT PAGES
    # ==========================================

    def scrape_products(self, page, product_urls):

        total = len(product_urls)

        print("\n========================================")
        print("STARTING PRODUCT SCRAPING")
        print("========================================")
        print("Total products:", total)

        for index, url in enumerate(
            product_urls,
            start=1
        ):

            print("\n----------------------------------------")
            print(f"PRODUCT {index} / {total}")
            print("----------------------------------------")

            print(url)

            try:

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                page.wait_for_timeout(3000)

                html = page.content()

                product = self.parser.parse_product_page(
                    html,
                    url
                )

                # Basic validation

                if not product.get("name"):

                    print("WARNING: Product name empty")
                    print("Skipping:", url)

                    continue

                self.products.append(product)

                self.save_product(product)

                print("Name:", product["name"])
                print("Brand:", product["brand"])
                print("Price:", product["price"])
                print("Rating:", product["rating"])
                print("Saved successfully.")

            except Exception as e:

                print("ERROR:", e)
                print("Skipping product.")

                continue

            time.sleep(0.5)

        print("\n========================================")
        print("PRODUCT SCRAPING COMPLETED")
        print("========================================")
        print("Products scraped:", len(self.products))
        print("Output:", OUTPUT_FILE)

    # ==========================================
    # MAIN CRAWLER
    # ==========================================

    def crawl(self):

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

            # ----------------------------------
            # STEP 1
            # Collect all product URLs
            # ----------------------------------

            product_urls = self.collect_product_urls(
                page
            )

            # ----------------------------------
            # STEP 2
            # Scrape product pages
            # ----------------------------------

            self.scrape_products(
                page,
                product_urls
            )

            browser.close()


# ==========================================
# RUN
# ==========================================

if __name__ == "__main__":

    crawler = SephoraCrawler()

    crawler.crawl()