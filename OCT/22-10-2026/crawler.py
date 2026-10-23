import logging
import re
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from parsel import Selector
from settings import (
    BASE_URL, START_URLS, PAGE_PARAM, MAX_PAGES, HEADERS, get_response,
    CATEGORY_FILE, SUBCATEGORY_FILE, PRODUCT_URL_FILE, DONE_FILE, FAILED_FILE,
)
from items import (
    CsvStore, CATEGORY_HEADERS, SUBCATEGORY_HEADERS, PRODUCT_URL_HEADERS,
    DONE_HEADERS, FAILED_HEADERS,
)

# nav entries that are not real categories (gender tabs etc.)
SKIP_NAMES = {"women", "men", "kids", "home", "sale", "smart prices", "brands", "new in"}

# product urls look like /anna-field-cocktail-dress-black-an621c1og-q11.html
PRODUCT_URL_RE = re.compile(r"^/[a-z0-9\-%]+-[a-z0-9]{9}-[a-z0-9]{3}\.html$", re.I)
PRICE_RE = re.compile(r"£\s?[\d,]+(?:\.\d{2})?")
ICON_RE = re.compile(r"^(heart|bag|add|close|arrow|star)[a-z_]*$", re.I)  # icon font text
BADGE_RE = re.compile(r"^(-\d+%|up to -\d+%|new|top rated|bestseller|exclusive|designer|maternity)$", re.I)

# links we never want as categories
SKIP_HREF = ("/outfits/", "/creator/", "/help", "/brands", "/gift", "/myaccount",
             "/cart", "/wishlist", "/sale", "/new-in", "?", "#", "/_", "__size")

# XPATHs (verify against live html)
NAV_CATEGORY_XPATH = '//header//nav//a | //nav[contains(@aria-label,"ategor")]//a'
SIDEBAR_XPATH = ('//aside//a | //nav[contains(@aria-label,"ategor")]//a '
                 '| //div[@data-testid="sidebar"]//a')
ARTICLE_XPATH = "//article"
TOTAL_PAGES_XPATH = '//*[contains(text(),"Page ") and contains(text()," of ")]/text()'


def clean_url(href):
    url = urljoin(BASE_URL, href)
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def page_url(url, page):
    if page <= 1:
        return url
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query[PAGE_PARAM] = [str(page)]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def link_name(a):
    return " ".join(t.strip() for t in a.xpath(".//text()").extract() if t.strip())


class Crawler:
    """Crawling category -> subcategory -> product urls (csv files, resumable)"""

    def __init__(self):
        self.categories = CsvStore(CATEGORY_FILE, CATEGORY_HEADERS, "url")
        self.subcategories = CsvStore(SUBCATEGORY_FILE, SUBCATEGORY_HEADERS, "url")
        self.products = CsvStore(PRODUCT_URL_FILE, PRODUCT_URL_HEADERS, "product_url")
        self.done = CsvStore(DONE_FILE, DONE_HEADERS, "url")
        self.failed = CsvStore(FAILED_FILE, FAILED_HEADERS, "url")

    def start(self):
        self.crawl_categories()
        self.crawl_subcategories()
        self.crawl_products()

    # ---------------- STEP 1: categories ----------------
    def crawl_categories(self):
        """Women / Men / Kids home -> main nav categories (Clothing, Shoes, ...)"""

        for category, url in START_URLS.items():
            if self.done.has(url):
                continue
            response = get_response(url)
            if not response:
                self.failed.add({"url": url, "stage": "category_home"})
                continue
            sel = Selector(text=response.text)
            for a in sel.xpath(NAV_CATEGORY_XPATH):
                href = a.xpath("./@href").extract_first()
                name = link_name(a)
                if not href or not name or any(s in href for s in SKIP_HREF):
                    continue
                if name.lower() in SKIP_NAMES:
                    continue
                item = {"url": clean_url(href), "category": category, "category_name": name}
                if self.categories.add(item):
                    logging.info(item)
            self.done.add({"url": url, "stage": "category_home"})

    # ---------------- STEP 2: sub categories ----------------
    def crawl_subcategories(self):
        """Category page sidebar -> sub categories (Dresses, Jeans, ...)"""

        for cat in list(self.categories.rows):
            if self.done.has(cat["url"]):
                continue
            response = get_response(cat["url"])
            if not response:
                self.failed.add({"url": cat["url"], "stage": "subcategory"})
                continue
            sel = Selector(text=response.text)
            found = 0
            for a in sel.xpath(SIDEBAR_XPATH):
                href = a.xpath("./@href").extract_first()
                name = link_name(a)
                if not href or not name or any(s in href for s in SKIP_HREF):
                    continue
                if name.lower() in SKIP_NAMES:
                    continue
                url = clean_url(href)
                if url.rstrip("/") == cat["url"].rstrip("/"):
                    continue
                item = {"url": url, "category": cat["category"],
                        "category_name": cat["category_name"], "subcategory": name}
                if self.subcategories.add(item):
                    logging.info(item)
                    found += 1
            if not found:
                # page has no sub categories -> treat the page itself as a listing
                self.subcategories.add({
                    "url": cat["url"], "category": cat["category"],
                    "category_name": cat["category_name"],
                    "subcategory": cat["category_name"]})
            self.done.add({"url": cat["url"], "stage": "category"})

    # ---------------- STEP 3: products ----------------
    def crawl_products(self):
        """Sub category listing -> product urls with pagination (?p=N)"""

        for sub in list(self.subcategories.rows):
            if self.done.has(sub["url"]):
                continue
            meta = {"category": sub["category"], "category_name": sub["category_name"],
                    "subcategory": sub["subcategory"]}
            page = 1
            total_pages = MAX_PAGES
            completed = True
            while page <= min(total_pages, MAX_PAGES):
                url = page_url(sub["url"], page)
                if self.done.has(url):  # page already crawled in an earlier run
                    page += 1
                    continue
                HEADERS["referer"] = sub["url"]
                response = get_response(url)
                if not response:
                    # keep sub category NOT done so the next run resumes from this page
                    self.failed.add({"url": url, "stage": "listing"})
                    logging.error(f"giving up for now on {url}")
                    completed = False
                    break
                if page == 1:
                    total_pages = self.get_total_pages(response)
                has_products = self.parse_item(response, meta)
                self.done.add({"url": url, "stage": "page"})
                if not has_products:
                    logging.info("Pagination completed")
                    break
                page += 1
            if completed:
                logging.info(f"done {meta} -> {len(self.products.rows)} product urls total")
                self.done.add({"url": sub["url"], "stage": "listing"})

    @staticmethod
    def get_total_pages(response):
        sel = Selector(text=response.text)
        text = " ".join(sel.xpath(TOTAL_PAGES_XPATH).extract())
        match = re.search(r"of\s+(\d+)", text)
        return int(match.group(1)) if match else MAX_PAGES

    def parse_item(self, response, meta):
        """Listing page -> product url, name, brand, price, badge"""

        sel = Selector(text=response.text)
        count = 0
        seen = set()
        for tile in sel.xpath(ARTICLE_XPATH):
            href = next((h for h in tile.xpath(".//a/@href").extract()
                         if PRODUCT_URL_RE.match(urlparse(h).path)), None)
            if not href:
                continue
            product_url = clean_url(href)
            if product_url in seen:
                continue
            seen.add(product_url)

            texts = [t.strip() for t in tile.xpath(".//text()[not(ancestor::a[.//img])]").extract() if t.strip()]
            prices = PRICE_RE.findall(" ".join(texts))
            badge = next((t for t in texts if BADGE_RE.match(t)), "")
            words = [t for t in texts if not PRICE_RE.search(t) and not BADGE_RE.match(t)
                     and not ICON_RE.match(t)]
            # tile text order: brand, product name, ...
            brand = words[0] if words else ""
            name = words[1] if len(words) > 1 else ""

            item = {
                "product_url": product_url,
                "category": meta.get("category"),
                "category_name": meta.get("category_name"),
                "subcategory": meta.get("subcategory"),
                "name": name,
                "brand": brand,
                "price": prices[0] if prices else "",
                "regular_price": prices[1] if len(prices) > 1 else "",
                "badge": badge,
            }
            if self.products.add(item):
                logging.info(item)
            count += 1

        # fallback: no <article> tiles -> take every product-looking link
        if not count:
            for href in sel.xpath("//a/@href").extract():
                if PRODUCT_URL_RE.match(urlparse(href).path):
                    product_url = clean_url(href)
                    if product_url in seen:
                        continue
                    seen.add(product_url)
                    self.products.add({
                        "product_url": product_url, "category": meta.get("category"),
                        "category_name": meta.get("category_name"),
                        "subcategory": meta.get("subcategory")})
                    count += 1
        return count > 0

    def close(self):
        pass


if __name__ == "__main__":
    crawler = Crawler()
    crawler.start()
    crawler.close()