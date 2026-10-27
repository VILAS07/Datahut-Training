import csv
import logging
import os
import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse

from parsel import Selector
from settings import requests, HEADERS


# -------------------- CONFIGURATION --------------------

BASE_URL = "https://shop.mango.com"
API_BASE_URL = "https://api.shop.mango.com"

SECTION_URLS = [
    "/in/en/h/women",
    "/in/en/h/men",
    "/in/en/h/teen",
    "/in/en/h/kids",
]

PRODUCTS_FILE = "mango_products.csv"
LINKS_FILE = "mango_product_links.csv"

REQUEST_DELAY = 1.0
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

COUNTRY_ISO = "in"
LANGUAGE_ISO = "en"

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

LINK_FIELDS = ["Product ID", "Color ID", "PDP URL"]

GENDERS = {"women", "men", "teen", "kids"}


class Parser:

    def __init__(self):
        self.visited_categories = set()
        self.processed_catalogs = set()

        # (product_id, color_id) -> PDP URL
        self.product_urls = {}

        # Gender -> observed PDP URL template.
        # Used only when an exact PDP URL cannot be found.
        self.product_templates = {}

        self.saved_variant_keys = set()
        self.saved_final_urls = set()

        self.request_count = 0
        self.saved_count = 0
        self.failed_count = 0
        self.last_request_time = 0.0

    # -------------------- URL HELPERS --------------------

    @staticmethod
    def clean_url(url):
        absolute = urljoin(BASE_URL, url.strip())
        parsed = urlparse(absolute)

        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            "",
            "",
            "",
        ))

    @staticmethod
    def variant_key_from_url(url):
        path = urlparse(url).path

        match = re.search(r"/(\d+)/(\d+)/(\d+)/?$", path)

        if match:
            return match.group(1), match.group(2)

        return None

    @staticmethod
    def template_from_url(url):
        path = urlparse(url).path.rstrip("/")
        match = re.search(r"/(\d+)/(\d+)/(\d+)$", path)

        if match:
            return path[:match.start()]

        return ""

    @staticmethod
    def get_gender(url):
        parts = urlparse(url).path.split("/")

        for part in parts:
            if part in GENDERS:
                return part.title()

        return ""

    @staticmethod
    def get_catalog_id(html):
        patterns = [
            r'"catalogId"\s*:\s*"([^"]+)"',
            r'\\"catalogId\\"\s*:\s*\\"([^"]+)\\"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)

            if match:
                return match.group(1)

        return ""

    @staticmethod
    def extract_pdp_urls(html):
        """Find actual product detail URLs embedded in page HTML."""

        html = html.replace(r"\/", "/")
        html = html.replace("&amp;", "&")

        paths = re.findall(
            r'/in/en/p/[^"\'\s<>\\]+',
            html,
        )

        urls = []

        for path in paths:
            path = path.rstrip(",);]")
            path = path.split("?")[0]

            if path.startswith("/in/en/p/"):
                urls.append(urljoin(BASE_URL, path))

        return list(dict.fromkeys(urls))

    # -------------------- REQUEST HANDLING --------------------

    def fetch(self, url, retries=MAX_RETRIES):

        for attempt in range(retries):

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
                self.request_count += 1

                if response.status_code == 429:
                    wait = min(60, 10 * (attempt + 1))

                    logging.warning(
                        "HTTP 429. Waiting %s seconds: %s",
                        wait,
                        url,
                    )

                    time.sleep(wait)
                    continue

                if response.status_code in (403, 503):
                    logging.warning(
                        "HTTP %s: %s",
                        response.status_code,
                        url,
                    )

                    if attempt < retries - 1:
                        time.sleep(5 * (attempt + 1))
                        continue

                    return None

                response.raise_for_status()
                return response

            except Exception as error:
                logging.warning(
                    "Request failed (%s/%s): %s",
                    attempt + 1,
                    retries,
                    error,
                )

                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))

        logging.error("Giving up on URL: %s", url)
        return None

    # -------------------- CSV / RESUME --------------------

    def ensure_csvs(self):

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

        if (
            not os.path.exists(LINKS_FILE)
            or os.path.getsize(LINKS_FILE) == 0
        ):
            with open(
                LINKS_FILE,
                "w",
                newline="",
                encoding="utf-8-sig",
            ) as file:
                csv.DictWriter(
                    file,
                    fieldnames=LINK_FIELDS,
                ).writeheader()

    def load_existing_data(self):
        """Load previously discovered links and saved product variants."""

        try:
            with open(
                LINKS_FILE,
                newline="",
                encoding="utf-8-sig",
            ) as file:

                for row in csv.DictReader(file):
                    pid = row.get("Product ID", "").strip()
                    cid = row.get("Color ID", "").strip()
                    url = row.get("PDP URL", "").strip()

                    if pid and cid and url:
                        self.product_urls.setdefault(
                            (pid, cid),
                            url,
                        )

        except (OSError, csv.Error) as error:
            logging.warning("Cannot load links CSV: %s", error)

        try:
            with open(
                PRODUCTS_FILE,
                newline="",
                encoding="utf-8-sig",
            ) as file:

                for row in csv.DictReader(file):
                    url = row.get("PDP URL", "").strip()

                    if not url:
                        continue

                    key = self.variant_key_from_url(url)

                    if key:
                        self.saved_variant_keys.add(key)

                    self.saved_final_urls.add(self.clean_url(url))

        except (OSError, csv.Error) as error:
            logging.warning("Cannot load products CSV: %s", error)

        logging.info(
            "Existing links: %s | Already saved variants: %s",
            len(self.product_urls),
            len(self.saved_variant_keys),
        )

    def save_link(self, pid, cid, url):
        """Persist a discovered link immediately."""

        key = (str(pid), str(cid))

        if key in self.product_urls:
            return

        with open(
            LINKS_FILE,
            "a",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=LINK_FIELDS,
            )

            writer.writerow({
                "Product ID": pid,
                "Color ID": cid,
                "PDP URL": url,
            })

            file.flush()

        self.product_urls[key] = url

    # -------------------- CATALOG API --------------------

    def fetch_catalog_items(self, catalog_id):

        api_url = (
            f"{API_BASE_URL}/cs/product-lists-drive-thru/v2/"
            f"channels/shop/countries/{COUNTRY_ISO}/"
            f"catalogs/{catalog_id}"
        )

        unique_items = {}
        page = 1

        while True:

            url = (
                f"{api_url}?languageIso={LANGUAGE_ISO}"
                f"&page={page}"
            )

            response = self.fetch(url)

            if response is None:
                break

            try:
                data = response.json()

            except ValueError:
                logging.warning("Invalid catalog JSON: %s", url)
                break

            items = data.get("items") or []
            total_pages = int(data.get("totalPages") or 1)

            for item in items:
                pid = str(item.get("productId", "")).strip()
                cid = str(item.get("colorId", "")).strip()

                if pid and cid:
                    unique_items[(pid, cid)] = item

            logging.info(
                "Catalog %s | Page %s/%s | Items: %s",
                catalog_id,
                page,
                total_pages,
                len(items),
            )

            if not items or page >= total_pages:
                break

            page += 1

        return list(unique_items.values())

    # -------------------- PRODUCT EXTRACTION --------------------

    def parse_item(self, product_url, response, rank):

        sel = Selector(text=response.text)

        product_name = sel.xpath(
            "normalize-space(string(//h1))"
        ).get(default="").strip()

        # Main product images: only Mango media URLs.
        images = []

        image_values = sel.xpath(
            "//img/@src | //img/@data-src | //img/@data-original"
        ).getall()

        for image in image_values:
            image = image.strip()

            if image.startswith("//"):
                image = "https:" + image

            if (
                image.startswith("https://media.mango.com/")
                and image not in images
            ):
                images.append(image)

        # Breadcrumb / category names.
        breadcrumbs = []

        for node in sel.xpath(
            '//a[contains(@href, "/in/en/c/")]'
        ):
            label = " ".join(
                text.strip()
                for text in node.xpath(".//text()").getall()
                if text.strip()
            )

            if label and label not in breadcrumbs:
                breadcrumbs.append(label)

        # Product description.
        description_parts = sel.xpath(
            '//*[contains(@class, "textContent")]//text()'
        ).getall()

        description = re.sub(
            r"\s+",
            " ",
            " ".join(
                text.strip()
                for text in description_parts
                if text.strip()
            ),
        ).strip()

        # Colour.
        colour = sel.xpath(
            '//*[contains(@class, "ColorsSelector")]'
            '//p[contains(@class, "title")]/span[last()]/text()'
        ).get(default="").strip()

        colour = (
            colour
            .replace("Colour ", "")
            .replace(" selected", "")
        )

        # Price.
        price_text = " ".join(
            text.strip()
            for text in sel.xpath(
                '//*[contains(@class, "SinglePrice")]//text()'
            ).getall()
            if text.strip()
        )

        price_match = re.search(
            r"(?:Rs\.?|₹)\s*[\d,]+(?:\.\d{1,2})?",
            price_text,
        )

        price = price_match.group(0) if price_match else ""

        # Clothing sizes.
        valid_sizes = {
            "XXS", "XS", "S", "M", "L", "XL", "XXL",
            "1XL", "2XL", "3XL", "4XL",
            "34", "36", "38", "40", "42", "44",
            "46", "48",
        }

        sizes = []

        for button in sel.xpath("//button[normalize-space()]"):

            size_value = button.xpath(
                "normalize-space(string(.))"
            ).get(default="").strip()

            button_text = " ".join(
                button.xpath(".//text()").getall()
            )

            unavailable = re.search(
                r"not available|unavailable|sold out",
                button_text,
                re.I,
            )

            if size_value in valid_sizes and not unavailable:
                if size_value not in sizes:
                    sizes.append(size_value)

        gender = self.get_gender(product_url)

        item = {
            "Product Name": product_name,
            "Size": ", ".join(sizes),
            "Product Description": description,
            "Category / Product Type": " > ".join(breadcrumbs),
            "Price": price,
            "Currency": "INR",
            "Main Product Image URL": images[0] if images else "",
            "PDP URL": product_url,
            "Rank": rank,
            "Colour": colour,
            "Gender": gender,
            "Material / Fabric": "",
            "Fit / Sizing Information": "",
            "Occasion / Style": "",
        }

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

    def process_product(self, key, requested_url, rank):

        if key in self.saved_variant_keys:
            return

        response = self.fetch(requested_url)

        if response is None:
            self.failed_count += 1
            return

        sel = Selector(text=response.text)

        canonical_url = sel.xpath(
            '//link[@rel="canonical"]/@href'
        ).get()

        final_url = self.clean_url(
            canonical_url or getattr(response, "url", "") or requested_url
        )

        sel = Selector(text=response.text)

        product_name = sel.xpath(
            "normalize-space(string(//h1))"
        ).get(default="").strip()

        # Avoid saving challenge pages or pages without a product title.
        if not product_name or len(product_name) > 250:
            logging.warning(
                "Product title not found; keeping link for a later retry: %s",
                requested_url,
            )

            self.failed_count += 1
            return

        final_key = self.variant_key_from_url(final_url) or key

        if (
            final_key in self.saved_variant_keys
            or final_url in self.saved_final_urls
        ):
            self.saved_variant_keys.add(final_key)
            return

        self.parse_item(final_url, response, rank)

        self.saved_variant_keys.add(final_key)
        self.saved_final_urls.add(final_url)
        self.saved_count += 1

        logging.info(
            "Saved %s | %s",
            self.saved_count,
            product_name,
        )

    def process_existing_links(self):

        try:
            with open(
                LINKS_FILE,
                newline="",
                encoding="utf-8-sig",
            ) as file:
                rows = list(csv.DictReader(file))

        except (OSError, csv.Error) as error:
            logging.warning("Cannot read links CSV: %s", error)
            return

        logging.info(
            "Resuming extraction from %s saved links",
            len(rows),
        )

        for index, row in enumerate(rows, start=1):

            pid = row.get("Product ID", "").strip()
            cid = row.get("Color ID", "").strip()
            url = row.get("PDP URL", "").strip()

            key = (pid, cid)

            if (
                not pid
                or not cid
                or not url
                or key in self.saved_variant_keys
            ):
                continue

            self.process_product(key, url, index)

            if index % 50 == 0:
                logging.info(
                    "Resume progress: %s/%s links",
                    index,
                    len(rows),
                )

    # -------------------- MAIN CRAWLER --------------------

    def start(self):

        self.ensure_csvs()
        self.load_existing_data()

        # Extract products left unfinished by previous runs.
        self.process_existing_links()

        category_queue = deque(
            urljoin(BASE_URL, path)
            for path in SECTION_URLS
        )

        while category_queue:

            current_url = self.clean_url(category_queue.popleft())

            if current_url in self.visited_categories:
                continue

            self.visited_categories.add(current_url)

            response = self.fetch(current_url)

            if response is None:
                continue

            html = response.text
            sel = Selector(text=html)

            logging.info(
                "Category %s: %s",
                len(self.visited_categories),
                current_url,
            )

            # Discover actual PDP URLs found in this page.
            observed_urls = {}

            for product_url in self.extract_pdp_urls(html):

                key = self.variant_key_from_url(product_url)

                if not key:
                    continue

                observed_urls.setdefault(key, product_url)

                template = self.template_from_url(product_url)
                gender = self.get_gender(product_url).lower()

                if template and gender:
                    self.product_templates.setdefault(
                        gender,
                        template,
                    )

            # Discover child categories.
            category_links = sel.xpath(
                '//a[contains(@href, "/in/en/c/")]/@href'
            ).getall()

            for href in category_links:

                child_url = self.clean_url(href)

                if child_url not in self.visited_categories:
                    category_queue.append(child_url)

            catalog_id = self.get_catalog_id(html)

            if not catalog_id:
                logging.info(
                    "No catalog ID; skipping API: %s",
                    current_url,
                )
                continue

            # Avoid duplicate API calls for shared catalog IDs.
            if catalog_id in self.processed_catalogs:
                continue

            self.processed_catalogs.add(catalog_id)

            catalog_items = self.fetch_catalog_items(catalog_id)

            gender = self.get_gender(current_url).lower()

            logging.info(
                "Catalog %s: %s variants",
                catalog_id,
                len(catalog_items),
            )

            for item in catalog_items:

                pid = str(item.get("productId", "")).strip()
                cid = str(item.get("colorId", "")).strip()

                if not pid or not cid:
                    continue

                key = (pid, cid)

                # Prefer an exact PDP URL discovered in HTML.
                product_url = observed_urls.get(key)

                # Reuse saved link if this variant was already discovered.
                if not product_url:
                    product_url = self.product_urls.get(key)

                # Fallback: use a URL template. Verify these URLs because
                # Mango may require the correct SEO slug for a PDP.
                if not product_url:
                    template = self.product_templates.get(gender, "")

                    if template:
                        product_url = (
                            f"{BASE_URL}{template}/{pid}/{cid}/00"
                        )

                if not product_url:
                    logging.debug(
                        "No PDP URL available for variant %s",
                        key,
                    )
                    continue

                self.save_link(pid, cid, product_url)

                if key not in self.saved_variant_keys:
                    self.process_product(
                        key,
                        product_url,
                        len(self.product_urls),
                    )

            logging.info(
                "Progress | Categories: %s | Catalogs: %s | "
                "Links: %s | Saved variants: %s | Failed: %s | "
                "Requests: %s",
                len(self.visited_categories),
                len(self.processed_catalogs),
                len(self.product_urls),
                len(self.saved_variant_keys),
                self.failed_count,
                self.request_count,
            )

        logging.info(
            "FINISHED | Categories: %s | Catalogs: %s | "
            "Links: %s | Saved this run: %s | Failed: %s | "
            "Requests: %s",
            len(self.visited_categories),
            len(self.processed_catalogs),
            len(self.product_urls),
            self.saved_count,
            self.failed_count,
            self.request_count,
        )


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    Parser().start()