import argparse
import base64
import csv
import hashlib
import html as html_lib
import json
import logging
import os
import re
import sys
import time
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from parsel import Selector

from settings import (
    HEADERS, PROXIES, DELAY, RETRIES, TIMEOUT, URLS_FILE, BASE_URL, WEBSITE,
    EXTRACTION_DATE, FETCH_AMAZON_PRICE, USE_MONGO, COOLDOWN, MAX_COOLDOWNS,
    FILE_NAME_PRODUCTS, FILE_NAME_REVIEWS, FILE_HEADERS, REVIEW_HEADERS,
)

CURRENCIES = {"₹": "INR", "$": "USD", "€": "EUR", "£": "GBP"}
PRICE_RE = re.compile(r"(₹|\$|€|£|Rs\.?|INR|USD|EUR|GBP)\s*([\d][\d.,]*)")

# page text can be French (.fr) or English (.com); both are handled
YEAR_RE = re.compile(r"(?:lancé en|lancé pendant|launched in|launched during)\s+(\d{4}(?:'?s)?)", re.I)
FAMILY_RE = re.compile(r"(?:est un parfum|is an?)\s+(.+?)\s+(?:pour (?:homme|femme)|fragrance for)", re.I)
PERFUMER_RE = re.compile(
    r"(?:nez derrière ce parfum (?:est|sont)|perfumers? behind this fragrance (?:is|are))\s+(.+?)\.(?:\s|$)",
    re.I,
)


def clean(text):
    """collapse whitespace"""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip() if text else ""


def html_to_text(raw):
    """review html -> plain text, keeping line breaks and emoji alt text"""
    if not raw:
        return ""
    raw = re.sub(r"<img[^>]*alt=\"([^\"]*)\"[^>]*>", r"\1", raw)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"</p>|</div>|</li>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = html_lib.unescape(raw).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", x).strip() for x in raw.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


class RateLimited(Exception):
    """site keeps answering 429 after all cooldowns"""


class Parser:
    """parser"""

    def __init__(self):
        try:
            # chrome-like TLS fingerprint; plain requests gets 403 from the site
            from curl_cffi import requests as cffi_requests
            self.session = cffi_requests.Session(impersonate="chrome")
            logging.info("using curl_cffi (chrome impersonation)")
        except ImportError:
            logging.warning("curl_cffi not installed -> pip install curl_cffi (plain requests is usually blocked)")
            self.session = requests.Session()
            self.session.headers.update(HEADERS)
        if PROXIES:
            self.session.proxies.update(PROXIES)
        self.mongo = None
        self.delay = DELAY

    # ------------------------------------------------------------ mongo
    def connect(self):
        from items import connect_db
        self.mongo = connect_db()

    # ------------------------------------------------------------ run
    def start(self, limit=None):
        """read urls.csv -> fetch page -> parse -> save"""
        if USE_MONGO:
            from items import ProductItem
            self.connect()
            done = set(ProductItem.objects.scalar("pdp_url"))
        else:
            done = self.load_done()
        metas = self.read_urls()
        logging.info(f"{len(metas)} urls in {URLS_FILE}, {len(done)} already parsed")
        count = 0
        for meta in metas:
            url = meta["pdp_url"]
            if url in done:
                continue
            if limit and count >= limit:
                break
            try:
                response_text = self.fetch(url)
            except RateLimited:
                logging.error("Site is still blocking us (429) after all cooldowns. "
                              "Progress is saved. Wait 1-2 hours (or change IP / set PROXY) and run again.")
                sys.exit(2)
            if not response_text:
                self.failed(url)
                continue
            try:
                item = self.parse_item(url, response_text)
                if FETCH_AMAZON_PRICE:
                    item.update(self.get_amazon(response_text))
            except Exception as e:  # keep the run alive, log the url
                logging.exception(f"parse failed {url}: {e}")
                self.failed(url)
                continue
            self.save(item)
            count += 1
            time.sleep(self.delay)

    @staticmethod
    def read_urls():
        with open(URLS_FILE, newline="", encoding="utf-8") as f:
            return [r for r in csv.DictReader(f) if r.get("pdp_url")]

    @staticmethod
    def failed(url):
        logging.warning(f"failed (will retry on next run): {url}")
        if USE_MONGO:
            from items import ProductFailedItem
            ProductFailedItem(pdp_url=url).save()

    @staticmethod
    def load_done():
        """resume: urls already written to the products csv"""
        if not os.path.exists(FILE_NAME_PRODUCTS):
            return set()
        with open(FILE_NAME_PRODUCTS, newline="", encoding="utf-8-sig") as f:
            return {r["pdp_url"] for r in csv.DictReader(f)}

    @staticmethod
    def save(item):
        if USE_MONGO:
            from items import ProductItem
            ProductItem.objects(pdp_url=item["pdp_url"]).delete()
            ProductItem(**item).save()
        else:
            Parser.save_csv(item)
        # terminal output
        logging.info(
            f"{item['product_id']} | {item['product_name']} | {item['brand']} | "
            f"{item['gender']} | {item['launch_year']} | rating {item['rating_value']} "
            f"({item['rating_count']} votes) | reviews {item['reviews_scraped']}/{item['review_count']} | "
            f"amazon {item['amazon_currency']} {item['amazon_price']}"
        )

    @staticmethod
    def save_csv(item):
        """append one product row and its review rows (reviews first, so a
        product only counts as done once all its reviews are written)"""
        def cell(v):
            return "" if v is None else v

        def join(values):
            return " | ".join(str(v) for v in values) if values else ""

        row = dict(item)
        row["main_accords"] = join([f"{a['accord']}:{a['strength']:g}" for a in item["main_accords"]])
        row["top_notes"] = join(item["top_notes"])
        row["middle_notes"] = join(item["middle_notes"])
        row["base_notes"] = join(item["base_notes"])
        row["also_like"] = join([f"{a['name']} ({a['brand']}) {a['url']}" for a in item["also_like"]])

        for path, headers, rows in (
            (FILE_NAME_REVIEWS, REVIEW_HEADERS,
             [{**{k: item[k] for k in ("website", "extraction_date", "product_id", "pdp_url", "product_name")}, **r}
              for r in item["reviews"]]),
            (FILE_NAME_PRODUCTS, FILE_HEADERS, [row]),
        ):
            new = not os.path.exists(path) or os.path.getsize(path) == 0
            with open(path, "a", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, quoting=csv.QUOTE_ALL)
                if new:
                    w.writerow(headers)
                for r in rows:
                    w.writerow([cell(r.get(h)) for h in headers])

    # ------------------------------------------------------------ http
    def fetch(self, url, referer=None, raise_limit=True):
        wait = 15
        errors = 0
        limited = 0
        while errors < RETRIES:
            try:
                headers = {"Referer": referer} if referer else None
                r = self.session.get(url, headers=headers, timeout=TIMEOUT)
                if r.status_code == 200:
                    return r.text
                if r.status_code == 404:
                    logging.warning(f"404 {url}")
                    return None
                if r.status_code == 429:
                    # rate limited: cool down, then retry the SAME url, and slow down
                    limited += 1
                    if limited > MAX_COOLDOWNS:
                        if raise_limit:
                            raise RateLimited(url)
                        return None
                    self.delay = min(self.delay * 1.5, 30)
                    pause = min(COOLDOWN * limited, 1800)   # 3, 6, 9 ... max 30 minutes
                    logging.warning(f"429 rate limit, cooling down {pause}s "
                                    f"(#{limited}/{MAX_COOLDOWNS}), delay now {self.delay:.1f}s")
                    time.sleep(pause)
                    continue
                logging.warning(f"status {r.status_code} {url}, retry in {wait}s")
            except RateLimited:
                raise
            except Exception as e:  # network / curl errors
                logging.warning(f"{type(e).__name__} {url}, retry in {wait}s")
            errors += 1
            time.sleep(wait)
            wait *= 2
        return None

    # ------------------------------------------------------------ parse
    def parse_item(self, url, page_html):
        """item part"""

        sel = Selector(text=page_html)

        # XPATH
        H1_XPATH = '//h1[@itemprop="name"]'
        GENDER_XPATH = '//h1[@itemprop="name"]/span/text()'
        BRAND_XPATH = '//p[@itemprop="brand"]//span[@itemprop="name"]/text()'
        BRAND_URL_XPATH = '//p[@itemprop="brand"]/a/@href'
        BRAND_LOGO_XPATH = '//p[@itemprop="brand"]//img[@itemprop="logo"]/@src'
        IMAGE_XPATH = '(//img[@itemprop="image" and contains(@src,"perfume-thumbs")]/@src)[1]'
        DESCRIPTION_XPATH = '//div[@id="perfume-description-content"]'
        PERFUMER_XPATH = '//a[contains(@href,"/perfumers/") and contains(@href,".html")]//span/text()'
        ACCORD_LINK_XPATH = '//a[contains(@href,"/accords-search/?")]/@href'
        ACCORD_BAR_XPATH = '//div[span[contains(@class,"truncate")] and contains(@style,"width")]'
        NOTE_XPATH = './/a[contains(@class,"pyramid-note-link")]'
        RATING_VALUE_XPATH = '//span[@itemprop="ratingValue"]/text()'
        RATING_COUNT_XPATH = '//span[@itemprop="ratingCount"]/@content'
        REVIEW_COUNT_XPATH = '(//a[contains(@href,"#all-reviews")]//span/span/text())[1]'
        CAROUSEL_XPATH = '//div[contains(@class,"perfume-carousel-scroll")]'
        CARD_XPATH = './/div[contains(concat(" ",normalize-space(@class)," ")," tw-carousel-perfume-card ")]'

        # EXTRACT
        product_id = re.search(r"-(\d+)\.html", url)
        product_id = product_id.group(1) if product_id else sel.xpath('//*[@perfume_id]/@perfume_id').get()
        h1 = sel.xpath(H1_XPATH)
        h1_name = clean(" ".join(h1.xpath("./text()").getall()))
        gender = clean(sel.xpath(GENDER_XPATH).get())
        brand = clean(sel.xpath(BRAND_XPATH).get())
        brand_url = sel.xpath(BRAND_URL_XPATH).get()
        brand_logo = sel.xpath(BRAND_LOGO_XPATH).get()
        main_image = sel.xpath(IMAGE_XPATH).get()
        description = clean(" ".join(sel.xpath(DESCRIPTION_XPATH + "//text()").getall()))
        perfumer_list = [clean(x) for x in sel.xpath(PERFUMER_XPATH).getall() if clean(x)]
        rating_value = clean(sel.xpath(RATING_VALUE_XPATH).get())
        rating_count = sel.xpath(RATING_COUNT_XPATH).get() or ""
        review_count = clean(sel.xpath(REVIEW_COUNT_XPATH).get())

        # CLEAN
        # h1 is "<name> <brand>"; remove the brand to get the product name
        product_name = h1_name
        if brand and h1_name.endswith(brand):
            product_name = h1_name[: -len(brand)].strip()

        year = YEAR_RE.search(description)
        launch_year = year.group(1) if year else ""
        family = FAMILY_RE.search(description)
        fragrance_family = clean(family.group(1)) if family else ""
        if not perfumer_list:
            perfumer = PERFUMER_RE.search(description)
            perfumer_list = [clean(x) for x in re.split(r",| et | and ", perfumer.group(1))] if perfumer else []

        accords = self.parse_accords(sel.xpath(ACCORD_LINK_XPATH).getall(), sel.xpath(ACCORD_BAR_XPATH))

        levels = {}
        for level in ("top", "middle", "base"):
            names = [clean(" ".join(a.xpath(".//span[contains(@class,'pyramid-note-label')]//text()").getall()))
                     for a in sel.xpath(f'//pyramid-level-new[@notes="{level}"]').xpath(NOTE_XPATH)]
            levels[level] = [x for x in names if x]
        if not any(levels.values()):  # flat note list, no pyramid levels
            names = [clean(" ".join(a.xpath(".//span[contains(@class,'pyramid-note-label')]//text()").getall()))
                     for a in sel.xpath(NOTE_XPATH)]
            levels["middle"] = list(dict.fromkeys(x for x in names if x))

        also_like = []
        cards = []
        for carousel in sel.xpath(CAROUSEL_XPATH):
            found = carousel.xpath(CARD_XPATH)
            if found:
                cards = found  # the last carousel with perfume cards = "also like"
        for card in cards:
            texts = [clean(x) for x in card.xpath(".//a[1]//p//text()").getall() if clean(x)]
            href = card.xpath(".//a[1]/@href").get()
            if href and len(texts) >= 2:
                also_like.append({"name": texts[1], "brand": texts[0], "url": urljoin(BASE_URL, href)})

        reviews = self.parse_reviews(sel, product_id, url, product_name)
        if not review_count:  # page hides the count link when there are very few reviews
            review_count = str(len(reviews))

        # ITEM YEILD
        item = {}
        item["website"] = WEBSITE
        item["extraction_date"] = EXTRACTION_DATE
        item["product_id"] = product_id
        item["pdp_url"] = url
        item["product_name"] = product_name
        item["brand"] = brand
        item["brand_url"] = brand_url
        item["brand_logo"] = brand_logo
        item["gender"] = gender
        item["launch_year"] = launch_year
        item["fragrance_family"] = fragrance_family
        item["perfumer"] = ", ".join(perfumer_list)
        item["description"] = description
        item["main_image"] = main_image
        item["main_accords"] = accords
        item["top_notes"] = levels["top"]
        item["middle_notes"] = levels["middle"]
        item["base_notes"] = levels["base"]
        item["rating_value"] = rating_value
        item["rating_count"] = rating_count
        item["review_count"] = review_count
        item["reviews_scraped"] = len(reviews)
        item["also_like"] = also_like
        item["amazon_title"] = ""
        item["amazon_price"] = ""
        item["amazon_currency"] = ""
        item["amazon_url"] = ""
        item["reviews"] = reviews

        if review_count.isdigit() and int(review_count) != len(reviews):
            logging.warning(f"{url}: page says {review_count} reviews, parsed {len(reviews)}")
        return item

    @staticmethod
    def parse_accords(links, bars):
        """accord names + strength. The 'search by accords' link holds the
        english names and 0-100 strengths; bar widths are the fallback."""
        for link in links:
            query = parse_qs(urlparse(link.replace("&amp;", "&")).query)
            accords = [{"accord": k, "strength": float(v[0])}
                       for k, v in query.items() if not k.startswith("f_") and v and v[0].replace(".", "").isdigit()]
            if accords:
                return accords
        accords = []
        for bar in bars:
            name = clean(bar.xpath(".//span/text()").get())
            width = re.search(r"width:\s*([\d.]+)%", bar.xpath("./@style").get() or "")
            if name and width:
                accords.append({"accord": name, "strength": round(float(width.group(1)), 1)})
        return accords

    @staticmethod
    def parse_reviews(sel, product_id, url, product_name):
        """every review of the 'all reviews' block"""
        REVIEW_XPATH = '//div[@id="all-reviews"]//div[@itemprop="review"]'
        reviews, seen = [], set()
        for card in sel.xpath(REVIEW_XPATH):
            review_id = card.xpath('.//vote-buttons-new/@comment-id').get()
            if not review_id:
                review_id = (card.xpath('.//div[starts-with(@id,"review_")]/@id').get() or "").replace("review_", "")
            if review_id in seen:
                continue
            seen.add(review_id)

            body = card.xpath('.//div[@itemprop="reviewBody"]//div[starts-with(@id,"review_")]').get()
            if not body:
                body = card.xpath('.//div[@itemprop="reviewBody"]').get()
            votes = card.xpath('.//user-perfume-votes-new/@*[name()=":perfume-votes"]').get()
            try:
                votes = json.loads(votes) if votes else {}
            except ValueError:
                votes = {}

            reviews.append({
                "review_id": review_id,
                "reviewer": clean(card.xpath('.//*[@itemprop="author"]/meta[@itemprop="name"]/@content').get()),
                "reviewer_url": card.xpath('.//span[contains(@class,"idLinkify") and starts-with(@title,"http")]/@title').get() or "",
                "review_date": card.xpath('.//span[@itemprop="datePublished"]/@content').get() or "",
                "review_datetime_text": clean(card.xpath('.//span[@itemprop="datePublished"]/text()').get()),
                "review_text": html_to_text(body),
                "reviewer_rating": votes.get("rating"),
                "winter": votes.get("winter"),
                "spring": votes.get("spring"),
                "summer": votes.get("summer"),
                "autumn": votes.get("autumn"),
                "day": votes.get("day"),
                "night": votes.get("night"),
                "longevity": votes.get("longevity"),
                "sillage": votes.get("sillage"),
                "gender": votes.get("gender"),
                "relation": votes.get("relation"),
            })
        return reviews

    # ------------------------------------------------------------ amazon
    @staticmethod
    def decrypt_slots(page_html):
        """The 'where to buy' boxes are AES-encrypted inside the page
        (<vue-encrypt-postscribe slotid=.. slotpayload=..>, key = slotid).
        Returns the decrypted html/script of each box."""
        from Crypto.Cipher import AES

        def evp(password, salt, n=48):
            out, prev = b"", b""
            while len(out) < n:
                prev = hashlib.md5(prev + password + salt).digest()
                out += prev
            return out

        out = []
        for slot_id, payload in re.findall(
                r"<vue-encrypt-postscribe[^>]*slotid='([^']+)' slotpayload='(.*?)'", page_html, flags=re.S):
            try:
                data = json.loads(html_lib.unescape(payload).replace("\\/", "/"))
                salt, iv = bytes.fromhex(data["s"]), bytes.fromhex(data["iv"])
                plain = AES.new(evp(slot_id.encode(), salt)[:32], AES.MODE_CBC, iv).decrypt(base64.b64decode(data["ct"]))
                plain = plain[:-plain[-1]].decode("utf-8", "ignore")
                if plain.startswith('"'):  # payload is a json string
                    plain = json.loads(plain)
                out.append(plain)
            except Exception as e:
                logging.warning(f"slot decrypt failed: {e}")
        return out

    def get_amazon(self, page_html):
        """Amazon box: title, price, currency, url. The price is not in the
        product page; it sits in a small iframe page (c.fimgs.net/f/<country>/...)
        whose address is inside the encrypted box."""
        empty = {"amazon_title": "", "amazon_price": "", "amazon_currency": "", "amazon_url": ""}
        for slot in self.decrypt_slots(page_html):
            iframe = re.search(r"baseUrl\s*=\s*'(https://c\.fimgs\.net/f/[^']+)'", slot)
            if not iframe:
                continue
            frame_html = self.fetch(iframe.group(1), referer=BASE_URL + "/", raise_limit=False)
            if not frame_html:
                return empty
            return self.parse_amazon(frame_html) or empty
        return empty

    @staticmethod
    def parse_amazon(frame_html):
        sel = Selector(text=frame_html)
        links = sel.xpath('//a[contains(@href,"amazon.")]')
        for link in links:
            nodes = [clean(t) for t in link.xpath(".//text()").getall() if clean(t)]
            price = next((PRICE_RE.search(t) for t in nodes if PRICE_RE.search(t)), None)
            if not price:
                continue
            title = [t for t in nodes if not PRICE_RE.fullmatch(t) and "Amazon" not in t[:12]]
            title = max(title, key=len) if title else ""
            title = PRICE_RE.sub("", title).strip() if title.endswith(price.group(0)) else title
            symbol = price.group(1)
            return {
                "amazon_title": title,
                "amazon_price": price.group(2).replace(",", "").rstrip("."),
                "amazon_currency": CURRENCIES.get(symbol, symbol.replace("Rs.", "INR").replace("Rs", "INR")),
                "amazon_url": link.xpath("./@href").get(),
            }
        return None

    # ------------------------------------------------------------ close
    def close(self):
        """connection close"""
        if self.mongo:
            from items import close_db
            close_db()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fragrantica product parser")
    ap.add_argument("--file", help="parse one saved html file and print the item (no Mongo, no network)")
    ap.add_argument("--url", help="product url of the saved file (needed for the product id)")
    ap.add_argument("--limit", type=int, help="parse only N new urls")
    args = ap.parse_args()

    parser_obj = Parser()
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            page = f.read()
        canonical = Selector(text=page).xpath('//link[@rel="canonical"]/@href').get()
        data = parser_obj.parse_item(args.url or canonical, page)
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        parser_obj.start(limit=args.limit)
        parser_obj.close()