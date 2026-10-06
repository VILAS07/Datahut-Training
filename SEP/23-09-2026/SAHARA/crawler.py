from playwright.sync_api import sync_playwright
from playwright.sync_api import Error as PlaywrightError
import time

from parser import SephoraParser
from export import MongoDBExporter


BASE_URL = "https://www.sephora.sg/categories/makeup"


class SephoraCrawler:

    def __init__(self):

        self.parser = SephoraParser()

        self.exporter = MongoDBExporter()

        self.seen_urls = set()

        self.products_scraped = 0

        self.products_saved = 0

    # ==========================================
    # CREATE PAGE
    # ==========================================

    def create_page(self, browser):

        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            )
        )

        return page

    # ==========================================
    # GET CATEGORY URL
    # ==========================================

    def get_category_url(self, page_number):

        if page_number == 1:

            return BASE_URL

        return f"{BASE_URL}?page={page_number}"

    # ==========================================
    # COLLECT PRODUCTS FROM ONE CATEGORY PAGE
    # ==========================================

    def collect_category_products(
        self,
        page,
        page_number
    ):

        current_url = self.get_category_url(
            page_number
        )

        print("\n========================================")
        print(
            f"COLLECTING CATEGORY PAGE {page_number}"
        )
        print("========================================")

        print("URL:", current_url)

        page.goto(
            current_url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(3000)

        html = page.content()

        products = self.parser.parse_products(
            html
        )

        print(
            "Products found:",
            len(products)
        )

        if not products:

            print("No products found.")

            return []

        product_urls = []

        new_products = 0

        for product in products:

            url = product.get(
                "url",
                ""
            ).strip()

            if not url:
                continue

            if url.startswith("/"):

                url = (
                    "https://www.sephora.sg"
                    + url
                )

            if url not in self.seen_urls:

                self.seen_urls.add(url)

                product_urls.append(url)

                new_products += 1

        print(
            "New URLs:",
            new_products
        )

        print(
            "Total unique URLs:",
            len(self.seen_urls)
        )

        return product_urls

    # ==========================================
    # SCRAPE ONE PRODUCT
    # ==========================================

    def scrape_product(
        self,
        page,
        url
    ):

        print("\n----------------------------------------")

        print("PRODUCT")

        print(url)

        print("----------------------------------------")

        try:

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            page.wait_for_timeout(3000)

            html = page.content()

            product = (
                self.parser.parse_product_page(
                    html,
                    url
                )
            )

            # ------------------------------
            # VALIDATION
            # ------------------------------

            if not product.get("name"):

                print(
                    "WARNING: Product name empty"
                )

                print(
                    "Skipping:",
                    url
                )

                return True

            # ------------------------------
            # SAVE TO MEMORY
            # ------------------------------

            self.products_scraped += 1

            # ------------------------------
            # SAVE TO MONGODB IMMEDIATELY
            # ------------------------------

            saved = self.exporter.export_one(
                product
            )

            if saved:

                self.products_saved += 1

            print(
                "Name:",
                product["name"]
            )

            print(
                "Brand:",
                product["brand"]
            )

            print(
                "Price:",
                product["price"]
            )

            print(
                "MongoDB total:",
                self.exporter.count()
            )

            return True

        except PlaywrightError as e:

            print(
                "PLAYWRIGHT ERROR:",
                e
            )

            return False

        except Exception as e:

            print(
                "ERROR:",
                e
            )

            return True

    # ==========================================
    # SCRAPE CATEGORY PRODUCTS
    # ==========================================

    def scrape_category_products(
        self,
        page,
        product_urls
    ):

        total = len(product_urls)

        print("\n========================================")

        print(
            "SCRAPING PRODUCTS FROM CATEGORY PAGE"
        )

        print("Total products:", total)

        print("========================================")

        for index, url in enumerate(
            product_urls,
            start=1
        ):

            print(
                f"\nPRODUCT {index} / {total}"
            )

            success = self.scrape_product(
                page,
                url
            )

            # If Playwright page died,
            # stop this batch and let caller retry.
            if not success:

                print(
                    "Page/browser problem detected."
                )

                print(
                    "Stopping current category batch."
                )

                return False

            time.sleep(0.5)

        return True

    # ==========================================
    # MAIN CRAWLER
    # ==========================================

    def crawl(self):

        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=False
            )

            page = self.create_page(
                browser
            )

            page_number = 1

            max_retries = 3

            try:

                while True:

                    print("\n\n")
                    print(
                        "########################################"
                    )

                    print(
                        f"STARTING CATEGORY PAGE {page_number}"
                    )

                    print(
                        "########################################"
                    )

                    # ----------------------------------
                    # RETRY CATEGORY PAGE
                    # ----------------------------------

                    category_success = False

                    for retry in range(
                        1,
                        max_retries + 1
                    ):

                        try:

                            product_urls = (
                                self.collect_category_products(
                                    page,
                                    page_number
                                )
                            )

                            category_success = True

                            break

                        except Exception as e:

                            print(
                                "\nCATEGORY PAGE ERROR:"
                            )

                            print(e)

                            print(
                                f"Retry {retry}/{max_retries}"
                            )

                            # ----------------------------------
                            # RESTART BROWSER
                            # ----------------------------------

                            try:

                                if not browser.is_connected():

                                    print(
                                        "Browser is closed."
                                    )

                            except Exception:

                                pass

                            try:

                                page.close()

                            except Exception:

                                pass

                            try:

                                browser.close()

                            except Exception:

                                pass

                            print(
                                "Restarting browser..."
                            )

                            browser = p.chromium.launch(
                                headless=False
                            )

                            page = self.create_page(
                                browser
                            )

                            time.sleep(3)

                    # ----------------------------------
                    # IF PAGE STILL FAILED
                    # ----------------------------------

                    if not category_success:

                        print(
                            "\nCould not process category page."
                        )

                        print(
                            "Stopping scraper safely."
                        )

                        break

                    # ----------------------------------
                    # NO PRODUCTS = END
                    # ----------------------------------

                    if not product_urls:

                        print(
                            "\nNo products found."
                        )

                        print(
                            "Category scraping completed."
                        )

                        break

                    # ----------------------------------
                    # SCRAPE PRODUCTS
                    # ----------------------------------

                    product_success = (
                        self.scrape_category_products(
                            page,
                            product_urls
                        )
                    )

                    # ----------------------------------
                    # RESTART PAGE IF PRODUCT SCRAPING
                    # FAILED
                    # ----------------------------------

                    if not product_success:

                        print(
                            "\nProduct scraping interrupted."
                        )

                        print(
                            "Restarting browser..."
                        )

                        try:

                            browser.close()

                        except Exception:

                            pass

                        browser = p.chromium.launch(
                            headless=False
                        )

                        page = self.create_page(
                            browser
                        )

                        # Retry the same category page
                        continue

                    # ----------------------------------
                    # NEXT CATEGORY
                    # ----------------------------------

                    print("\n========================================")

                    print(
                        f"CATEGORY PAGE {page_number} COMPLETED"
                    )

                    print("MongoDB records:")

                    print(
                        self.exporter.count()
                    )

                    print("========================================")

                    page_number += 1

                    time.sleep(2)

            finally:

                print("\n========================================")

                print("SCRAPER FINISHED")

                print(
                    "Products scraped:",
                    self.products_scraped
                )

                print(
                    "MongoDB records:",
                    self.exporter.count()
                )

                print("========================================")

                try:

                    self.exporter.close()

                except Exception:

                    pass

                try:

                    browser.close()

                except Exception:

                    pass


# ==========================================
# RUN
# ==========================================

if __name__ == "__main__":

    crawler = SephoraCrawler()

    crawler.crawl()