import json
import logging
import requests

from urllib.parse import urljoin
from parsel import Selector

from settings import START_URL
from export import export_to_csv
from parser import Parser


class Crawler:
    """Crawling OpenSooq property URLs"""

    def __init__(self):
        self.session = requests.Session()
        self.urls = []
        self.items = []

    def start(self):
        """Request and parse all listing pages"""

        current_url = START_URL
        current_page = 1

        while current_url:

            logging.info(
                f"Requesting page {current_page}: {current_url}"
            )

            response = self.session.get(
                current_url,
                headers={
                    "User-Agent": "Mozilla/5.0"
                },
                timeout=30
            )

            logging.info(
                f"Status Code: {response.status_code}"
            )

            if response.status_code != 200:
                logging.warning(
                    f"Request failed: {response.status_code}"
                )
                break

            # Parse listing page
            selector = Selector(text=response.text)

            # Collect child URLs from current page
            new_urls = self.parse_item(response)

            logging.info(
                f"Page {current_page} new URLs: {len(new_urls)}"
            )

            # Parse child URLs immediately
            self.parse_children(new_urls)

            logging.info(
                f"Total parsed listings: {len(self.items)}"
            )

            # Find next page
            next_url = self.get_next_page(
                selector,
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

        # Export all scraped data
        export_to_csv(self.items)

    def parse_item(self, response):
        """Extract child URLs from current listing page"""

        selector = Selector(text=response.text)

        json_ld_list = selector.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall()

        new_urls = []

        for json_text in json_ld_list:

            try:
                data = json.loads(json_text)

                graph = data.get(
                    "@graph",
                    []
                )

                for graph_item in graph:

                    if graph_item.get(
                        "@type"
                    ) != "ItemList":
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

            except json.JSONDecodeError:
                continue

        return new_urls

    def parse_children(self, urls):
        """Parse child listing pages immediately"""

        for url in urls:

            parser = Parser(url)

            data = parser.parse()

            if data:

                logging.info(
                    f"Parsed: {data}"
                )

                self.items.append(data)

    def get_next_page(
        self,
        selector,
        current_page,
        current_url
    ):
        """Find the next pagination page"""

        page_links = selector.xpath(
            '//a[contains(@href, "page=")]/@href'
        ).getall()

        next_page = current_page + 1

        for href in page_links:

            if f"page={next_page}" in href:

                next_url = urljoin(
                    current_url,
                    href
                )

                return next_url

        return None

    def close(self):
        """Close the session"""

        self.session.close()


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s:%(message)s"
    )

    crawler = Crawler()

    try:
        crawler.start()

    finally:
        crawler.close()