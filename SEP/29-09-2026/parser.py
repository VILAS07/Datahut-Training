"""Parser for John Lewis product pages."""

import json
import re
from parsel import Selector


def clean_text(value):
    if not value:
        return ""

    return re.sub(r"\s+", " ", value).strip()


def parse_product(html, url):
    """
    Parse a John Lewis product page.

    Args:
        html: Page HTML as string
        url: Product URL

    Returns:
        dict containing product information
    """

    selector = Selector(text=html)

    # ---------------------------------------------------------
    # PRODUCT ID
    # ---------------------------------------------------------

    match = re.search(r"/p(\d+)", url)

    product_id = match.group(1) if match else ""

    # ---------------------------------------------------------
    # JSON-LD
    # ---------------------------------------------------------

    json_ld_items = selector.xpath(
        '//script[@type="application/ld+json"]/text()'
    ).getall()

    json_products = []

    for item in json_ld_items:

        try:
            data = json.loads(item)

            if isinstance(data, list):
                json_products.extend(data)

            elif isinstance(data, dict):

                if "@graph" in data:
                    graph = data["@graph"]

                    if isinstance(graph, list):
                        json_products.extend(graph)

                else:
                    json_products.append(data)

        except Exception:
            continue

    product_data = {}

    for item in json_products:

        if not isinstance(item, dict):
            continue

        item_type = item.get("@type")

        if item_type == "Product":
            product_data = item
            break

    # ---------------------------------------------------------
    # NAME
    # ---------------------------------------------------------

    name = clean_text(
        product_data.get("name")
        or selector.xpath("//h1/text()").get()
        or selector.xpath("//title/text()").get()
    )

    # ---------------------------------------------------------
    # BRAND
    # ---------------------------------------------------------

    brand = product_data.get("brand", "")

    if isinstance(brand, dict):
        brand = brand.get("name", "")

    brand = clean_text(brand)

    # ---------------------------------------------------------
    # PRICE
    # ---------------------------------------------------------

    price = None
    currency = "GBP"

    offers = product_data.get("offers")

    if isinstance(offers, dict):

        price = offers.get("price")
        currency = offers.get("priceCurrency") or "GBP"

    elif isinstance(offers, list) and offers:

        first_offer = offers[0]

        if isinstance(first_offer, dict):
            price = first_offer.get("price")
            currency = (
                first_offer.get("priceCurrency")
                or "GBP"
            )

    # Fallback price search
    if price is None:

        price_match = re.search(
            r'"price"\s*:\s*"?(?:£)?([\d,.]+)',
            html
        )

        if price_match:
            price = price_match.group(1)

    try:
        if price is not None:
            price = float(
                str(price).replace(",", "")
            )
    except Exception:
        pass

    # ---------------------------------------------------------
    # AVAILABILITY
    # ---------------------------------------------------------

    availability = ""

    if isinstance(offers, dict):
        availability = offers.get(
            "availability",
            ""
        )

    if availability:
        availability = availability.split("/")[-1]

    if not availability:

        if "InStock" in html:
            availability = "InStock"

        elif "OutOfStock" in html:
            availability = "OutOfStock"

        else:
            availability = ""

    # ---------------------------------------------------------
    # DESCRIPTION
    # ---------------------------------------------------------

    description = clean_text(
        product_data.get("description")
    )

    if not description:

        description = clean_text(
            selector.xpath(
                '//meta[@name="description"]/@content'
            ).get()
        )

    # ---------------------------------------------------------
    # IMAGES
    # ---------------------------------------------------------

    images = []

    product_images = product_data.get("image", [])

    if isinstance(product_images, str):
        product_images = [product_images]

    if isinstance(product_images, list):
        images.extend(product_images)

    # Find John Lewis media images in HTML
    html_images = re.findall(
        r'https://media\.johnlewiscontent\.com/[^"\']+',
        html
    )

    for image in html_images:

        image = image.replace(
            "\\u0026",
            "&"
        )

        if image not in images:
            images.append(image)

    # Clean images
    cleaned_images = []

    for image in images:

        if not image:
            continue

        image = image.strip()

        if image not in cleaned_images:
            cleaned_images.append(image)

    images = cleaned_images

    # ---------------------------------------------------------
    # SIZES
    # ---------------------------------------------------------

    sizes = []

    size_patterns = [
        r'"size"\s*:\s*"([^"]+)"',
        r'"name"\s*:\s*"size"\s*,\s*"value"\s*:\s*"([^"]+)"',
    ]

    for pattern in size_patterns:

        matches = re.findall(
            pattern,
            html,
            flags=re.IGNORECASE
        )

        for size in matches:

            size = clean_text(size)

            if (
                size
                and len(size) <= 20
                and size not in sizes
            ):
                sizes.append(size)

    # Common clothing sizes
    common_sizes = [
        "XXXS",
        "XXS",
        "XS",
        "S",
        "M",
        "L",
        "XL",
        "XXL",
        "XXXL",
    ]

    for size in common_sizes:

        if re.search(
            rf'["\']{re.escape(size)}["\']',
            html
        ):
            if size not in sizes:
                sizes.append(size)

    # ---------------------------------------------------------
    # SPECIFICATION
    # ---------------------------------------------------------

    specification = {}

    # Try to find specification JSON
    specification_patterns = [
        r'"specifications"\s*:\s*(\[[^\]]*\])',
        r'"attributes"\s*:\s*(\{.*?\})',
    ]

    for pattern in specification_patterns:

        match = re.search(
            pattern,
            html,
            flags=re.DOTALL
        )

        if not match:
            continue

        try:

            data = json.loads(match.group(1))

            if isinstance(data, dict):
                specification.update(data)

            elif isinstance(data, list):

                for item in data:

                    if not isinstance(item, dict):
                        continue

                    key = (
                        item.get("name")
                        or item.get("label")
                        or item.get("key")
                    )

                    value = (
                        item.get("value")
                        or item.get("text")
                    )

                    if key and value:
                        specification[
                            clean_text(key)
                        ] = clean_text(
                            str(value)
                        )

        except Exception:
            pass

    # ---------------------------------------------------------
    # RESULT
    # ---------------------------------------------------------

    product = {
        "product_id": product_id,
        "name": name,
        "brand": brand,
        "price": price,
        "currency": currency,
        "availability": availability,
        "url": url,
        "images": images,
        "sizes": sizes,
        "description": description,
        "specification": specification,
    }

    return product