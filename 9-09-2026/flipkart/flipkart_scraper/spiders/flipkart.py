
import json
import re

import scrapy


class FlipkartSpider(scrapy.Spider):
    name = "flipkart"
    allowed_domains = ["flipkart.com"]
    base_listing = (
        "https://www.flipkart.com/mens-footwear/mens-sports-shoes/pr"
        "?sid=osp,cil,1cu&otracker=categorytree&page={page}"
    )

    MAX_PRODUCTS = 20
    MAX_LISTING_PAGES = 6  
    custom_settings = {
        "PLAYWRIGHT_CONTEXTS": {
            "default": {
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
                "viewport": {"width": 1366, "height": 900},
                "locale": "en-US",
            }
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.collected_urls = set()
        self.seen_list_products = set()
        self.listing_page = 0
        self.inflight = 0  
        resume_from = getattr(self, "resume_from", None)
        if resume_from:
            import csv as _csv

            with open(resume_from, newline="", encoding="utf8") as fh:
                for row in _csv.DictReader(fh):
                    u = (row.get("product_url") or "").strip()
                    if u:
                        self.collected_urls.add(u)
            self.logger.info(
                "resumed: %d products already collected, %d to go",
                len(self.collected_urls), self.MAX_PRODUCTS - len(self.collected_urls),
            )

    # A valid record needs ALL required fields populated (assignment:
    # "output fields contain actual values, not empty strings/None").
    FIELDS = (
        "name", "price", "discount", "stars",
        "people_bought", "mrp", "offer_price", "product_url",
    )

    async def start(self):
        # Scrapy >= 2.13 start API
        self.listing_page = 1
        yield self._listing_request(1)

    def _listing_request(self, page):
        return scrapy.Request(
            self.base_listing.format(page=page),
            meta={
                "playwright": True,
                # "load" never fires on Flipkart (long-polling/analytics keep the
                # page "loading") — wait for DOM readiness, then a fixed delay.
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                "playwright_page_methods": [
                    PageMethod("wait_for_timeout", 6000),
                ],
            },
            callback=self.parse_listing,
            cb_kwargs={"page": page},
            dont_filter=True,
        )

    # ---------- listing ----------

    def parse_listing(self, response, page):
        product_paths = response.xpath("//a/@href").getall()
        products = []
        for href in product_paths:
            if "/p/" not in href:
                continue
            path = href.split("?")[0]
            if path in self.seen_list_products:
                continue
            self.seen_list_products.add(path)
            products.append(path)

        self.logger.info(
            "listing page %s: %d new product paths (total seen %d)",
            page, len(products), len(self.seen_list_products),
        )

        for path in products:
            if self._quota_reached():
                return
            url = "https://www.flipkart.com" + path
            if url.split("?")[0] in self.collected_urls:
                continue  # already scraped (e.g. resuming a partial run)
            self.inflight += 1
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 6000),
                    ],
                },
                callback=self.parse_product,
                dont_filter=True,
            )

        # paginate only while quota unmet
        if (
            not self._quota_reached()
            and products
            and page < self.MAX_LISTING_PAGES
        ):
            yield self._listing_request(page + 1)

    # ---------- product ----------

    def parse_product(self, response):
        if self.inflight > 0:
            self.inflight -= 1
        if self._quota_reached():
            return
        if response.url.split("?")[0] in self.collected_urls:
            return  # duplicate (resumed run) — don't double-count

        item = {
            "name": "",
            "price": "",
            "discount": "",
            "stars": "",
            "people_bought": "",
            "mrp": "",
            "offer_price": "",
            "product_url": response.url.split("?")[0],
        }

        # ---- JSON-LD Product (primary; stable schema) ----
        for blob in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                data = json.loads(blob)
            except (json.JSONDecodeError, TypeError):
                continue
            candidates = data if isinstance(data, list) else [data]
            for obj in candidates:
                if not isinstance(obj, dict) or obj.get("@type") != "Product":
                    continue
                item["name"] = (obj.get("name") or "").strip()
                offers = obj.get("offers") or {}
                price = offers.get("price")
                if price is not None:
                    item["price"] = f"₹{price}"
                agg = obj.get("aggregateRating") or {}
                if agg.get("ratingValue") is not None:
                    item["stars"] = str(agg.get("ratingValue"))
                if agg.get("ratingCount") is not None:
                    item["people_bought"] = f"{agg.get('ratingCount'):,}"
                break

        # ---- visible DOM fallbacks / supplements ----
        if not item["name"]:
            item["name"] = (response.xpath("//h1/text()").get() or "").strip()

        if not item["price"]:
            # final price: big div right after the h1, first ₹NNN text
            item["price"] = (
                response.xpath(
                    '//div[contains(@class,"Nx9bqj")]/text()'
                ).get()
                or ""
            )

        # MRP: strikethrough div in the price cluster
        mrp = response.xpath(
            '//div[contains(@style,"line-through")]/text()'
        ).get()
        if mrp:
            item["mrp"] = mrp.strip()

        # discount badge: green div with NN% next to the price cluster
        pct = response.xpath(
            '//div[contains(@style,"#008042") and contains(text(),"%")]/text()'
        ).get()
        if pct:
            item["discount"] = pct.strip()
        # compute discount from MRP/price if the badge is missing
        if not item["discount"] and item["mrp"] and item["price"]:
            m = _num(item["mrp"])
            p = _num(item["price"])
            if m and p and m > p:
                item["discount"] = f"{round((m - p) / m * 100)}% off"

        # offer price ("Buy at ₹NNN" — the Flipkart Pay-Later / hot-deal price)
        offer = response.xpath(
            '//div[contains(text(),"Buy at")]/text()'
        ).get()
        if offer:
            item["offer_price"] = offer.strip()

        # stars fallback: bold css-146c3p1 div holding a lone decimal
        if not item["stars"]:
            for txt in response.xpath(
                '//div[contains(@class,"css-146c3p1")]/text()'
            ).getall():
                if re.fullmatch(r"\d\.\d", txt.strip()):
                    item["stars"] = txt.strip()
                    break

        # people bought fallback: css-146c3p1 div like '| 37,062'
        if not item["people_bought"]:
            for txt in response.xpath(
                '//div[contains(@class,"css-146c3p1")]/text()'
            ).getall():
                if re.fullmatch(r"\|?\s*[\d,]{3,}", txt.strip()):
                    item["people_bought"] = txt.strip().lstrip("| ").strip()
                    break

        # a valid record requires every field populated; products missing e.g.
        # ratings are skipped and do not count toward the 20
        valid = all(item[f] for f in self.FIELDS)
        if not valid:
            missing = [f for f in self.FIELDS if not item[f]]
            self.logger.info(
                "invalid product (empty %s): %s", missing, response.url
            )
            return

        self.collected_urls.add(item["product_url"])
        yield item

        if self._quota_reached():
            self.logger.info("Quota of %d reached — closing.", self.MAX_PRODUCTS)
            self.crawler.engine.close_spider(self, "quota_reached")

    def _quota_reached(self):
        return len(self.collected_urls) >= self.MAX_PRODUCTS


def _num(s):
    """'₹1,699' -> 1699 ; returns None if not numeric."""
    m = re.search(r"[\d,]+", s or "")
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


# import at bottom to keep the docstring/flow readable
from scrapy_playwright.page import PageMethod  # noqa: E402
