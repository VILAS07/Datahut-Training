import logging
import csv
import re
import os
import time
from parsel import Selector
from settings import requests, HEADERS


# -------------------- CONFIGURATION --------------------

BASE_URL = "https://shop.mango.com"
PRODUCTS_FILE = "mango_products.csv"
LINKS_FILE = "mango_product_links.csv"

REQUEST_DELAY = 1.0
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

FIELDNAMES = [
    "Product Name",
    "Size",
    "Product Description",
    "Category / Product Type",
    "Price",
    "Currency",
    "Main Product Image URL",
    "PDP URL",
    "Rank",
    "Colour",
    "Gender",
    "Material / Fabric",
    "Fit / Sizing Information",
    "Occasion / Style",
]

GENDERS = {"women", "men", "teen", "kids"}


class Parser:
    """parser"""

    def __init__(self):
        self.queue = ''   # queue connect
        self.mongo = ''   # mongo connect
        self.last_request_time = 0.0

    def start(self):
        """start code"""

        # Read discovered product URLs from the crawler.
        if not os.path.exists(LINKS_FILE):
            logging.error("Product links file not found: %s", LINKS_FILE)
            return

        if (
            not os.path.exists(PRODUCTS_FILE)
            or os.path.getsize(PRODUCTS_FILE) == 0
        ):
            with open(
                PRODUCTS_FILE,
                "w",
                newline="",
                encoding="utf-8-sig",
            ) as file:
                csv.DictWriter(
                    file,
                    fieldnames=FIELDNAMES,
                ).writeheader()

        try:
            with open(
                LINKS_FILE,
                newline="",
                encoding="utf-8-sig",
            ) as file:
                metas = list(csv.DictReader(file))

        except (OSError, csv.Error):
            logging.exception("Failed to read product links")
            return

        saved_urls = set()

        try:
            with open(
                PRODUCTS_FILE,
                newline="",
                encoding="utf-8-sig",
            ) as file:
                for row in csv.DictReader(file):
                    url = row.get("PDP URL", "").strip()
                    if url:
                        saved_urls.add(url.rstrip("/"))

        except (OSError, csv.Error):
            logging.exception("Failed to read existing products")
            return

        for rank, meta in enumerate(metas, start=1):
            url = meta.get("PDP URL", "").strip()

            if not url or url.rstrip("/") in saved_urls:
                continue

            response = None

            for attempt in range(MAX_RETRIES):
                elapsed = time.monotonic() - self.last_request_time

                if elapsed < REQUEST_DELAY:
                    time.sleep(REQUEST_DELAY - elapsed)

                try:
                    response = requests.get(
                        url,
                        headers=HEADERS,
                        impersonate="chrome124",
                        timeout=REQUEST_TIMEOUT,
                    )

                    self.last_request_time = time.monotonic()

                    if response.status_code in (403, 503, 429):
                        logging.warning(
                            "HTTP %s: %s",
                            response.status_code,
                            url,
                        )

                        if attempt < MAX_RETRIES - 1:
                            time.sleep(5 * (attempt + 1))
                            continue

                        response = None
                        break

                    response.raise_for_status()
                    break

                except Exception:
                    logging.warning(
                        "Request failed (%s/%s): %s",
                        attempt + 1,
                        MAX_RETRIES,
                        url,
                    )

                    response = None

                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2 * (attempt + 1))

            if response is not None:
                self.parse_item(url, response, rank)
                saved_urls.add(url.rstrip("/"))

    def parse_item(self, url, response, rank=1):
        """item part"""

        sel = Selector(text=response.text)

        # XPATH
        PRODUCT_NAME_XPATH = "normalize-space(string(//h1))"
        IMAGES_XPATH = (
            "//img/@src | //img/@data-src | //img/@data-original"
        )
        BREADCRUMBS_XPATH = '//a[contains(@href, "/in/en/c/")]'
        DESCRIPTION_XPATH = '//*[contains(@class, "textContent")]//text()'
        COLOUR_XPATH = (
            '//*[contains(@class, "ColorsSelector")]'
            '//p[contains(@class, "title")]/span[last()]/text()'
        )
        PRICE_XPATH = '//*[contains(@class, "SinglePrice")]//text()'
        SIZES_XPATH = "//button[normalize-space()]"

        # EXTRACT
        product_name = sel.xpath(
            PRODUCT_NAME_XPATH
        ).get(default="").strip()

        images = sel.xpath(IMAGES_XPATH).getall()
        breadcrumbs_list = sel.xpath(BREADCRUMBS_XPATH)
        description_parts = sel.xpath(DESCRIPTION_XPATH).getall()
        colour = sel.xpath(COLOUR_XPATH).get(default="").strip()
        price_text = " ".join(
            text.strip()
            for text in sel.xpath(PRICE_XPATH).getall()
            if text.strip()
        )

        # CLEAN
        clean_images = []

        for image in images:
            image = image.strip()

            if image.startswith("//"):
                image = "https:" + image

            if (
                image.startswith("https://media.mango.com/")
                and image not in clean_images
            ):
                clean_images.append(image)

        breadcrumbs = []

        for breadcrumb in breadcrumbs_list:
            value = " ".join(
                text.strip()
                for text in breadcrumb.xpath(".//text()").getall()
                if text.strip()
            )

            if value and value not in breadcrumbs:
                breadcrumbs.append(value)

        description = re.sub(
            r"\s+",
            " ",
            " ".join(
                text.strip()
                for text in description_parts
                if text.strip()
            ),
        ).strip()

        colour = (
            colour.replace("Colour ", "")
            .replace(" selected", "")
        )

        price_match = re.search(
            r"(?:Rs\.?|₹)\s*[\d,]+(?:\.\d{1,2})?",
            price_text,
        )
        price = price_match.group(0) if price_match else ""

        # Extract available clothing sizes.
        valid_sizes = {
            "XXS", "XS", "S", "M", "L", "XL", "XXL",
            "1XL", "2XL", "3XL", "4XL",
            "34", "36", "38", "40", "42", "44", "46", "48",
        }

        sizes = []

        for button in sel.xpath(SIZES_XPATH):
            size_value = button.xpath(
                "normalize-space(string(.))"
            ).get(default="").strip()

            button_text = " ".join(button.xpath(".//text()").getall())

            unavailable = re.search(
                r"not available|unavailable|sold out",
                button_text,
                re.I,
            )

            if size_value in valid_sizes and not unavailable:
                if size_value not in sizes:
                    sizes.append(size_value)

        gender = ""

        for part in url.split("/"):
            if part in GENDERS:
                gender = part.title()
                break

        # ITEM YEILD
        item = {
            "Product Name": product_name,
            "Size": ", ".join(sizes),
            "Product Description": description,
            "Category / Product Type": " > ".join(breadcrumbs),
            "Price": price,
            "Currency": "INR",
            "Main Product Image URL": clean_images[0] if clean_images else "",
            "PDP URL": url,
            "Rank": rank,
            "Colour": colour,
            "Gender": gender,
            "Material / Fabric": "",
            "Fit / Sizing Information": "",
            "Occasion / Style": "",
        }

        if not product_name:
            logging.warning("Product name not found: %s", url)
            return

        try:
            with open(
                PRODUCTS_FILE,
                "a",
                newline="",
                encoding="utf-8-sig",
            ) as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=FIELDNAMES,
                )
                writer.writerow(item)

            logging.info("Product saved: %s", product_name)

        except Exception:
            logging.exception("Failed to save product: %s", url)

    def close(self):
        """connection close"""

        if self.mongo and hasattr(self.mongo, "close"):
            self.mongo.close()

        if self.queue and hasattr(self.queue, "close"):
            self.queue.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    parser_obj = Parser()
    parser_obj.start()
    parser_obj.close()
