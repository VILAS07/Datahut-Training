import re


def clean_text(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", text).strip()


def get_product_name(page):
    try:
        locator = page.locator("h1").first

        return clean_text(
            locator.inner_text(timeout=10000)
        )

    except Exception:
        return ""


def get_price(page):
    """
    Extract the main product price.

    We avoid simply taking the first £ value from
    the whole page because Next also contains
    payment-plan prices.
    """

    try:

        # First try elements containing price-related
        # data/test identifiers or classes.
        selectors = [
            '[data-testid*="price"]',
            '[class*="price"]',
        ]

        candidates = []

        for selector in selectors:

            locator = page.locator(selector)

            count = locator.count()

            for i in range(count):

                try:

                    text = clean_text(
                        locator.nth(i).inner_text(
                            timeout=3000
                        )
                    )

                    if text and "£" in text:
                        candidates.append(text)

                except Exception:
                    continue

        # Prefer a price that looks like the main
        # standalone product price.
        for text in candidates:

            matches = re.findall(
                r"£\s*([\d,.]+)",
                text
            )

            if len(matches) == 1:

                return f"£{matches[0]}"

    except Exception:
        pass

    # Fallback: inspect body text around the
    # product heading.
    try:

        body = page.locator("body").inner_text()

        product_name = get_product_name(page)

        if product_name and product_name in body:

            start = body.find(product_name)

            nearby = body[
                start:start + 1000
            ]

            # Ignore finance/payment-plan amounts
            # when possible.
            lines = [
                clean_text(x)
                for x in nearby.splitlines()
                if clean_text(x)
            ]

            for line in lines:

                if re.fullmatch(
                    r"£\s*[\d,.]+",
                    line
                ):
                    return line

    except Exception:
        pass

    return ""


def get_colour(page):

    try:

        body = page.locator("body").inner_text()

        match = re.search(
            r"Colour:\s*(.+?)(?=\s+Size:|\s+ADD TO BAG)",
            body,
            re.IGNORECASE | re.DOTALL
        )

        if match:
            return clean_text(
                match.group(1)
            )

    except Exception:
        pass

    return ""


def get_description(page):

    try:

        body = page.locator("body").inner_text()

        match = re.search(
            r"Description\s+(.*?)(?=\s+Customers Also Bought|\s+Reviews|$)",
            body,
            re.IGNORECASE | re.DOTALL
        )

        if match:
            return clean_text(
                match.group(1)
            )

    except Exception:
        pass

    return ""


def get_material(description):

    if not description:
        return ""

    # Capture the composition beginning with Main
    match = re.search(
        r"Main\s+(.+?)(?=\.\s+Our tall collection|$)",
        description,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        return clean_text(
            match.group(1)
        )

    # More general fallback
    match = re.search(
        r"(Main\s+.+?)(?=Our tall collection|$)",
        description,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        return clean_text(
            match.group(1)
        )

    return ""


def get_fit_sizing(page):

    try:

        body = page.locator("body").inner_text()

        patterns = [
            r"This item runs large\.",
            r"This item runs small\.",
            r"This item runs true to size\.",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                body,
                re.IGNORECASE
            )

            if match:
                return clean_text(
                    match.group(0)
                )

    except Exception:
        pass

    return ""


def get_size(page):

    try:

        body = page.locator("body").inner_text()

        if "Choose Size" in body:
            return "Available sizes on PDP"

    except Exception:
        pass

    return ""


def get_category(keyword):

    keyword = keyword.lower()

    if "dress" in keyword:
        return "Dresses"

    if "jeans" in keyword:
        return "Jeans"

    if "jumper" in keyword:
        return "Knitwear"

    if "cardigan" in keyword:
        return "Knitwear"

    if "top" in keyword:
        return "Tops"

    return ""


def get_product_type(keyword):

    keyword = keyword.lower()

    if "dress" in keyword:
        return "Dress"

    if "jeans" in keyword:
        return "Jeans"

    if "jumper" in keyword:
        return "Jumper"

    if "cardigan" in keyword:
        return "Cardigan"

    if "top" in keyword:
        return "Top"

    return ""


def get_occasion_style(keyword):

    keyword = keyword.lower()

    if "dress" in keyword:
        return "Casual"

    if "jeans" in keyword:
        return "Casual"

    if "jumper" in keyword:
        return "Casual"

    if "cardigan" in keyword:
        return "Casual"

    if "top" in keyword:
        return "Casual"

    return ""


def parse_product(
    page,
    keyword,
    rank,
    pdp_url,
    image_url,
):

    product_name = get_product_name(page)

    description = get_description(page)

    item = {
        "keyword": keyword,
        "product_name": product_name,
        "size": get_size(page),
        "product_description": description,
        "category": get_category(keyword),
        "product_type": get_product_type(keyword),
        "price": get_price(page),
        "main_image": image_url,
        "pdp_url": pdp_url,
        "rank": rank,
        "colour": get_colour(page),
        "gender": "Women",
        "material": get_material(description),
        "fit_sizing": get_fit_sizing(page),
        "occasion_style": get_occasion_style(keyword),
    }

    return item