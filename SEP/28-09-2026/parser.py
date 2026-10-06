"""Parsing and extraction for MSC Direct pages.

Every selector in this module was discovered by inspecting the DOM that
Camoufox actually renders (homepage carousel, category/search listings and
product detail pages) - nothing here is copied from generic examples.

Rendered DOM that these selectors come from:

Listing cards (carousel and category/search grid, both use the same markup)::

    <div class="... recommendation-horizontal-card ...">      <!-- carousel card -->
    <div class="bg-white rounded-2xl ...">                    <!-- grid card -->
      <div class="recommendation-image-container ...">
        <a href="/product/details/05051644">
          <img class="recommendation-image ..." src="https://cdn.mscdirect.com/global/images/ProductImages/0505164-24.jpg">
      <span class="recomm-slider-price ...">$48.49<span class="text-sm"> /ea.</span></span>
      <div id="topseller_supplier"><p class="... font-bold uppercase ..."><a href="/product/details/05051644"> Bondhus</a>
      <div id="topseller_desc"><p class="... hover:underline ..."><a href="/product/details/05051644"> 22 Piece L-Key ...</a>
      <span class="text-base leading-4">MSC #</span><span><a href="/product/details/05051644"> 05051644</a></span>

Product detail page::

    <h1 id="short-decription">SCRUBS in-a-Bucket (R) Hand Cleaner Towels ...</h1>
    <a id="brand-name" class="hidden lg:block ... uppercase font-bold ...">SCRUBS</a>
    <p id="webPriceId" class="font-bold">$23.51 ea.</p>
    <p id="basePartNumber" data-partnumber="00262220">MSC# 00262220</p>
    <p id="mfr-part-number">Mfr# 42272</p>
    <p class="text-green-700 font-bold text-sm leading-14 mt-5">In Stock</p>
    <table class="w-full specs_table"><td id="Wipe Type" data-value="Hand">...
    <img class="thumbnail-image" src="https://cdn.mscdirect.com/global/images/ProductImages/0026222AQ-21.jpg">

The ``schema.org`` ``Product`` JSON-LD block rendered on detail pages is used
only as a secondary source (for example the manufacturer part number and the
short description MSC publishes inside that block).
"""

import json
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

from lxml import html as lxml_html

from items import merge_records
from settings import PRODUCT_URL_TOKEN

PRICE_RE = re.compile(r"\$\s?[\d,]+(?:\.\d{1,2})?")
MSC_RE = re.compile(r"MSC\s*#\s*:?\s*([0-9]{4,14})", re.IGNORECASE)
MFR_RE = re.compile(r"Mfr\s*#\s*:?\s*([A-Za-z0-9][A-Za-z0-9._/\-]*)", re.IGNORECASE)
MSC_LABEL_RE = re.compile(r"MSC\s*#", re.IGNORECASE)
UNIT_RE = re.compile(r"(/\s?each|/\s?ea\.?|each|\bea\.?)\s*$", re.IGNORECASE)
PRICE_TEXT_RE = re.compile(
    r"^\$\s?[\d,]+(?:\.\d{1,2})?\s*(?:/\s?each|/\s?ea\.?|ea\.?)?$", re.IGNORECASE
)

NOISE_TOKENS = (
    "recommend",
    "glider",
    "carousel",
    "alternate",
    "similar",
    "frequently",
    "related",
    "topseller",
    "top-seller",
    "pdp-rec",
    "pr-rd",
    "review",
    "sticky",
)

AVAILABILITY_WORDS = (
    "in stock",
    "out of stock",
    "backorder",
    "back order",
    "on backorder",
    "limited availability",
    "notify me",
    "on order",
    "ships",
)

HTML_PARSER = lxml_html.HTMLParser(encoding="utf-8")


def clean(value: Optional[str]) -> Optional[str]:
    """Collapse whitespace and turn empty strings into ``None``."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def text_of(node) -> Optional[str]:
    """Whitespace-cleaned text of an lxml node."""
    if node is None or not isinstance(getattr(node, "tag", None), str):
        return None
    return clean(node.text_content())


def _parse(html_text: str) -> "lxml_html.HtmlElement":
    """Build an lxml tree from Camoufox rendered HTML."""
    if isinstance(html_text, str):
        html_text = html_text.encode("utf-8")
    return lxml_html.fromstring(html_text, parser=HTML_PARSER)


def _first_text(node, xpath: str) -> Optional[str]:
    """First non-empty value of ``xpath`` (text nodes or attributes)."""
    if node is None:
        return None
    for value in node.xpath(xpath):
        text = clean(value if isinstance(value, str) else value.text_content())
        if text:
            return text
    return None


def _normalise_url(href: Optional[str], page_url: Optional[str] = None) -> Optional[str]:
    """Absolute, query/fragment free product URL (``/product/details/<MSC>``)."""
    if not href:
        return None
    absolute = urljoin(page_url, href) if page_url else href
    parts = urlsplit(absolute)
    path = parts.path
    if PRODUCT_URL_TOKEN in path:
        head, _, tail = path.partition(PRODUCT_URL_TOKEN)
        path = head + PRODUCT_URL_TOKEN + tail.split("/")[0]
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _in_noise(node) -> bool:
    """True when a node lives inside a recommendation/review/sticky widget."""
    current = node
    while current is not None:
        identifier = " ".join(
            filter(None, (current.get("id") or "", current.get("class") or ""))
        ).lower()
        if any(token in identifier for token in NOISE_TOKENS):
            return True
        current = current.getparent()
    return False


def extract_product_name(node) -> Optional[str]:
    """Product name - ``h1`` on a detail page, the title link on a card.

    Three rendered title shapes exist: the detail page ``h1``, the carousel and
    grid card ``#topseller_desc`` link, and the search result list card
    ``.tn-product-title-wrapper`` (whose first ``p`` is the brand and holds the
    ``uppercase`` class, so it is excluded here).
    """
    name = _first_text(node, "(.//h1)[1]//text()")
    if name:
        return name
    name = _first_text(node, './/*[@id="topseller_desc"]//a//text()')
    if name:
        return name
    name = _first_text(
        node,
        '(.//div[contains(@class, "tn-product-title-wrapper")]'
        '//p[contains(@class, "font-bold") and not(contains(@class, "uppercase"))])'
        "[1]//a//text()",
    )
    if name:
        return name
    for image in node.xpath(".//img[@alt]"):
        alt = clean(image.get("alt"))
        if alt and "product image" not in alt.lower() and "click for more" not in alt.lower():
            return alt
    return None


def extract_brand(node) -> Optional[str]:
    """Brand - ``a#brand-name`` on a detail page, the supplier block on a card."""
    brand = _first_text(node, './/*[@id="brand-name"]//text()')
    if brand:
        return brand
    brand = _first_text(
        node,
        './/a[contains(@class, "uppercase") and contains(@class, "font-bold")]//text()',
    )
    if brand:
        return brand
    brand = _first_text(node, './/*[@id="topseller_supplier"]//a//text()')
    if brand:
        return brand
    return _first_text(
        node,
        './/p[contains(@class, "uppercase") and contains(@class, "font-bold")]//a//text()',
    )


def extract_msc_number(node, page_url: Optional[str] = None) -> Optional[str]:
    """MSC number - data attribute, the "MSC #" label, or the product URL."""
    value = _first_text(node, './/*[@id="basePartNumber"]/@data-partnumber')
    if value:
        return value
    value = _first_text(node, './/*[@id="basePartNumber"]//text()')
    if value:
        match = re.search(r"[0-9]{4,14}", value)
        if match:
            return match.group(0)
    match = MSC_RE.search(text_of(node) or "")
    if match:
        return match.group(1)
    if page_url:
        tail = urlsplit(page_url).path.rstrip("/").rsplit("/", 1)[-1]
        if tail.isdigit():
            return tail
    return None


def extract_manufacturer_number(node) -> Optional[str]:
    """Manufacturer (Mfr#) number - detail page only, cards do not render it."""
    value = _first_text(node, './/*[@id="mfr-part-number"]//text()')
    if value:
        stripped = clean(re.sub(r"^Mfr\s*#?\s*:?\s*", "", value, flags=re.IGNORECASE))
        if stripped:
            return stripped
    match = MFR_RE.search(text_of(node) or "")
    if match:
        return match.group(1)
    return None


def extract_price(node, scoped: bool = False) -> Optional[str]:
    """Price exactly as rendered, e.g. ``$23.51 ea.`` or ``$48.49 /ea.``.

    ``scoped`` skips prices that belong to recommendation rails when parsing a
    product detail page.
    """
    for xpath in (
        './/*[@id="webPriceId"]',
        './/*[@id="totalPriceId"]',
        './/*[@id="totalPriceIdStickyNav"]',
    ):
        for element in node.xpath(xpath):
            text = text_of(element)
            if text and PRICE_RE.search(text):
                return text

    for element in node.xpath(
        "descendant-or-self::*[@data-price-display-text or @data-price]"
    ):
        if scoped and _in_noise(element):
            continue
        text = clean(element.get("data-price-display-text"))
        if not text or not PRICE_RE.search(text):
            raw = clean(element.get("data-price"))
            text = f"${raw}" if raw else None
        if text and PRICE_RE.search(text):
            return text

    candidates = []
    for element in node.xpath(
        './/*[contains(@class, "recomm-slider-price") or '
        'contains(@class, "price") or contains(@id, "price")]'
    ):
        text = text_of(element)
        if not text or len(text) > 40 or not PRICE_RE.search(text):
            continue
        if scoped and _in_noise(element):
            continue
        candidates.append(text)
    for text in candidates:
        if PRICE_TEXT_RE.match(text):
            return text
    if candidates:
        return candidates[0]

    for element in node.iter():
        if not isinstance(element.tag, str):
            continue
        text = text_of(element)
        if not text or len(text) > 30 or not PRICE_RE.search(text):
            continue
        if not UNIT_RE.search(text):
            continue
        if scoped and _in_noise(element):
            continue
        return text
    return None


def extract_availability(node, scoped: bool = True) -> Optional[str]:
    """Stock status, e.g. ``In Stock`` (rendered in the detail page buy box)."""
    for element in node.xpath(
        './/p[contains(@class, "text-green-700") or contains(@class, "text-success") '
        'or contains(@class, "text-red-") or contains(@class, "text-danger") '
        'or contains(@class, "text-orange-")]'
    ):
        text = text_of(element)
        if text and len(text) <= 45 and (not scoped or not _in_noise(element)):
            return text

    for element in node.xpath(".//p[not(*)] | .//span[not(*)]"):
        text = text_of(element)
        if not text or len(text) > 45:
            continue
        lowered = text.lower()
        if not any(lowered.startswith(word) for word in AVAILABILITY_WORDS):
            continue
        if scoped and _in_noise(element):
            continue
        return text
    return None


def extract_description(node) -> Optional[str]:
    """Marketing description from the rendered "Product Details" panel.

    MSC only renders a long description for part of the catalogue; when that
    panel holds nothing but feedback/recommendation widgets this returns
    ``None`` and the caller falls back to the JSON-LD description.
    """
    for heading in node.xpath(".//h2"):
        if clean(heading.text_content()) != "Product Details":
            continue
        article = heading.getparent()
        if article is None:
            continue
        blocks = []
        for element in article.xpath(".//p[not(*)] | .//div[not(*)]"):
            text = text_of(element)
            if not text or not 60 < len(text) < 2000:
                continue
            if _in_noise(element) or "MSC #" in text or "$" in text:
                continue
            blocks.append(text)
        if blocks:
            return max(blocks, key=len)

    for element in node.xpath(
        './/*[contains(@id, "description") or contains(@class, "description")]'
    ):
        text = text_of(element)
        if text and 40 < len(text) < 2000 and "MSC #" not in text:
            if not _in_noise(element):
                return text
    return None


def extract_specifications(node) -> Optional[str]:
    """Specifications as ``Name: Value`` pairs joined with ``"; "``.

    The rendered detail page carries ``<td id="Wipe Type" data-value="Hand">``
    cells inside ``table.specs_table``; a plain key/value table is used as a
    fallback for layouts that render the same data without data attributes.
    """
    pairs: List[str] = []
    for cell in node.xpath('.//table[contains(@class, "specs_table")]//td[@id]'):
        name = clean(cell.get("id"))
        value = clean(cell.get("data-value"))
        if value is None:
            text = text_of(cell)
            if text and ":" in text:
                key, _, tail = text.partition(":")
                name = clean(key) or name
                value = clean(tail)
        if name and value:
            pair = f"{name}: {value}"
            if pair not in pairs:
                pairs.append(pair)

    if not pairs:
        for row in node.xpath(".//table//tr"):
            cells = row.xpath("./td")
            if len(cells) < 2:
                continue
            key = clean(cells[0].text_content())
            value = clean(cells[1].text_content())
            if key and value and key.endswith(":") and ":" not in value:
                pair = f"{key.rstrip(':')}: {value}"
                if pair not in pairs:
                    pairs.append(pair)
    return "; ".join(pairs) if pairs else None


def extract_image_url(node, page_url: Optional[str] = None) -> Optional[str]:
    """Product image URL from the MSC image CDN (query string stripped)."""
    for image in node.xpath(".//img"):
        src = image.get("src") or image.get("data-src") or ""
        if "ProductImages" in src:
            return urljoin(page_url, src.split("?")[0]) if page_url else src.split("?")[0]
    return None


def extract_product_url(node, page_url: Optional[str] = None) -> Optional[str]:
    """Product URL taken from the product anchors rendered inside ``node``."""
    for anchor in node.xpath(".//a[@href]"):
        href = anchor.get("href") or ""
        if PRODUCT_URL_TOKEN in href:
            return _normalise_url(href, page_url)
    return None


def canonical_product_url(tree, page_url: Optional[str] = None) -> Optional[str]:
    """Product URL of a detail page: its canonical link, else the visited URL."""
    href = _first_text(tree, './/link[@rel="canonical"]/@href')
    if href and PRODUCT_URL_TOKEN in href:
        return _normalise_url(href, page_url)
    return _normalise_url(page_url, page_url)


def _iter_json_ld_products(data):
    """Yield every ``@type: Product`` object inside a JSON-LD document."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_json_ld_products(item)
    elif isinstance(data, dict):
        if data.get("@type") == "Product":
            yield data
        for value in data.values():
            yield from _iter_json_ld_products(value)


def parse_json_ld_product(tree) -> Dict[str, Optional[str]]:
    """Product fields from the JSON-LD block rendered on a detail page.

    Used only to fill fields the DOM does not always render (manufacturer part
    number, published description, availability wording).
    """
    result: Dict[str, Optional[str]] = {}
    for script in tree.xpath('.//script[@type="application/ld+json"]'):
        raw = script.text_content()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        for product in _iter_json_ld_products(data):
            brand = product.get("brand") or {}
            if isinstance(brand, dict):
                brand = brand.get("name")
            offers = product.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            image = product.get("image")
            if isinstance(image, list):
                image = image[0] if image else None
            price = offers.get("price")
            if price is not None and not str(price).startswith("$"):
                price = f"${price}"
            result = {
                "name": clean(product.get("name")),
                "brand": clean(brand),
                "sku": clean(product.get("sku")),
                "mpn": clean(product.get("mpn")),
                "price": clean(price),
                "availability": clean(offers.get("availability")),
                "description": clean(product.get("description")),
                "image": clean(image),
            }
            return result
    return result


def find_cards(tree) -> List:
    """Return the product cards rendered on a listing page.

    A card is the highest ancestor of a ``/product/details/...`` link that still
    renders exactly one "MSC #" label, i.e. the container holding this
    product's image, brand, name, price and MSC number but no other product.
    The homepage carousel and the category/search grid both match this shape.
    """
    cards = []
    seen = set()
    for anchor in tree.xpath('.//a[contains(@href, "%s")]' % PRODUCT_URL_TOKEN):
        node = anchor
        card = None
        while node is not None:
            text = node.text_content() or ""
            if len(text) >= 3000 or len(MSC_LABEL_RE.findall(text)) > 1:
                break
            if MSC_LABEL_RE.search(text):
                card = node
            node = node.getparent()
        if card is None or id(card) in seen:
            continue
        seen.add(id(card))
        cards.append(card)
    return cards


def parse_listing(
    html_text: str, page_url: Optional[str] = None
) -> List[Dict[str, Optional[str]]]:
    """Extract one record per product card rendered on a listing page."""
    tree = _parse(html_text)
    records: List[Dict[str, Optional[str]]] = []
    index: Dict[str, Dict[str, Optional[str]]] = {}
    for card in find_cards(tree):
        record = {
            "product_name": extract_product_name(card),
            "brand": extract_brand(card),
            "msc_number": extract_msc_number(card, page_url),
            "manufacturer_number": extract_manufacturer_number(card),
            "price": extract_price(card),
            "availability": extract_availability(card, scoped=False),
            "description": extract_description(card),
            "specifications": extract_specifications(card),
            "image_url": extract_image_url(card, page_url),
            "product_url": extract_product_url(card, page_url),
        }
        key = record["product_url"] or record["msc_number"]
        if not key:
            continue
        if key in index:
            index[key] = merge_records(index[key], record)
            continue
        index[key] = record
        records.append(record)
    return records


def parse_product(
    html_text: str, page_url: Optional[str] = None
) -> Dict[str, Optional[str]]:
    """Extract every field of a product detail page (DOM first, JSON-LD second)."""
    tree = _parse(html_text)
    json_ld = parse_json_ld_product(tree)
    return {
        "product_name": extract_product_name(tree) or json_ld.get("name"),
        "brand": extract_brand(tree) or json_ld.get("brand"),
        "msc_number": extract_msc_number(tree, page_url) or json_ld.get("sku"),
        "manufacturer_number": extract_manufacturer_number(tree) or json_ld.get("mpn"),
        "price": extract_price(tree, scoped=True) or json_ld.get("price"),
        "availability": extract_availability(tree) or json_ld.get("availability"),
        "description": extract_description(tree) or json_ld.get("description"),
        "specifications": extract_specifications(tree),
        "image_url": extract_image_url(tree, page_url) or json_ld.get("image"),
        "product_url": canonical_product_url(tree, page_url),
    }

