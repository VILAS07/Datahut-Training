import json
import logging
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from settings import START_URL
from parser import Parser
from export import save_to_mongodb


class Crawler:
    """Crawl OpenSooq using Playwright"""

    def __init__(self):
        self.urls = []
        self.items = []

    def start(self):
        """Open listing pages and parse property pages"""

        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=False
            )

            page = browser.new_page()

            current_url = START_URL
            current_page = 1

            while current_url:

                logging.info(
                    f"Requesting page {current_page}: {current_url}"
                )

                page.goto(
                    current_url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                page.wait_for_timeout(2000)

                logging.info(
                    f"Loaded page {current_page}"
                )

                # Get page HTML
                html = page.content()

                # Extract property URLs
                new_urls = self.parse_item(html)

                logging.info(
                    f"Page {current_page} new URLs: {len(new_urls)}"
                )

                # Parse each property
                self.parse_children(
                    new_urls,
                    page
                )

                logging.info(
                    f"Total parsed listings: {len(self.items)}"
                )

                # Find next page
                next_url = self.get_next_page(
                    html,
                    current_page,
                    current_url
                )

                if not next_url:
                    logging.info(
                        "No next page found. Stopping."
                    )
                    break

                current_page += 1
                current_url = next_url

            logging.info(
                f"Total child URLs: {len(self.urls)}"
            )

            logging.info(
                f"Total parsed listings: {len(self.items)}"
            )

            browser.close()

    def parse_item(self, html):
        """Extract property URLs from listing page"""

        from parsel import Selector

        selector = Selector(text=html)

        json_ld_list = selector.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall()

        new_urls = []

        for json_text in json_ld_list:

            try:
                data = json.loads(json_text)

            except json.JSONDecodeError:
                continue

            graph = data.get("@graph", [])

            for graph_item in graph:

                if graph_item.get("@type") != "ItemList":
                    continue

                for element in graph_item.get(
                    "itemListElement",
                    []
                ):

                    item = element.get(
                        "item",
                        {}
                    )

                    url = item.get("url")

                    if not url:
                        url = item.get(
                            "itemOffered",
                            {}
                        ).get("url")

                    if (
                        url
                        and "/en/search/" in url
                        and url not in self.urls
                    ):

                        logging.info(
                            f"Child URL: {url}"
                        )

                        self.urls.append(url)
                        new_urls.append(url)

        return new_urls

    def parse_children(self, urls, page):
        """Parse property pages using Playwright"""

        for url in urls:

            parser = Parser(
                url,
                page
            )

            data = parser.parse()

            if data:
                self.items.append(data)
                save_to_mongodb(data)

    def get_next_page(
        self,
        html,
        current_page,
        current_url
    ):
        """Find next pagination page"""

        from parsel import Selector

        selector = Selector(text=html)

        page_links = selector.xpath(
            '//a[contains(@href, "page=")]/@href'
        ).getall()

        next_page = current_page + 1

        for href in page_links:

            if f"page={next_page}" in href:

                return urljoin(
                    current_url,
                    href
                )

        return None


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s:%(message)s"
    )

    crawler = Crawler()

    crawler.start()