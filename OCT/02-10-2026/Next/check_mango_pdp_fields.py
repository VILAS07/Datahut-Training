from playwright.sync_api import sync_playwright
import re
from urllib.parse import urljoin


PDP_URL = (
    "https://shop.mango.com/gb/en/p/women/"
    "dresses-and-jumpsuits/party/"
    "ruched-dress-with-draped-neckline/"
    "37006011/05/00"
)


def get_meta(page, selector):
    try:
        locator = page.locator(selector).first
        if locator.count() > 0:
            return locator.get_attribute("content")
    except Exception:
        pass

    return None


def get_text(page, selectors):
    for selector in selectors:
        try:
            locator = page.locator(selector).first

            if locator.count() > 0:
                text = locator.inner_text().strip()

                if text:
                    return text
        except Exception:
            pass

    return None


def main():

    print("Launching Playwright...\n")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 900
            }
        )

        print("Opening PDP:")
        print(PDP_URL)

        response = page.goto(
            PDP_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(3000)

        print("\n" + "=" * 80)
        print("MANGO PDP FIELD TEST")
        print("=" * 80)

        # --------------------------------------------------
        # BASIC PAGE INFORMATION
        # --------------------------------------------------

        status = response.status if response else None

        print("\nSTATUS:", status)
        print("FINAL URL:", page.url)
        print("TITLE:", page.title())

        # --------------------------------------------------
        # BODY TEXT
        # --------------------------------------------------

        body_text = page.locator("body").inner_text()

        # --------------------------------------------------
        # 1. PRODUCT NAME
        # --------------------------------------------------

        product_name = get_text(
            page,
            [
                "h1",
                "[data-testid*='product'] h1",
                "[class*='product'] h1"
            ]
        )

        if not product_name:
            product_name = get_meta(
                page,
                "meta[property='og:title']"
            )

        if product_name:
            product_name = product_name.split("|")[0].strip()

        # --------------------------------------------------
        # 2. SIZE
        # --------------------------------------------------

        sizes = []

        try:
            buttons = page.locator("button")

            for i in range(buttons.count()):

                text = buttons.nth(i).inner_text().strip()

                if re.search(
                    r"\b(EUR|UK|US)\s*(XS|S|M|L|XL|XXL|\d+)",
                    text,
                    re.I
                ):
                    sizes.append(text)

        except Exception:
            pass

        # Remove duplicates
        sizes = list(dict.fromkeys(sizes))

        # --------------------------------------------------
        # 3. PRODUCT DESCRIPTION
        # --------------------------------------------------

        description = get_meta(
            page,
            "meta[name='description']"
        )

        if not description:
            description = get_meta(
                page,
                "meta[property='og:description']"
            )

        # --------------------------------------------------
        # 4. CATEGORY / PRODUCT TYPE
        # --------------------------------------------------

        category = None

        # Try breadcrumb
        try:
            breadcrumb_text = page.locator(
                "nav"
            ).all_inner_texts()

            for text in breadcrumb_text:

                text_lower = text.lower()

                if any(
                    word in text_lower
                    for word in [
                        "dress",
                        "jeans",
                        "trousers",
                        "top",
                        "jumper",
                        "cardigan",
                        "knitwear"
                    ]
                ):
                    category = text.strip()
                    break

        except Exception:
            pass

        # Fallback from URL
        if not category:

            url_lower = page.url.lower()

            if "dress" in url_lower:
                category = "dress"

            elif "jeans" in url_lower:
                category = "jeans"

            elif "jumper" in url_lower:
                category = "jumper"

            elif "cardigan" in url_lower:
                category = "cardigan"

            elif "top" in url_lower:
                category = "top"

        # --------------------------------------------------
        # 5. PRICE
        # --------------------------------------------------

        price = None
        currency = None

        # IMPORTANT:
        # Mango does NOT necessarily use:
        # meta[name="price"]
        #
        # Try several possible locations.

        price_selectors = [
            "meta[property='product:price:amount']",
            "meta[property='og:price:amount']",
            "meta[itemprop='price']",
            "[itemprop='price']",
            "[class*='price']"
        ]

        for selector in price_selectors:

            try:

                locator = page.locator(selector).first

                if locator.count() > 0:

                    value = (
                        locator.get_attribute("content")
                        or locator.inner_text()
                    )

                    if value:

                        match = re.search(
                            r"\d+(?:[.,]\d{1,2})?",
                            value
                        )

                        if match:
                            price = match.group(0)
                            break

            except Exception:
                pass

        # Fallback: search body text
        if not price:

            match = re.search(
                r"[£€$]\s?(\d+(?:[.,]\d{1,2})?)",
                body_text
            )

            if match:
                price = match.group(1)

        # Currency
        currency = get_meta(
            page,
            "meta[property='product:price:currency']"
        )

        if not currency:

            currency = get_meta(
                page,
                "meta[name='priceCurrency']"
            )

        if not currency and "£" in body_text:
            currency = "GBP"

        # --------------------------------------------------
        # 6. MAIN PRODUCT IMAGE
        # --------------------------------------------------

        main_image = None

        # Try OpenGraph image first
        main_image = get_meta(
            page,
            "meta[property='og:image']"
        )

        # Fallback to product images
        if not main_image:

            try:

                images = page.locator("img")

                for i in range(images.count()):

                    src = images.nth(i).get_attribute("src")

                    if src and "mango.com" in src:

                        main_image = urljoin(
                            page.url,
                            src
                        )

                        break

            except Exception:
                pass

        # --------------------------------------------------
        # 7. PDP URL
        # --------------------------------------------------

        pdp_url = page.url

        # --------------------------------------------------
        # 8. RANK
        # --------------------------------------------------

        # PDP itself does not contain search ranking.
        # Rank must come from the keyword search results.

        rank = None

        # --------------------------------------------------
        # 9. COLOUR
        # --------------------------------------------------

        colour = None

        colour_match = re.search(
            r"Select a colour\s+([A-Za-z -]+)",
            body_text,
            re.I
        )

        if colour_match:
            colour = colour_match.group(1).strip()

        # --------------------------------------------------
        # 10. GENDER
        # --------------------------------------------------

        gender = None

        if re.search(r"\bWOMEN\b", body_text, re.I):
            gender = "Women"

        # --------------------------------------------------
        # 11. MATERIAL / FABRIC
        # --------------------------------------------------

        material = None

        # Search page text around composition section
        composition_match = re.search(
            r"DETAILS, COMPOSITION AND CARE(.*?)(?:STORE AVAILABILITY|YOU MAY ALSO LIKE)",
            body_text,
            re.I | re.S
        )

        if composition_match:

            composition_text = (
                composition_match.group(1).strip()
            )

            if composition_text:
                material = composition_text

        # --------------------------------------------------
        # 12. FIT / SIZING
        # --------------------------------------------------

        fit = None

        fit_keywords = [
            "oversized",
            "slim fit",
            "regular fit",
            "relaxed fit",
            "loose fit",
            "straight fit",
            "fitted"
        ]

        body_lower = body_text.lower()

        for keyword in fit_keywords:

            if keyword in body_lower:

                fit = keyword
                break

        # --------------------------------------------------
        # 13. OCCASION / STYLE TAGS
        # --------------------------------------------------

        style_tags = []

        possible_tags = [
            "party",
            "casual",
            "evening",
            "smart casual",
            "formal",
            "office",
            "summer",
            "winter",
            "wedding"
        ]

        for tag in possible_tags:

            if tag in body_lower:
                style_tags.append(tag)

        style_tags = list(dict.fromkeys(style_tags))

        # --------------------------------------------------
        # OUTPUT
        # --------------------------------------------------

        print("\n" + "=" * 80)
        print("MANGO PDP FIELD RESULTS")
        print("=" * 80)

        print("\nMUST-HAVE FIELDS")
        print("-" * 80)

        print("1. Product Name       :", product_name or "NOT FOUND")
        print("2. Size               :", sizes or "NOT FOUND")
        print("3. Product Description:", description or "NOT FOUND")
        print("4. Category           :", category or "NOT FOUND")

        if price:
            if currency:
                print(
                    "5. Price              :",
                    f"{currency} {price}"
                )
            else:
                print("5. Price              :", price)
        else:
            print("5. Price              : NOT FOUND")

        print(
            "6. Main Product Image :",
            main_image or "NOT FOUND"
        )

        print(
            "7. PDP URL            :",
            pdp_url
        )

        print(
            "8. Rank               :",
            rank or "NOT AVAILABLE ON PDP"
        )

        print("\nNICE-TO-HAVE FIELDS")
        print("-" * 80)

        print("9. Colour             :", colour or "NOT FOUND")
        print("10. Gender            :", gender or "NOT FOUND")
        print("11. Material          :", material or "NOT FOUND")
        print("12. Fit / Sizing      :", fit or "NOT FOUND")
        print(
            "13. Occasion / Tags   :",
            style_tags or "NOT FOUND"
        )

        # --------------------------------------------------
        # FIELD SUMMARY
        # --------------------------------------------------

        print("\n" + "=" * 80)
        print("FIELD AVAILABILITY SUMMARY")
        print("=" * 80)

        fields = {
            "Product Name": product_name,
            "Size": sizes,
            "Product Description": description,
            "Category/Product Type": category,
            "Price": price,
            "Main Product Image": main_image,
            "PDP URL": pdp_url,
            "Rank": rank,
            "Colour": colour,
            "Gender": gender,
            "Material": material,
            "Fit/Sizing": fit,
            "Occasion/Style Tags": style_tags,
        }

        available = 0

        for name, value in fields.items():

            if value:

                print(f"✓ {name}")
                available += 1

            else:

                print(f"✗ {name}")

        print("\nFields available:", available, "/", len(fields))

        print("\n" + "=" * 80)

        browser.close()


if __name__ == "__main__":
    main()