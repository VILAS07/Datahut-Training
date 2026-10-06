"""Camoufox crawler for MSC Direct (https://www.mscdirect.com).

Only Camoufox is used: no requests/curl, no Selenium. Each page is rendered by
the real browser and then handed to ``parser.py`` for extraction.

Flow:
    1. open the homepage and confirm the rendered DOM is the real MSC page,
    2. walk the configured category/search listings and collect product cards,
    3. open every unique product page and extract the full record,
    4. export the result to CSV.

If MSC answers with an explicit security/block page the crawl stops gracefully
without trying to bypass anything, and whatever was collected so far is kept.
"""

import logging
import random
import time
from typing import Dict, List, Optional

from camoufox.sync_api import Camoufox

import settings
from export import save_to_csv
from items import FIELDS, merge_records
from parser import parse_listing, parse_product

LOGGER = logging.getLogger("msc_crawler")


class MscCrawler:
    """Sequential Camoufox crawler for MSC Direct product data."""

    def __init__(self) -> None:
        self.products: Dict[str, Dict[str, Optional[str]]] = {}
        self.msc_index: Dict[str, str] = {}
        self.pending: List[str] = []
        self.home_loaded = False
        self.listing_pages = 0
        self.detail_pages = 0
        self.duplicates = 0
        self.blocked = False

    def run(self) -> List[Dict[str, Optional[str]]]:
        """Launch Camoufox, crawl the site and export the CSV."""
        LOGGER.info("Starting Camoufox (headless=%s)", settings.HEADLESS)
        with Camoufox(
            headless=settings.HEADLESS,
            block_images=settings.BLOCK_IMAGES,
            humanize=settings.HUMANIZE,
        ) as browser:
            page = browser.new_page()
            self.open_homepage(page)
            if not self.blocked:
                self.crawl_listings(page)
                self.crawl_details(page)

        save_to_csv(list(self.products.values()), settings.OUTPUT_CSV)
        self.report()
        return list(self.products.values())

    def open_homepage(self, page) -> None:
        """Open MSC Direct and verify that a real MSC page was rendered."""
        LOGGER.info("Opening %s", settings.START_URL)
        try:
            page.goto(
                settings.START_URL,
                wait_until="domcontentloaded",
                timeout=settings.PAGE_LOAD_TIMEOUT_MS,
            )
            page.wait_for_timeout(settings.HOME_WAIT_MS)
        except Exception as error:
            LOGGER.warning("Homepage did not finish loading: %s", error)

        html = page.content()
        LOGGER.info("Homepage title: %s", page.title())
        LOGGER.info("Homepage rendered DOM: %d characters", len(html))

        if self.is_blocked(page, html):
            self.stop_for_block(page)
            return
        if "msc" not in (page.title() or "").lower():
            LOGGER.warning(
                "Rendered page does not look like an MSC page (title: %s)", page.title()
            )
        self.home_loaded = True

        cards = parse_listing(html, page.url)
        LOGGER.info("Homepage product cards found in the rendered DOM: %d", len(cards))
        self.add_products(cards)

    def crawl_listings(self, page) -> None:
        """Walk the category/search listings and collect the product cards."""
        for url in settings.LISTING_URLS:
            if self.enough_products() or len(self.pending) >= settings.PRODUCT_LIMIT:
                break
            html = self.load(page, url, wait_ms=settings.LISTING_WAIT_MS)
            if html is None:
                if self.blocked:
                    return
                LOGGER.warning("Listing page gave no usable HTML: %s", url)
                continue
            self.listing_pages += 1
            cards = parse_listing(html, page.url)
            LOGGER.info(
                "Listing %s -> %d product cards (title: %s)", url, len(cards), page.title()
            )
            self.add_products(cards)
            if not cards:
                LOGGER.warning("No product cards recognised on %s", url)
            self.pause()

    def crawl_details(self, page) -> None:
        """Open every collected product URL and extract the full record.

        ``PRODUCT_LIMIT`` is the *collection* target, so reaching it does not
        skip this phase - the detail pages are what fill description,
        specifications, availability and the manufacturer part number.
        """
        queue = list(dict.fromkeys(self.pending))
        total = len(queue)
        for index, url in enumerate(queue, start=1):
            if self.blocked:
                break
            html = self.load(
                page,
                url,
                wait_ms=settings.DETAIL_SETTLE_MS,
                selector="h1",
                extra_selector="table.specs_table",
            )
            if html is None:
                if self.blocked:
                    return
                LOGGER.warning("Product page gave no usable HTML: %s", url)
                continue
            self.detail_pages += 1
            detail = parse_product(html, page.url)
            detail["product_url"] = detail.get("product_url") or url
            status = self.add_product(detail, detailed=True)
            LOGGER.info(
                "[%d/%d] %s -> %s (%s)",
                index,
                total,
                detail.get("msc_number") or url,
                status,
                detail.get("product_name"),
            )
            self.pause()

    def load(
        self,
        page,
        url,
        wait_ms: int = 0,
        selector: Optional[str] = None,
        extra_selector: Optional[str] = None,
    ):
        """Navigate to ``url`` (with retries) and return the rendered HTML.

        ``selector`` is required (for example the product ``h1``), while
        ``extra_selector`` is waited for best effort (for example the specs
        table, which not every product renders).

        Returns ``None`` when the page could not be rendered, or when MSC
        answered with a security/block page (the crawl then stops).
        """
        for attempt in range(1, settings.MAX_PAGE_RETRIES + 2):
            try:
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=settings.PAGE_LOAD_TIMEOUT_MS,
                )
                if selector:
                    try:
                        page.wait_for_selector(selector, timeout=settings.SELECTOR_TIMEOUT_MS)
                    except Exception:
                        LOGGER.warning("Selector %s never appeared on %s", selector, url)
                if extra_selector:
                    try:
                        page.wait_for_selector(
                            extra_selector, timeout=settings.EXTRA_SELECTOR_TIMEOUT_MS
                        )
                    except Exception:
                        pass
                if wait_ms:
                    page.wait_for_timeout(wait_ms)
                html = page.content()
            except Exception as error:
                LOGGER.warning("Attempt %d failed for %s: %s", attempt, url, error)
                page.wait_for_timeout(settings.RETRY_WAIT_MS)
                continue

            if self.is_blocked(page, html):
                self.stop_for_block(page)
                return None
            return html
        return None

    def add_products(self, records: List[Dict[str, Optional[str]]]) -> None:
        """Store every card of a listing page, skipping known products."""
        for record in records:
            self.add_product(record)

    def add_product(self, record: Dict[str, Optional[str]], detailed: bool = False) -> str:
        """Add a product, enrich an already known one, or skip a duplicate.

        Returns ``"new"``, ``"enriched"``, ``"duplicate"`` or ``"invalid"``.
        """
        product_url = record.get("product_url")
        msc_number = record.get("msc_number")
        key = self._existing_key(product_url, msc_number)

        if key is None:
            key = product_url or msc_number
            if not key:
                return "invalid"
            self.products[key] = dict(record)
            if msc_number:
                self.msc_index[msc_number] = key
            if not detailed and product_url:
                self.pending.append(product_url)
            return "new"

        if detailed:
            self.products[key] = merge_records(self.products[key], record)
            return "enriched"

        self.duplicates += 1
        return "duplicate"

    def _existing_key(self, product_url, msc_number) -> Optional[str]:
        """Key of an already stored product (matched by URL or by MSC number)."""
        if product_url and product_url in self.products:
            return product_url
        if msc_number and msc_number in self.msc_index:
            return self.msc_index[msc_number]
        return None

    def is_blocked(self, page, html: str) -> bool:
        """Detect an explicit MSC security / block page."""
        title = (page.title() or "").lower()
        head = (html or "")[:4000].lower()
        return any(
            marker in title or marker in head for marker in settings.BLOCK_PAGE_MARKERS
        )

    def stop_for_block(self, page) -> None:
        """Stop the crawl without trying to defeat the security page."""
        self.blocked = True
        LOGGER.error(
            "MSC served a security/block page at %s - stopping gracefully and "
            "keeping the %d products collected so far.",
            page.url,
            len(self.products),
        )
        print(
            "\nMSC returned a security/block page. The crawler stopped without "
            f"trying to bypass it; {len(self.products)} collected products are kept."
        )

    def enough_products(self) -> bool:
        """True once the requested number of unique products is collected."""
        return len(self.products) >= settings.PRODUCT_LIMIT

    def pause(self) -> None:
        """Short human-sized delay between page loads."""
        low, high = settings.DELAY_BETWEEN_PAGES_MS
        time.sleep(random.randint(low, high) / 1000)

    def report(self) -> None:
        """Print the crawl summary and the per-field coverage."""
        total = len(self.products)
        coverage = {
            field: sum(1 for product in self.products.values() if product.get(field))
            for field in FIELDS
        }
        print("")
        print("=" * 72)
        print("MSC Direct crawl summary")
        print("=" * 72)
        print(f"Homepage loaded           : {self.home_loaded}")
        print(f"Unique products collected : {total}")
        print(f"Listing/category pages    : {self.listing_pages}")
        print(f"Product detail pages      : {self.detail_pages}")
        print(f"Duplicates skipped        : {self.duplicates}")
        print(f"Stopped by security page  : {self.blocked}")
        print(f"CSV output               : {settings.OUTPUT_CSV}")
        print("-" * 72)
        print("Field coverage (non-empty values):")
        for field in FIELDS:
            print(f"  {field:<22} {coverage[field]:>4}/{total}")
        print("=" * 72)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    MscCrawler().run()
