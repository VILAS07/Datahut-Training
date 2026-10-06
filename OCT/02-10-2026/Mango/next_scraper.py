from cloakbrowser import launch
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import json
import re
import time


# ==========================================================
# CONFIG
# ==========================================================

BASE_URL = "https://www.next.co.uk"

KEYWORD = "mini dress"

TOP_N = 10


# ==========================================================
# TEXT CLEANER
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
# JSON-LD
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
# PRODUCT GROUP
# ==========================================================

def get_product_group(data):

    for item in data:

        if not isinstance(item, dict):
            continue

        if item.get("@type") == "ProductGroup":

            return item

    return {}


# ==========================================================
# PRODUCT VARIANTS
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

    name = clean_text(
        product_group.get("name")
    )

    if name:

        return name

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
# SIZES
# ==========================================================

def get_sizes(
    html,
    variants
):

    sizes = []

    # ------------------------------------------------------
    # NEXT INTERNAL SIZE OPTIONS
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
    # HTML SIZE BUTTONS
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

        value = clean_text(value)

        if value and value not in sizes:

            sizes.append(value)

    if sizes:

        return sizes

    # ------------------------------------------------------
    # JSON-LD FALLBACK
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

    description = clean_text(
        product_group.get(
            "description"
        )
    )

    if description:

        return description

    for variant in variants:

        description = clean_text(
            variant.get(
                "description"
            )
        )

        if not description:
            continue

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

    match = re.search(
        r'"priceUnformatted"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        html
    )

    if match:

        return f"£{match.group(1)}"

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
# PARSER
# ==========================================================

def parse_product(
    html,
    keyword,
    rank,
    pdp_url
):

    data = get_jsonld_data(
        html
    )

    product_group = get_product_group(
        data
    )

    variants = get_variants(
        data
    )

    return {

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

        "pdp_url": pdp_url.split("#")[0],

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
        ),
    }


# ==========================================================
# SEARCH URL
# ==========================================================

def get_search_url(keyword):

    return (
        f"{BASE_URL}/search?w={quote(keyword)}"
    )


# ==========================================================
# PRODUCT URL EXTRACTION
# ==========================================================

def get_product_urls(
    page,
    limit=10
):

    selectors = [

        'a[data-testid="product_summary_image_media"]',

        'a[href*="/style/"]',

    ]

    urls = []

    for selector in selectors:

        elements = page.locator(
            selector
        )

        count = elements.count()

        for i in range(count):

            href = elements.nth(i).get_attribute(
                "href"
            )

            if not href:
                continue

            href = urljoin(
                BASE_URL,
                href
            )

            href = href.split("#")[0]

            if "/style/" not in href:
                continue

            if href not in urls:

                urls.append(href)

            if len(urls) >= limit:

                return urls

    return urls


# ==========================================================
# PRINT PRODUCT
# ==========================================================

def print_product(product):

    print("\n")
    print("=" * 70)
    print("PARSED PRODUCT")
    print("=" * 70)

    fields = [

        "keyword",
        "rank",
        "product_name",
        "size",
        "description",
        "category",
        "price",
        "main_image_url",
        "pdp_url",
        "colour",
        "gender",
        "material",
        "fit",
        "occasion",

    ]

    for field in fields:

        print(
            f"{field}: "
            f"{product.get(field, '')}"
        )


# ==========================================================
# MAIN CRAWLER
# ==========================================================

def run():

    browser = None

    parsed_count = 0
    failed_count = 0

    block_checked_urls = 0
    blocked_urls = 0

    search_requests = 0

    try:

        # ==================================================
        # CLOAKBROWSER
        # ==================================================

        print("\n")
        print("=" * 75)
        print("STARTING CLOAKBROWSER")
        print("=" * 75)

        browser = launch(
            headless=False
        )

        page = browser.new_page()

        # ==================================================
        # HOME
        # ==================================================

        response = page.goto(
            BASE_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(
            5000
        )

        print("\n========== HOME ==========")

        if response:

            print(
                "STATUS:",
                response.status
            )

        print(
            "URL:",
            page.url
        )

        print(
            "TITLE:",
            page.title()
        )

        # ==================================================
        # SEARCH
        # ==================================================

        search_url = get_search_url(
            KEYWORD
        )

        print("\n========== SEARCH ==========")

        print(
            "KEYWORD:",
            KEYWORD
        )

        response = page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        search_requests += 1

        page.wait_for_timeout(
            5000
        )

        print(
            "SEARCH URL:",
            page.url
        )

        if response:

            print(
                "SEARCH STATUS:",
                response.status
            )

        print(
            "SEARCH TITLE:",
            page.title()
        )

        # ==================================================
        # BLOCK CHECK
        # ==================================================

        block_checked_urls += 1

        body_text = page.locator(
            "body"
        ).inner_text(
            timeout=10000
        )

        if "Access Denied" in body_text:

            blocked_urls += 1

            print(
                "\nSEARCH BLOCKED"
            )

            print(
                body_text[:1000]
            )

            return

        print(
            "BLOCK CHECKED URL:",
            block_checked_urls
        )

        print(
            "SEARCH BLOCK STATUS: NOT BLOCKED"
        )

        # ==================================================
        # PRODUCT URLS
        # ==================================================

        print(
            "\n========== PRODUCT URL EXTRACTION =========="
        )

        product_urls = get_product_urls(
            page,
            TOP_N
        )

        print(
            "PRODUCT COUNT:",
            len(product_urls)
        )

        for rank, url in enumerate(
            product_urls,
            1
        ):

            print(
                f"RANK {rank}: {url}"
            )

        if not product_urls:

            print(
                "No products found."
            )

            return

        # ==================================================
        # PDP LOOP
        # ==================================================

        for rank, product_url in enumerate(
            product_urls,
            1
        ):

            print("\n")
            print("=" * 75)

            print(
                f"OPENING PDP - RANK {rank}"
            )

            print("=" * 75)

            print(
                "PDP URL:",
                product_url
            )

            try:

                response = page.goto(
                    product_url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                page.wait_for_timeout(
                    3000
                )

                status = (
                    response.status
                    if response
                    else None
                )

                print(
                    "PDP STATUS:",
                    status
                )

                print(
                    "PDP FINAL URL:",
                    page.url
                )

                print(
                    "PDP TITLE:",
                    page.title()
                )

                # ------------------------------------------
                # BLOCK CHECK
                # ------------------------------------------

                block_checked_urls += 1

                body_text = page.locator(
                    "body"
                ).inner_text(
                    timeout=10000
                )

                if "Access Denied" in body_text:

                    blocked_urls += 1

                    print(
                        "PDP BLOCK STATUS: BLOCKED"
                    )

                    print(
                        body_text[:500]
                    )

                    failed_count += 1

                    continue

                print(
                    "BLOCK CHECKED URL:",
                    block_checked_urls
                )

                print(
                    "PDP BLOCK STATUS: NOT BLOCKED"
                )

                # ------------------------------------------
                # GET HTML
                # ------------------------------------------

                html = page.content()

                print(
                    "\nPARSING PRODUCT..."
                )

                # ------------------------------------------
                # PARSE
                # ------------------------------------------

                product = parse_product(
                    html=html,
                    keyword=KEYWORD,
                    rank=rank,
                    pdp_url=product_url
                )

                print_product(
                    product
                )

                parsed_count += 1

                time.sleep(2)

            except Exception as exc:

                failed_count += 1

                print(
                    f"\nERROR processing rank "
                    f"{rank}: {exc}"
                )

        # ==================================================
        # SUMMARY
        # ==================================================

        print("\n")
        print("=" * 75)
        print("CRAWLER SUMMARY")
        print("=" * 75)

        print(
            "Keyword:",
            KEYWORD
        )

        print(
            "Search Requests:",
            search_requests
        )

        print(
            "Product URLs Found:",
            len(product_urls)
        )

        print(
            "Block Checked URLs:",
            block_checked_urls
        )

        print(
            "Blocked URLs:",
            blocked_urls
        )

        print(
            "Parsed Products:",
            parsed_count
        )

        print(
            "Failed Products:",
            failed_count
        )

    finally:

        if browser:

            try:

                browser.close()

            except Exception:

                pass


# ==========================================================
# START
# ==========================================================

if __name__ == "__main__":

    run()