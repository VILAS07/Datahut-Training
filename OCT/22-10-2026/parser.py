import json
import logging
import os
import re
from lxml import html as lxml_html
from parsel import Selector
from settings import (
    HEADERS, EXTRACTION_DATE, SNAPSHOT_DIR, get_response,
)
from settings import PRODUCT_URL_FILE, FAILED_FILE
from items import CsvStore, PRODUCT_URL_HEADERS, FAILED_HEADERS
from export import Export

RAW_LIMIT = 3  # max debug html files kept

# ---- sections we do NOT want in the snapshot ----
EXCLUDE_HEADINGS = [
    "Variations of this style",
    "How about these?",
    "More from",
    "Better together",
    "Often viewed with each other",
    "More Brands",
    "More Inspiration",
    "Deals, drops and trends",
]


class Parser:
    """Product detail parser + product-details-only HTML snapshot (curl based)"""

    def __init__(self):
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        self.products = CsvStore(PRODUCT_URL_FILE, PRODUCT_URL_HEADERS, "product_url")
        self.failed = CsvStore(FAILED_FILE, ["url", "stage"], "url")
        self.export = Export()

    # ---------------- details-only snapshot ----------------
    @staticmethod
    def save_snapshot(sel, sku):
        """Save page html with the recommendation carousels, footer etc. removed"""

        path = os.path.join(SNAPSHOT_DIR, f"{sku}.html")
        try:
            root = sel.root
            for el in list(root.iter()):
                if not isinstance(el.tag, str) or el.getparent() is None:
                    continue
                if len(el) == 0 and (el.text or "").strip().startswith(tuple(EXCLUDE_HEADINGS)):
                    node = el
                    for _ in range(6):
                        parent = node.getparent()
                        if parent is None or parent.tag in ("main", "body", "html"):
                            break
                        node = parent
                        if parent.tag in ("section", "aside"):
                            break
                    if node.tag not in ("main", "body", "html") and node.getparent() is not None:
                        node.getparent().remove(node)
            for tag in ("footer", "script", "style", "noscript"):
                for el in root.xpath(f"//{tag}"):
                    if el.getparent() is not None:
                        el.getparent().remove(el)
            with open(path, "w", encoding="utf-8") as f:
                f.write(lxml_html.tostring(root, encoding="unicode"))
            return path
        except Exception as e:
            logging.warning(f"snapshot failed {sku}: {e}")
            return ""

    # ---------------- parsing ----------------
    def start(self):
        """Read product urls from product_urls.csv and parse each one"""

        for product in list(self.products.rows):
            url = product["product_url"]
            if self.export.has(url):
                continue  # already parsed (resume)
            response = get_response(url, headers=HEADERS)
            if response:
                self.parse_item(url, response, product)
            else:
                self.failed.add({"url": url, "stage": "product"})

    SECTION_TITLES = ["Material & care", "Details", "Size & fit"]
    SECTION_STOP = {"View manufacturing details", "Open size guide", "Follow",
                    "Report a legal concern", "All reviews"}

    @classmethod
    def section_pairs(cls, sel, title):
        """Accordion section text -> ['Label: value', ...]. Works on the flat text order of the page,
        so it does not depend on the html structure."""

        strings = [t.strip() for t in sel.xpath(
            "//body//text()[not(ancestor::script) and not(ancestor::style) and not(ancestor::noscript)]"
        ).extract() if t.strip()]

        for i, s in enumerate(strings):
            # the real heading is followed (within 3 texts) by a 'Label:' text
            if s != title or not any(x.endswith(":") for x in strings[i + 1:i + 4]):
                continue
            block = []
            for x in strings[i + 1:]:
                if x in cls.SECTION_TITLES or x in cls.SECTION_STOP:
                    break
                block.append(x)
            pairs, label, value = [], None, []
            for x in block:
                if x.endswith(":"):
                    if label:
                        pairs.append(f"{label}: {' '.join(value)}".strip())
                    label, value = x[:-1].strip(), []
                elif label:
                    value.append(x)
                elif ": " in x:
                    pairs.append(x)
            if label:
                pairs.append(f"{label}: {' '.join(value)}".strip())
            if pairs:
                return pairs
        return []

    @staticmethod
    def grab_json(text, key, check=None):
        """Decode the json value that follows "key": anywhere in the page source"""

        decoder = json.JSONDecoder()
        for m in re.finditer(f'"{key}":', text):
            try:
                value, _ = decoder.raw_decode(text, m.end())
            except ValueError:
                continue
            if check is None or check(value):
                return value
        return None

    @staticmethod
    def load_breadcrumbs(sel):
        for text in sel.xpath('//script[@type="application/ld+json"]/text()').extract():
            try:
                data = json.loads(text)
            except Exception:
                continue
            for block in (data if isinstance(data, list) else [data]):
                if isinstance(block, dict) and block.get("@type") == "BreadcrumbList":
                    return [str(i.get("name", "")).strip() for i in block.get("itemListElement", [])
                            if i.get("name")]
        return []

    @staticmethod
    def load_jsonld(sel):
        """Return the Product / ProductGroup json-ld dict"""

        for text in sel.xpath('//script[@type="application/ld+json"]/text()').extract():
            try:
                data = json.loads(text)
            except Exception:
                continue
            blocks = data if isinstance(data, list) else [data]
            for block in blocks:
                if isinstance(block, dict) and block.get("@type") in ("Product", "ProductGroup"):
                    return block
        return {}

    def parse_item(self, url, response, product=None):
        sel = Selector(text=response.text)
        ld = self.load_jsonld(sel)

        # data embedded in the page source (sizes+stock+price, material/details/size&fit)
        raw = response.text
        simples = self.grab_json(raw, "simplesWithStock",
                                 lambda v: isinstance(v, list) and v and isinstance(v[0], dict) and "size" in v[0]) or []
        clusters = self.grab_json(raw, "attributeSuperClusters", lambda v: isinstance(v, list) and v) or []
        sections = {}
        for cluster in clusters:
            sections[cluster.get("id")] = [
                re.sub(r"\s+", " ", f"{a['key']}: {a['value']}").strip()
                for cl in cluster.get("clusters", []) for a in cl.get("attributes", [])
                if a.get("key") and a.get("value")]

        # XPATH (verify against live html - see notes)
        NAME_XPATH = "//h1//text()"
        BRAND_XPATH = '(//h1/preceding::a[1] | //h1/preceding::span[1])[last()]//text()'
        PRICE_XPATH = '//*[contains(text(),"VAT included")]/preceding::*[contains(text(),"£")][1]//text()'
        COLOUR_XPATH = '//*[starts-with(normalize-space(text()),"Colour:")]/text()'
        IMAGES_XPATH = '//ul//img[contains(@src,"zalando")]/@src | //img[contains(@src,"mosaic")]/@src'
        BREADCRUMBS_XPATH = '//nav[contains(@aria-label,"readcrumb")]//a/text() | //a[@aria-label="Back"]/text()'
        SIZES_XPATH = '//select//option/text() | //*[@data-testid="pdp-size-picker"]//li//text()'

        # EXTRACT
        offers = ld.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        brand = ld.get("brand")
        brand = brand.get("name") if isinstance(brand, dict) else brand

        product_name = ld.get("name") or " ".join(sel.xpath(NAME_XPATH).extract())
        brand = brand or " ".join(sel.xpath(BRAND_XPATH).extract())
        sku = ld.get("sku") or self.sku_from_url(url)
        currency = offers.get("priceCurrency") or "GBP"
        price = offers.get("price") or offers.get("lowPrice") or ""
        if not price:
            price_text = " ".join(sel.xpath(PRICE_XPATH).extract())
            m = re.search(r"[\d,]+\.\d{2}", price_text)
            price = m.group(0).replace(",", "") if m else ""
        availability = str(offers.get("availability", "")).split("/")[-1]
        rating = (ld.get("aggregateRating") or {}).get("ratingValue", "")
        review_count = (ld.get("aggregateRating") or {}).get("reviewCount", "")
        description = ld.get("description", "")
        colour = ld.get("color") or " ".join(sel.xpath(COLOUR_XPATH).extract()).replace("Colour:", "")
        images = ld.get("image") or sel.xpath(IMAGES_XPATH).extract()
        images = [images] if isinstance(images, str) else images
        sizes = [s.strip() for s in sel.xpath(SIZES_XPATH).extract()
                 if s.strip() and "size" not in s.lower()]
        material = sections.get("material_care") or self.section_pairs(sel, "Material & care")
        details = sections.get("details") or self.section_pairs(sel, "Details")
        size_fit = sections.get("size_fit") or self.section_pairs(sel, "Size & fit")
        fit = next((x.split(":", 1)[1].strip() for x in size_fit if x.lower().startswith("fit:")), "")

        # occasion / style: json-ld additionalProperty + any matching label on the page
        occasion = []
        props = ld.get("additionalProperty") or []
        props = [props] if isinstance(props, dict) else props
        for prop in props:
            if isinstance(prop, dict) and any(k in str(prop.get("name", "")).lower() for k in ("occasion", "style")):
                occasion.append(str(prop.get("value", "")).strip())
        occasion += [x.split(":", 1)[1].strip() for x in material + details + size_fit
                     if any(k in x.split(":", 1)[0].lower() for k in ("occasion", "style"))]
        occasion = list(dict.fromkeys(o for o in occasion if o))

        gender = ld.get("gender")
        gender = gender.get("name") if isinstance(gender, dict) else gender
        if isinstance(gender, list):
            gender = " | ".join(str(g) for g in gender)
        gender = gender or (product.get("category", "") if product else "")
        product_type = ld.get("category")
        product_type = " > ".join(product_type) if isinstance(product_type, list) else product_type
        product_type = product_type or (product.get("subcategory", "") if product else "")

        if not (material or details or size_fit):
            # sections not found in html -> keep raw page so selectors can be fixed
            # only keep the first RAW_LIMIT pages for debugging (never one per product)
            existing = [f for f in os.listdir(SNAPSHOT_DIR) if f.startswith("RAW_")]
            if len(existing) < RAW_LIMIT:
                raw = os.path.join(SNAPSHOT_DIR, f"RAW_{self.sku_from_url(url)}.html")
                with open(raw, "w", encoding="utf-8") as f:
                    f.write(response.text)
                logging.warning(f"no Material/Details/Size&fit found, raw html saved: {raw}")
            else:
                logging.warning("no Material/Details/Size&fit found")
        breadcrumbs = [t.strip() for t in sel.xpath(BREADCRUMBS_XPATH).extract() if t.strip()]

        # PRICES: json-ld "price" is the full price on discounted items, so the real selling
        # price comes from the listing tile (or the "for £xx" text in the description)
        def num(v):
            m = re.search(r"[\d,]+(?:\.\d+)?", str(v or ""))
            return float(m.group(0).replace(",", "")) if m else None

        desc_price = re.search(r"for £([\d,]+\.\d{2})", description or "")
        current = (num(product.get("price")) if product else None) \
            or (num(desc_price.group(1)) if desc_price else None) or num(price)
        was = re.findall(r"£\s?([\d,]+\.\d{2})", " ".join(sel.xpath("//s//text() | //del//text()").extract()))
        candidates = [num(price), num(product.get("regular_price")) if product else None]
        candidates += [num(w) for w in was]
        higher = [c for c in candidates if c and current and c > current]
        regular_price = f"{max(higher):.2f}" if higher else ""
        price = f"{current:.2f}" if current else price
        discount = f"{round((1 - current / float(regular_price)) * 100)}%" if regular_price and current else ""

        # JSON overrides (most reliable source)
        if simples:
            sizes = [str(x["size"]) for x in simples]  # only sizes that are in stock are listed
            availability = "InStock"
            offer_price = ((simples[0].get("allOffers") or [{}])[0].get("price")) or {}
            orig = (offer_price.get("original") or {}).get("amount")
            promo = (offer_price.get("promotional") or {}).get("amount")
            if orig:
                current = (promo or orig) / 100
                price = f"{current:.2f}"
                regular_price = f"{orig / 100:.2f}" if promo and promo < orig else ""
                discount = f"{round((1 - current / (orig / 100)) * 100)}%" if regular_price else ""
        elif '"simplesWithStock":[]' in raw:
            sizes, availability = [], "OutOfStock"
        crumbs = self.load_breadcrumbs(sel)
        if crumbs:
            breadcrumbs = crumbs
            product_type = crumbs[-1]
        gm = re.search(r'"navigationTargetGroup":"([A-Z]+)"', raw)
        if gm:
            gender = gm.group(1).title()

        # CLEAN
        description = re.sub(r"\s*for £[\d,.]+ \(\d{4}-\d{2}-\d{2}\).*$", "", description or "").strip()
        product_name = re.sub(r"\s+", " ", product_name).strip()
        brand = re.sub(r"\s+", " ", str(brand)).strip()
        colour = re.sub(r"\s+", " ", str(colour)).strip()
        images = [re.sub(r"\?.*$", "", i).strip() for i in images]

        # snapshot must be taken last: it removes nodes from the tree
        snapshot = self.save_snapshot(sel, sku or "product")

        # ITEM YEILD
        item = {}
        item["extraction_date"] = EXTRACTION_DATE
        item["website"] = "Zalando UK"
        item["category"] = product.get("category", "") if product else ""
        item["subcategory"] = product.get("subcategory", "") if product else ""
        item["product_url"] = url
        item["product_name"] = product_name
        item["brand"] = brand
        item["sku"] = sku
        item["colour"] = colour
        item["currency"] = currency
        item["selling_price"] = str(price)
        item["regular_price"] = regular_price
        item["percentage_discount"] = discount
        item["badge"] = product.get("badge", "") if product else ""
        item["availability"] = availability
        item["sizes"] = sizes
        item["rating"] = str(rating)
        item["review_count"] = str(review_count)
        item["description"] = description
        item["gender"] = gender
        item["product_type"] = product_type
        item["material_and_care"] = " | ".join(material)
        item["details"] = " | ".join(details)
        item["size_and_fit"] = " | ".join(size_fit)
        item["fit"] = fit
        item["occasion_style"] = " | ".join(occasion)
        item["breadcrumbs"] = ">".join(breadcrumbs)
        item["images"] = images

        logging.info(item)
        self.export.write(item)  # row is on disk (csv) before the html is removed
        try:
            if snapshot and os.path.exists(snapshot):
                os.remove(snapshot)  # finished -> delete the saved html
        except OSError:
            pass

    @staticmethod
    def sku_from_url(url):
        m = re.search(r"-([a-z0-9]{9}-[a-z0-9]{3})\.html", url, re.I)
        return m.group(1).upper() if m else ""

    def close(self):
        """connection close"""
        pass


if __name__ == "__main__":
    import sys
    parser_obj = Parser()
    try:
        if len(sys.argv) > 1:  # test one url:  python parser.py <product_url>
            resp = get_response(sys.argv[1], headers=HEADERS)
            if resp:
                parser_obj.parse_item(sys.argv[1], resp)
        else:
            parser_obj.start()
    finally:
        parser_obj.close()