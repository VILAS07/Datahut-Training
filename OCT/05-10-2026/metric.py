import asyncio
from urllib.parse import urljoin
from playwright.async_api import async_playwright
import cloakbrowser


BASE_URL = "https://noragardner.com"

COLLECTION_URL = (
    "https://noragardner.com/collections/dresses"
)

PRODUCT_LIMIT = 20
MAX_PAGES = 3


class Metrics:
    def __init__(self):
        self.request_count = 0
        self.product_requests = 0
        self.shopify_requests = 0
        self.review_requests = 0
        self.pages_visited = 0
        self.products_found = set()

    def print_result(self):
        print("\n" + "=" * 80)
        print("FEASIBILITY METRICS")
        print("=" * 80)

        print(f"Record Count  : {len(self.products_found)}")
        print(f"Record Depth  : {self.pages_visited}")
        print(f"Request Count : {self.request_count}")

        print("\nREQUEST BREAKDOWN")
        print("-" * 80)
        print(f"Product requests : {self.product_requests}")
        print(f"Shopify requests : {self.shopify_requests}")
        print(f"Review requests  : {self.review_requests}")

        print("\nRANGE ESTIMATE")
        print("-" * 80)

        # Minimum = records actually found
        min_records = len(self.products_found)

        # Estimate based on tested pagination depth
        max_records = min_records * max(1, self.pages_visited)

        # Conservative request range
        min_requests = self.request_count
        max_requests = self.request_count + (
            max_records * 3
        )

        print(f"Record Count  : {min_records}–{max_records}")
        print(f"Record Depth  : 1–{max(1, self.pages_visited)}")
        print(f"Request Count : {min_requests}–{max_requests}")

        print("=" * 80)


async def main():

    metrics = Metrics()

    print("=" * 80)
    print("NORA GARDNER FEASIBILITY METRICS TEST")
    print("=" * 80)

    async with async_playwright() as pw:

        print("\n[+] Starting CloakBrowser...")

        browser = await cloakbrowser.launch_async(
            headless=False,
            stealth_args=True,
            humanize=True,
        )

        context = await browser.new_context(
            viewport={
                "width": 1440,
                "height": 900
            }
        )

        page = await context.new_page()

        # ---------------------------------------------------------
        # COUNT ALL REQUESTS
        # ---------------------------------------------------------

        def count_request(request):

            metrics.request_count += 1

            url = request.url

            if "/products/" in url and not url.endswith(".js"):
                metrics.product_requests += 1

            elif url.endswith(".js"):
                metrics.shopify_requests += 1

            elif "client_reviews" in url:
                metrics.review_requests += 1

        page.on("request", count_request)

        # ---------------------------------------------------------
        # TEST COLLECTION PAGES
        # ---------------------------------------------------------

        for page_number in range(1, MAX_PAGES + 1):

            if page_number == 1:
                url = COLLECTION_URL
            else:
                url = f"{COLLECTION_URL}?page={page_number}"

            print("\n" + "=" * 80)
            print(f"LISTING PAGE {page_number}")
            print(url)
            print("=" * 80)

            try:

                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                await page.wait_for_timeout(3000)

                metrics.pages_visited += 1

                print(
                    f"[+] Page loaded: {page.url}"
                )

            except Exception as e:

                print(
                    f"[ERROR] Page failed: {e}"
                )

                continue

            # -----------------------------------------------------
            # PRODUCT LINKS
            # -----------------------------------------------------

            links = await page.locator(
                'a[href*="/products/"]'
            ).evaluate_all(
                """
                elements => elements.map(
                    e => e.href
                )
                """
            )

            unique_links = []

            for link in links:

                if link not in unique_links:
                    unique_links.append(link)

            print(
                f"[+] Product links found: {len(unique_links)}"
            )

            for link in unique_links:

                metrics.products_found.add(link)

                print(
                    f"[PRODUCT] {link}"
                )

                if len(metrics.products_found) >= PRODUCT_LIMIT:
                    break

            if len(metrics.products_found) >= PRODUCT_LIMIT:
                break

        # ---------------------------------------------------------
        # TEST SHOPIFY JSON + REVIEW API
        # ---------------------------------------------------------

        print("\n" + "=" * 80)
        print("TESTING PRODUCT + REVIEW REQUESTS")
        print("=" * 80)

        for index, product_url in enumerate(
            list(metrics.products_found),
            start=1
        ):

            print(
                f"\n[{index}/{len(metrics.products_found)}] "
                f"{product_url}"
            )

            # -----------------------------------------------------
            # SHOPIFY JSON
            # -----------------------------------------------------

            product_path = product_url.split(
                "/products/"
            )[-1].split("?")[0]

            shopify_url = (
                f"{BASE_URL}/products/"
                f"{product_path}.js"
            )

            print(
                f"[+] Shopify JSON: {shopify_url}"
            )

            try:

                response = await context.request.get(
                    shopify_url,
                    timeout=30000
                )

                print(
                    f"[SHOPIFY] HTTP {response.status}"
                )

                if response.ok:

                    data = await response.json()

                    product_id = data.get("id")

                    print(
                        f"[SHOPIFY ID] {product_id}"
                    )

                    # -------------------------------------------------
                    # KLAVIYO REVIEW API
                    # -------------------------------------------------

                    if product_id:

                        review_url = (
                            "https://fast.a.klaviyo.com/"
                            "reviews/api/client_reviews/"
                            f"{product_id}/"
                            "?product_id="
                            f"{product_id}"
                            "&company_id=HWxMF4"
                            "&limit=5"
                            "&offset=0"
                            "&sort=3"
                            "&filter="
                            "&type=reviews"
                            "&media=false"
                            "&kl_review_uuid="
                            "&preferred_country=US"
                            "&tz=America%2FNew_York"
                        )

                        print(
                            f"[+] Review API: {review_url}"
                        )

                        try:

                            review_response = (
                                await context.request.get(
                                    review_url,
                                    timeout=30000
                                )
                            )

                            print(
                                "[REVIEW API] HTTP",
                                review_response.status
                            )

                        except Exception as e:

                            print(
                                f"[REVIEW ERROR] {e}"
                            )

            except Exception as e:

                print(
                    f"[SHOPIFY ERROR] {e}"
                )

            await asyncio.sleep(1)

        # ---------------------------------------------------------
        # FINAL METRICS
        # ---------------------------------------------------------

        metrics.print_result()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())