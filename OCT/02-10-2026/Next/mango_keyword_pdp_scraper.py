from playwright.sync_api import sync_playwright
from urllib.parse import quote
import re
import time


KEYWORD = "Mini dress"

SEARCH_URL = (
    "https://shop.mango.com/in/en/search/women/q/"
    + quote(KEYWORD)
)

TOP_N = 10


def clean_text(text):
    if not text:
        return None

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_meta(page, name=None, property_name=None):
    if name:
        locator = page.locator(f'meta[name="{name}"]')
    else:
        locator = page.locator(f'meta[property="{property_name}"]')

    if locator.count() == 0:
        return None

    return locator.first.get_attribute("content")


def extract_sizes(page):
    sizes = []

    # Mango size buttons
    buttons = page.locator("button")

    for i in range(buttons.count()):
        try:
            text = clean_text(buttons.nth(i).inner_text())

            if not text:
                continue

            # Examples:
            # 6 EUR XS
            # 8 EUR S
            # 10 EUR M
            # 12 EUR L
            # 14 EUR XL
            if re.search(r"\bEUR\s+(XXS|XS|S|M|L|XL|XXL)\b", text):
                sizes.append(text)

        except Exception:
            continue

    return list(dict.fromkeys(sizes))


def extract_colour(page):
    body = clean_text(page.locator("body").inner_text())

    match = re.search(
        r"Select a colour\s+(.*?)\s+Select your size",
        body,
        re.IGNORECASE,
    )

    if match:
        colour = clean_text(match.group(1))

        if colour:
            return colour

    return None


def extract_category(page):
    body = clean_text(page.locator("body").inner_text())

    categories = [
        "DRESSES AND JUMPSUITS",
        "JEANS",
        "KNITWEAR",
        "TOPS",
        "TROUSERS",
        "SHIRTS",
        "JACKETS",
        "COATS",
        "SKIRTS",
    ]

    found = []

    for category in categories:
        if category.lower() in body.lower():
            found.append(category)

    return found if found else None


def extract_occasion(page):
    body = clean_text(page.locator("body").inner_text())

    possible_tags = [
        "party",
        "casual",
        "evening",
        "office",
        "formal",
        "beach",
        "sport",
        "work",
    ]

    found = []

    for tag in possible_tags:
        if re.search(rf"\b{re.escape(tag)}\b", body, re.IGNORECASE):
            found.append(tag)

    return list(dict.fromkeys(found))


def extract_main_image(page):
    # Prefer Open Graph image
    image = get_meta(page, property_name="og:image")

    if image:
        return image

    # Fallback: product images
    images = page.locator("img")

    for i in range(min(images.count(), 30)):
        try:
            src = images.nth(i).get_attribute("src")

            if src and "media.mango.com" in src:
                return src

        except Exception:
            continue

    return None


def extract_material(page):
    body = clean_text(page.locator("body").inner_text())

    patterns = [
        r"Composition[:\s]+(.{0,300})",
        r"Material[:\s]+(.{0,300})",
        r"Fabric[:\s]+(.{0,300})",
    ]

    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE)

        if match:
            value = clean_text(match.group(1))

            if value:
                return value

    return None


def extract_fit(page):
    body = clean_text(page.locator("body").inner_text())

    patterns = [
        r"Fit[:\s]+(.{0,150})",
        r"Fitting[:\s]+(.{0,150})",
        r"Sizing[:\s]+(.{0,150})",
    ]

    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE)

        if match:
            value = clean_text(match.group(1))

            if value:
                return value

    return None


def extract_product(page, rank, pdp_url):

    print()
    print("=" * 80)
    print(f"PRODUCT RANK: {rank}")
    print("=" * 80)

    try:
        page.goto(
            pdp_url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(3000)

    except Exception as e:
        print(f"Failed to open PDP: {e}")
        return None

    final_url = page.url

    title = clean_text(page.title())

    body = clean_text(page.locator("body").inner_text())

    # --------------------------------------------------
    # PRODUCT NAME
    # --------------------------------------------------

    product_name = None

    h1 = page.locator("h1")

    if h1.count() > 0:
        product_name = clean_text(h1.first.inner_text())

    if not product_name:
        product_name = get_meta(
            page,
            property_name="og:title"
        )

    if product_name:
        product_name = re.sub(
            r"\s*-\s*Women.*$",
            "",
            product_name,
            flags=re.IGNORECASE,
        )

    # --------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------

    description = get_meta(
        page,
        name="description"
    )

    if not description:
        description = get_meta(
            page,
            property_name="og:description"
        )

    # --------------------------------------------------
    # PRICE
    # --------------------------------------------------

    price = None
    currency = None

    # Search body text
    price_match = re.search(
        r"([£€$₹])\s*([\d,.]+)",
        body
    )

    if price_match:
        symbol = price_match.group(1)
        amount = price_match.group(2)

        price = amount

        currency_map = {
            "£": "GBP",
            "€": "EUR",
            "$": "USD",
            "₹": "INR",
        }

        currency = currency_map.get(symbol)

    # --------------------------------------------------
    # SIZE
    # --------------------------------------------------

    sizes = extract_sizes(page)

    # --------------------------------------------------
    # COLOUR
    # --------------------------------------------------

    colour = extract_colour(page)

    # --------------------------------------------------
    # CATEGORY
    # --------------------------------------------------

    category = extract_category(page)

    # --------------------------------------------------
    # IMAGE
    # --------------------------------------------------

    main_image = extract_main_image(page)

    # --------------------------------------------------
    # GENDER
    # --------------------------------------------------

    gender = "Women"

    # --------------------------------------------------
    # MATERIAL
    # --------------------------------------------------

    material = extract_material(page)

    # --------------------------------------------------
    # FIT
    # --------------------------------------------------

    fit = extract_fit(page)

    # --------------------------------------------------
    # OCCASION / TAGS
    # --------------------------------------------------

    occasion = extract_occasion(page)

    product = {
        "keyword": KEYWORD,
        "rank": rank,
        "product_name": product_name,
        "size": sizes,
        "product_description": description,
        "category": category,
        "price": price,
        "currency": currency,
        "main_product_image": main_image,
        "pdp_url": final_url,
        "colour": colour,
        "gender": gender,
        "material": material,
        "fit_sizing": fit,
        "occasion_tags": occasion,
    }

    print(f"Product Name : {product_name}")
    print(f"Size         : {sizes}")
    print(f"Description  : {description}")
    print(f"Category     : {category}")
    print(f"Price        : {currency} {price}")
    print(f"Image        : {main_image}")
    print(f"PDP URL      : {final_url}")
    print(f"Rank         : {rank}")
    print(f"Colour       : {colour}")
    print(f"Gender       : {gender}")
    print(f"Material     : {material}")
    print(f"Fit/Sizing   : {fit}")
    print(f"Occasion     : {occasion}")

    return product


def get_search_products(page):

    print()
    print("=" * 80)
    print("SEARCH PAGE")
    print("=" * 80)

    page.goto(
        SEARCH_URL,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    page.wait_for_timeout(3000)

    print("STATUS: Search page opened")
    print("FINAL URL:", page.url)
    print("TITLE:", page.title())

    links = page.locator("a")

    products = []
    seen_urls = set()

    for i in range(links.count()):

        try:
            href = links.nth(i).get_attribute("href")

            if not href:
                continue

            if "/p/women/" not in href:
                continue

            if href.startswith("/"):
                href = "https://shop.mango.com" + href

            if href in seen_urls:
                continue

            seen_urls.add(href)

            image_alt = None

            try:
                img = links.nth(i).locator("img")

                if img.count() > 0:
                    image_alt = img.first.get_attribute("alt")

            except Exception:
                pass

            products.append({
                "url": href,
                "image_alt": image_alt,
            })

        except Exception:
            continue

    return products[:TOP_N]


def main():

    print("Launching Playwright...")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 900,
            }
        )

        # --------------------------------------------------
        # SEARCH
        # --------------------------------------------------

        products = get_search_products(page)

        print()
        print("=" * 80)
        print("TOP SEARCH PRODUCTS")
        print("=" * 80)

        print(f"Products found: {len(products)}")

        for rank, product in enumerate(products, start=1):

            print()
            print(
                f"RANK {rank} | "
                f"IMAGE ALT: {product['image_alt']}"
            )

            print(
                f"PDP: {product['url']}"
            )

        # --------------------------------------------------
        # PDP SCRAPING
        # --------------------------------------------------

        results = []

        for rank, product in enumerate(products, start=1):

            result = extract_product(
                page,
                rank,
                product["url"],
            )

            if result:
                results.append(result)

            # Small delay between PDP requests
            time.sleep(2)

        # --------------------------------------------------
        # FINAL SUMMARY
        # --------------------------------------------------

        print()
        print("=" * 80)
        print("FINAL SUMMARY")
        print("=" * 80)

        print("Keyword:", KEYWORD)
        print("Products scraped:", len(results))

        print()

        for product in results:

            print(
                f"{product['rank']}. "
                f"{product['product_name']}"
            )

        browser.close()


if __name__ == "__main__":
    main()