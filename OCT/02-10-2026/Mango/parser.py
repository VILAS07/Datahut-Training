import json
import re

from bs4 import BeautifulSoup


# ==========================================================
# CLEAN TEXT
# ==========================================================

def clean_text(value):

    if value is None:
        return ""

    if isinstance(value, (list, tuple)):
        value = " ".join(str(x) for x in value)

    value = str(value)

    value = BeautifulSoup(
        value,
        "html.parser"
    ).get_text(
        " ",
        strip=True
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    ).strip()

    return value


# ==========================================================
# GET JSON-LD
# ==========================================================

def get_jsonld_data(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    data = []

    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):

        raw = script.string or script.get_text()

        if not raw:
            continue

        try:

            parsed = json.loads(
                raw.strip()
            )

            if isinstance(parsed, list):
                data.extend(parsed)

            elif isinstance(parsed, dict):
                data.append(parsed)

        except Exception:
            continue

    return data


# ==========================================================
# GET PRODUCT GROUP
# ==========================================================

def get_product_group(data):

    for item in data:

        if not isinstance(item, dict):
            continue

        if item.get("@type") == "ProductGroup":

            return item

    return {}


# ==========================================================
# GET PRODUCT VARIANTS
# ==========================================================

def get_variants(data):

    variants = []

    for item in data:

        if not isinstance(item, dict):
            continue

        if item.get("@type") == "Product":

            variants.append(item)

    return variants


# ==========================================================
# PRODUCT NAME
# ==========================================================

def get_product_name(
    product_group,
    variants
):

    # Best source:
    # ProductGroup.name

    name = clean_text(
        product_group.get("name")
    )

    if name:

        return name

    # Fallback:
    # variant name without "- Size 6"

    for variant in variants:

        name = clean_text(
            variant.get("name")
        )

        if not name:
            continue

        name = re.sub(
            r"\s*-\s*Size\s+.+$",
            "",
            name,
            flags=re.I
        )

        return name

    return ""


# ==========================================================
# SIZE LIST
# ==========================================================

def get_sizes(
    html,
    variants
):

    sizes = []

    # ------------------------------------------------------
    # METHOD 1:
    # Next internal product options
    # ------------------------------------------------------

    pattern = re.compile(
        r'"options"\s*:\s*\{\s*"options"\s*:\s*\[(.*?)\]',
        re.S
    )

    matches = pattern.findall(
        html
    )

    for block in matches:

        names = re.findall(
            r'"name"\s*:\s*"([^"]+)"',
            block
        )

        for name in names:

            name = clean_text(name)

            if name and name not in sizes:

                sizes.append(name)

    if sizes:

        return sizes

    # ------------------------------------------------------
    # METHOD 2:
    # HTML size buttons
    # ------------------------------------------------------

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    buttons = soup.select(
        '[data-testid="size-chips-button-group"] button'
    )

    for button in buttons:

        value = (
            button.get("aria-label")
            or button.get_text(
                " ",
                strip=True
            )
        )

        if not value:
            continue

        value = re.sub(
            r"\s+available.*$",
            "",
            value,
            flags=re.I
        )

        value = clean_text(
            value
        )

        if value and value not in sizes:

            sizes.append(value)

    if sizes:

        return sizes

    # ------------------------------------------------------
    # METHOD 3:
    # JSON-LD variant size
    # ------------------------------------------------------

    for variant in variants:

        size = clean_text(
            variant.get("size")
        )

        if size and size not in sizes:

            sizes.append(size)

    return sizes


# ==========================================================
# DESCRIPTION
# ==========================================================

def get_description(
    product_group,
    variants
):

    # ProductGroup description

    description = clean_text(
        product_group.get(
            "description"
        )
    )

    if description:

        return description

    # Variant description

    for variant in variants:

        description = clean_text(
            variant.get(
                "description"
            )
        )

        if not description:
            continue

        # Ignore generic Next SEO description

        if (
            "Shop the latest women's fashion"
            in description
        ):

            continue

        return description

    return ""


# ==========================================================
# CATEGORY
# ==========================================================

def get_category(html):

    # Next internal data contains:
    #
    # "category":"Dresses"

    match = re.search(
        r'"category"\s*:\s*"([^"]+)"',
        html
    )

    if match:

        return clean_text(
            match.group(1)
        )

    return ""


# ==========================================================
# PRICE
# ==========================================================

def get_price(
    html,
    variants
):

    # JSON-LD offer

    for variant in variants:

        offers = variant.get(
            "offers"
        )

        if isinstance(
            offers,
            dict
        ):

            price = offers.get(
                "price"
            )

            if price is not None:

                return f"£{price}"

    # Next internal data

    match = re.search(
        r'"priceUnformatted"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        html
    )

    if match:

        return f"£{match.group(1)}"

    # Generic price fallback

    match = re.search(
        r'"price"\s*:\s*"([0-9]+(?:\.[0-9]+)?)"',
        html
    )

    if match:

        return f"£{match.group(1)}"

    return ""


# ==========================================================
# IMAGE
# ==========================================================

def get_image(
    product_group,
    variants
):

    image = product_group.get(
        "image"
    )

    if isinstance(
        image,
        list
    ):

        if image:

            return clean_text(
                image[0]
            )

    if isinstance(
        image,
        str
    ):

        return clean_text(
            image
        )

    # Variant fallback

    for variant in variants:

        image = variant.get(
            "image"
        )

        if isinstance(
            image,
            list
        ):

            if image:

                return clean_text(
                    image[0]
                )

        elif isinstance(
            image,
            str
        ):

            return clean_text(
                image
            )

    return ""


# ==========================================================
# COLOUR
# ==========================================================

def get_colour(variants):

    for variant in variants:

        colour = (
            variant.get("color")
            or variant.get("colour")
        )

        if colour:

            return clean_text(
                colour
            )

    return ""


# ==========================================================
# GENDER
# ==========================================================

def get_gender(html):

    match = re.search(
        r'"gender"\s*:\s*"([^"]+)"',
        html
    )

    if match:

        return clean_text(
            match.group(1)
        )

    return "Women"


# ==========================================================
# MATERIAL
# ==========================================================

def get_material(
    variants,
    html
):

    for variant in variants:

        material = variant.get(
            "material"
        )

        if material:

            return clean_text(
                material
            )

    match = re.search(
        r'"material"\s*:\s*"([^"]+)"',
        html
    )

    if match:

        return clean_text(
            match.group(1)
        )

    return ""


# ==========================================================
# FIT
# ==========================================================

def get_fit(
    variants,
    html
):

    for variant in variants:

        properties = variant.get(
            "additionalProperty"
        )

        if isinstance(
            properties,
            list
        ):

            for prop in properties:

                if not isinstance(
                    prop,
                    dict
                ):
                    continue

                if prop.get("name") == "Fit":

                    value = prop.get(
                        "value"
                    )

                    if value:

                        return clean_text(
                            value
                        )

    match = re.search(
        r'"fit"\s*:\s*"([^"]+)"',
        html
    )

    if match:

        return clean_text(
            match.group(1)
        )

    return ""


# ==========================================================
# OCCASION
# ==========================================================

def get_occasion(
    product_group,
    variants
):

    for source in [
        product_group,
        *variants
    ]:

        for key in [
            "occasion",
            "occasionTag",
            "occasionTags"
        ]:

            value = source.get(
                key
            )

            if value:

                if isinstance(
                    value,
                    list
                ):

                    return ", ".join(
                        clean_text(x)
                        for x in value
                    )

                return clean_text(
                    value
                )

    return ""


# ==========================================================
# MAIN PARSER
# ==========================================================

def parse_product(
    html,
    keyword,
    rank,
    pdp_url
):

    # Get JSON-LD

    data = get_jsonld_data(
        html
    )

    # Get ProductGroup

    product_group = get_product_group(
        data
    )

    # Get Product variants

    variants = get_variants(
        data
    )

    # Build result

    product = {

        "keyword": keyword,

        "rank": rank,

        "product_name": get_product_name(
            product_group,
            variants
        ),

        "size": get_sizes(
            html,
            variants
        ),

        "description": get_description(
            product_group,
            variants
        ),

        "category": get_category(
            html
        ),

        "price": get_price(
            html,
            variants
        ),

        "main_image_url": get_image(
            product_group,
            variants
        ),

        "pdp_url": pdp_url,

        "colour": get_colour(
            variants
        ),

        "gender": get_gender(
            html
        ),

        "material": get_material(
            variants,
            html
        ),

        "fit": get_fit(
            variants,
            html
        ),

        "occasion": get_occasion(
            product_group,
            variants
        )
    }

    return product