import asyncio
import json
from playwright.async_api import async_playwright


PRODUCT_URL = (
    "https://shop.mango.com/gb/en/p/women/dresses-and-jumpsuits/"
    "party/ruched-dress-with-draped-neckline/37006011/05/00"
)


async def scrape_product(page, url):
    print(f"\nOpening PDP:\n{url}\n")

    await page.goto(url, wait_until="domcontentloaded", timeout=120000)
    await page.wait_for_timeout(5000)

    # -----------------------------
    # Product name
    # -----------------------------
    product_name = await page.locator("h1").first.text_content()
    product_name = product_name.strip() if product_name else None

    # -----------------------------
    # Product URL
    # -----------------------------
    product_url = page.url

    # -----------------------------
    # Price
    # -----------------------------
    price = None

    price_meta = page.locator('meta[property="product:price:amount"]')

    if await price_meta.count():
        price = await price_meta.first.get_attribute("content")

    if not price:
        price_text = await page.locator("body").inner_text()

        import re

        price_match = re.search(
            r"(?:£|€|\$)\s*([\d,.]+)",
            price_text
        )

        if price_match:
            price = price_match.group(1)

    if price:
        try:
            price = float(price.replace(",", ""))
        except ValueError:
            pass

    # -----------------------------
    # Currency
    # -----------------------------
    currency = None

    currency_meta = page.locator(
        'meta[property="product:price:currency"]'
    )

    if await currency_meta.count():
        currency = await currency_meta.first.get_attribute("content")

    if not currency:
        currency = "GBP"

    # -----------------------------
    # Description
    # -----------------------------
    description = None

    description_meta = page.locator(
        'meta[name="description"]'
    )

    if await description_meta.count():
        description = await description_meta.first.get_attribute(
            "content"
        )

    # -----------------------------
    # Color
    # -----------------------------
    color = None

    body_text = await page.locator("body").inner_text()

    color_match = None

    import re

    color_match = re.search(
        r"Select a colour\s+([^\n]+)",
        body_text
    )

    if color_match:
        color = color_match.group(1).strip()

    # -----------------------------
    # Sizes
    # -----------------------------
    sizes = []

    size_buttons = page.locator("button")

    for i in range(await size_buttons.count()):
        button = size_buttons.nth(i)

        try:
            text = await button.inner_text()
            text = text.strip()

            if re.match(
                r"^\d+\s+EUR\s+(XS|S|M|L|XL|XXL|XXXL)$",
                text
            ):
                sizes.append(text)

        except Exception:
            continue

    # Remove duplicates
    sizes = list(dict.fromkeys(sizes))

    # -----------------------------
    # Availability
    # -----------------------------
    availability = None

    availability_keywords = [
        "LAST FEW ITEMS!",
        "NOT AVAILABLE.",
        "IN STOCK",
        "OUT OF STOCK",
        "AVAILABLE"
    ]

    for keyword in availability_keywords:
        if keyword in body_text:
            availability = keyword
            break

    # -----------------------------
    # Product images
    # -----------------------------
    images = []

    image_elements = page.locator("img")

    for i in range(await image_elements.count()):
        image = image_elements.nth(i)

        try:
            src = await image.get_attribute("src")
            alt = await image.get_attribute("alt")

            if src and "media.mango.com" in src:
                images.append(
                    {
                        "url": src,
                        "alt": alt
                    }
                )

        except Exception:
            continue

    # Remove duplicate image URLs
    unique_images = []
    seen_urls = set()

    for image in images:
        if image["url"] not in seen_urls:
            unique_images.append(image)
            seen_urls.add(image["url"])

    images = unique_images

    # -----------------------------
    # Category
    # -----------------------------
    category = []

    category_parts = [
        "WOMEN",
        "DRESSES AND JUMPSUITS",
        "PARTY"
    ]

    for item in category_parts:
        if item in body_text.upper():
            category.append(item)

    # -----------------------------
    # Final product dictionary
    # -----------------------------
    product = {
        "product_name": product_name,
        "product_url": product_url,
        "price": price,
        "currency": currency,
        "description": description,
        "color": color,
        "sizes": sizes,
        "availability": availability,
        "images": images,
        "category": category,
    }

    return product


async def main():
    print("Launching Playwright...")

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page(
            viewport={
                "width": 1920,
                "height": 1080
            }
        )

        try:
            product = await scrape_product(
                page,
                PRODUCT_URL
            )

            print("\n")
            print("=" * 70)
            print("SCRAPED PRODUCT")
            print("=" * 70)

            print(
                json.dumps(
                    product,
                    indent=4,
                    ensure_ascii=False
                )
            )

            print("=" * 70)
            print("SCRAPING COMPLETE")
            print("=" * 70)

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())