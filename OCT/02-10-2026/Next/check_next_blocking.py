from playwright.sync_api import sync_playwright
import time

URLS = [
    ("Mini dress", "https://www.next.co.uk/search?w=mini%20dress"),
    ("Midi dress", "https://www.next.co.uk/search?w=midi%20dress"),
]

def main():
    crawler_success = 0
    crawler_failure = 0

    parser_success = 0
    parser_failure = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for keyword, url in URLS:
            print("=" * 80)
            print(f"KEYWORD: {keyword}")
            print(f"URL: {url}")

            # -------------------------
            # CRAWLER BLOCKING CHECK
            # -------------------------
            try:
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )

                status = response.status if response else None
                final_url = page.url

                print(f"STATUS: {status}")
                print(f"FINAL URL: {final_url}")

                if response and 200 <= status < 400:
                    crawler_success += 1
                    print("CRAWLER: SUCCESS")
                else:
                    crawler_failure += 1
                    print("CRAWLER: FAILURE")

            except Exception as e:
                crawler_failure += 1
                print(f"CRAWLER: FAILURE - {e}")
                continue

            # -------------------------
            # PARSER BLOCKING CHECK
            # -------------------------
            try:
                page.wait_for_timeout(3000)

                title = page.title()

                # Look for actual product/result content
                product_text = page.locator(
                    "body"
                ).inner_text(timeout=10000)

                if product_text and len(product_text.strip()) > 200:
                    parser_success += 1
                    print("PARSER: SUCCESS")
                    print(f"TITLE: {title}")
                else:
                    parser_failure += 1
                    print("PARSER: FAILURE")

            except Exception as e:
                parser_failure += 1
                print(f"PARSER: FAILURE - {e}")

            time.sleep(1)

        browser.close()

    # -------------------------
    # CALCULATE RESULTS
    # -------------------------
    crawler_total = crawler_success + crawler_failure
    parser_total = parser_success + parser_failure

    crawler_success_rate = (
        crawler_success / crawler_total * 100
        if crawler_total else 0
    )

    crawler_failure_rate = (
        crawler_failure / crawler_total * 100
        if crawler_total else 0
    )

    parser_success_rate = (
        parser_success / parser_total * 100
        if parser_total else 0
    )

    parser_failure_rate = (
        parser_failure / parser_total * 100
        if parser_total else 0
    )

    print("\n")
    print("=" * 80)
    print("FINAL RESULT")
    print("=" * 80)

    print("\nCrawler Blocking:")
    print(f"total_requests: {crawler_total}")
    print(f"success_rate_percent: {crawler_success_rate:.1f}")
    print(f"failure_rate_percent: {crawler_failure_rate:.1f}")

    print("\nParser Blocking:")
    print(f"total_requests: {parser_total}")
    print(f"success_rate_percent: {parser_success_rate:.1f}")
    print(f"failure_rate_percent: {parser_failure_rate:.1f}")


if __name__ == "__main__":
    main()