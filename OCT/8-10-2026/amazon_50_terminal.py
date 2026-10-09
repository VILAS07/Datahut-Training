import asyncio
import re
from pathlib import Path

from scrapy import Selector
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


BASE_DIR = Path.cwd()

STAR_FIELDS = [
    "5_star_percentage",
    "4_star_percentage",
    "3_star_percentage",
    "2_star_percentage",
    "1_star_percentage",
]


# ============================================================
# HELPERS
# ============================================================

def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def first_text(selector, css_selectors):
    for css in css_selectors:
        try:
            for node in selector.css(css):
                value = clean(node.xpath("string(.)").get())
                if value:
                    return value
        except Exception:
            pass

    return ""


def extract_summary(html, asin):
    selector = Selector(text=html)

    title = first_text(
        selector,
        [
            "#productTitle",
            '[data-hook="product-title"]',
        ],
    )

    rating_text = first_text(
        selector,
        [
            '[data-hook="rating-out-of-text"]',
            '[data-hook="average-star-rating"] .a-icon-alt',
            "#acrPopover .a-icon-alt",
        ],
    )

    rating_match = re.search(
        r"([0-5](?:\.\d+)?)\s*out of\s*5",
        rating_text,
        re.I,
    )

    average_rating = (
        float(rating_match.group(1))
        if rating_match
        else ""
    )

    total_text = first_text(
        selector,
        [
            '[data-hook="total-review-count"]',
            "#acrCustomerReviewText",
        ],
    )

    if not total_text:
        total_text = clean(
            selector.css("#acrCustomerReviewText").attrib.get(
                "aria-label", ""
            )
        )

    count_match = re.search(
        r"([\d,]+)\s*(?:global\s+)?ratings?\b",
        total_text,
        re.I,
    )

    if not count_match:
        count_match = re.search(
            r"([\d,]+)\s+reviews?\b",
            total_text,
            re.I,
        )

    total_ratings = (
        int(count_match.group(1).replace(",", ""))
        if count_match
        else ""
    )

    distribution = {field: "" for field in STAR_FIELDS}

    for node in selector.css("#histogramTable a[aria-label]"):
        label = clean(node.attrib.get("aria-label", ""))

        star_match = re.search(r"\b([1-5])\s*stars?\b", label, re.I)
        percentage_match = re.search(
            r"([\d.]+)\s*(?:percent|%)",
            label,
            re.I,
        )

        if star_match and percentage_match:
            star = int(star_match.group(1))
            percentage = float(percentage_match.group(1))
            distribution[f"{star}_star_percentage"] = percentage

    return {
        "asin": asin,
        "title": title,
        "average_rating": average_rating,
        "total_ratings": total_ratings,
        **distribution,
    }


# ============================================================
# PRODUCT CLASSIFICATION
# ============================================================

def classify_product(title):
    """
    Classification is based on the listing title.
    Ambiguous titles are marked as unconfirmed.
    """

    t = title.lower()

    if not t:
        return "UNKNOWN — product title unavailable"

    accessory_terms = [
        "holder",
        "keychain",
        "key chain",
        "key ring",
        "keyring",
        "case",
        "protector",
        "protective cover",
        "cover",
        "mount",
        "carabiner",
        "wallet",
        "loop",
        "strap",
        "sleeve",
        "skin",
        "adhesive",
        "sticker",
        "replacement",
        "compatible with",
        "compatible for",
        "accessory",
        "accessories",
    ]

    # Accessories must be classified before checking generation.
    if any(term in t for term in accessory_terms):
        return "ACCESSORY — NOT the AirTag device"

    third_party_brands = [
        "ugreen",
        "chipolo",
        "pebblebee",
        "tile tracker",
        "eufy",
        "samsung smarttag",
    ]

    if any(brand in t for brand in third_party_brands):
        return "THIRD-PARTY TRACKER — NOT Apple AirTag"

    mentions_airtag = "airtag" in t or "air tag" in t
    says_apple = "apple" in t

    second_gen_patterns = [
        r"2nd\s+generation",
        r"second\s+generation",
        r"2nd\s+gen\b",
        r"gen\s*2\b",
        r"\bairtag\s*2\b",
    ]

    explicit_second_gen = any(
        re.search(pattern, t, re.I)
        for pattern in second_gen_patterns
    )

    if mentions_airtag and says_apple and explicit_second_gen:
        return "MATCH — Apple AirTag (2nd Generation)"

    if mentions_airtag and says_apple:
        return "APPLE AIRTAG DEVICE — generation unconfirmed"

    if mentions_airtag:
        return "AIRTag MENTIONED — device/generation unconfirmed"

    return "NOT CONFIRMED as an Apple AirTag"


# ============================================================
# INDIVIDUAL REVIEW EXTRACTION
# ============================================================

def extract_reviews(html, asin):
    selector = Selector(text=html)

    cards = selector.xpath('//*[@data-hook="review"]')

    if not cards:
        cards = selector.xpath('//*[@data-review-id]')

    reviews = []

    for card in cards:
        review_id = clean(
            card.attrib.get("data-review-id", "")
            or card.attrib.get("id", "")
        )

        review_id = re.sub(
            r"^customer_review-",
            "",
            review_id,
        )

        title = first_text(
            card,
            [
                '[data-hook="reviewTitle"]',
                '[data-hook="review-title"] span',
                '[data-hook="review-title"]',
            ],
        )

        title = re.sub(
            r"^\s*[1-5](?:\.\d+)?\s*out of\s*5 stars\s*",
            "",
            title,
            flags=re.I,
        ).strip()

        rating_text = first_text(
            card,
            [
                '[data-hook="review-star-rating"]',
                '[data-hook="cmps-review-star-rating"]',
                'i.review-rating span.a-icon-alt',
            ],
        )

        rating_match = re.search(
            r"([1-5](?:\.\d+)?)\s*out of\s*5",
            rating_text,
            re.I,
        )

        rating = (
            float(rating_match.group(1))
            if rating_match
            else ""
        )

        raw_date = first_text(
            card,
            ['[data-hook="review-date"]'],
        )

        review_date = raw_date

        date_match = re.search(r"\bon\s+(.+)$", raw_date, re.I)
        if date_match:
            review_date = clean(date_match.group(1))

        review_text = first_text(
            card,
            [
                '[data-hook="reviewText"]',
                '[data-hook="review-body"]',
                '[data-hook="reviewTextContainer"]',
            ],
        )

        # Remove accessibility instructions and duplicated UI labels.
        for phrase in [
            "Brief content visible, double tap to read full content.",
            "Full content visible, double tap to read brief content.",
        ]:
            review_text = review_text.replace(phrase, "")

        review_text = re.sub(
            r"\s*Read more\s*Read less\s*$",
            "",
            review_text,
            flags=re.I,
        )

        review_text = clean(review_text)

        card_text = clean(card.xpath("string(.)").get())

        verified = (
            "Yes"
            if "verified purchase" in card_text.lower()
            else "No badge shown"
        )

        # Never extract reviewer names.
        if not (review_id or title or review_text):
            continue

        reviews.append({
            "asin": asin,
            "review_id": review_id,
            "rating": rating,
            "date": review_date,
            "verified_purchase": verified,
            "title": title,
            "text": review_text,
        })

    return reviews, len(cards)


# ============================================================
# ACCESS RESTRICTION CHECK
# ============================================================

def restriction_detected(url, body, status):
    url = url.lower()
    body = body.lower()

    if "/ap/signin" in url or "validatecaptcha" in url:
        return True

    if status in (403, 429, 503):
        return True

    restricted_phrases = [
        "we limit review access when we detect unusual activity",
        "unusual activity on an account",
        "enter the characters you see below",
        "sorry, we just need to make sure you're not a robot",
    ]

    return any(phrase in body for phrase in restricted_phrases)


# ============================================================
# MAIN
# ============================================================

async def main():
    product_files = sorted(
        path for path in BASE_DIR.glob("product_*.html")
        if re.fullmatch(
            r"product_([A-Z0-9]{10})\.html",
            path.name,
            re.I,
        )
    )

    if not product_files:
        print("ERROR: No product_<ASIN>.html files found.")
        return

    # Load the saved pages first, so classifications are printed
    # even if Amazon later restricts live page access.
    products = []

    print("\n" + "=" * 90)
    print("AMAZON AIR TAG PRODUCT CLASSIFICATION")
    print("=" * 90)

    for path in product_files:
        match = re.fullmatch(
            r"product_([A-Z0-9]{10})\.html",
            path.name,
            re.I,
        )

        asin = match.group(1).upper()
        html = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        summary = extract_summary(html, asin)
        category = classify_product(summary["title"])

        products.append({
            "asin": asin,
            "path": path,
            "saved_summary": summary,
            "category": category,
        })

        print(f"\n{len(products):02d}. ASIN: {asin}")
        print(f"    Product: {summary['title'] or 'TITLE NOT FOUND'}")
        print(f"    Classification: {category}")

    actual_gen2 = sum(
        product["category"].startswith("MATCH —")
        for product in products
    )

    print("\n" + "-" * 90)
    print(f"Total product pages: {len(products)}")
    print(f"Confirmed Gen 2 by title: {actual_gen2}")
    print("-" * 90)

    print("\nStarting one-pass live extraction.")
    print("Output goes to the terminal; no CSV/JSON files are created.\n")

    total_reviews = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(locale="en-US")
        page.set_default_navigation_timeout(45000)

        try:
            for index, product in enumerate(products, start=1):
                asin = product["asin"]
                saved = product["saved_summary"]

                print("\n" + "=" * 90)
                print(f"PRODUCT {index}/{len(products)} — {asin}")
                print("=" * 90)

                url = f"https://www.amazon.com/dp/{asin}"

                try:
                    response = await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=45000,
                    )

                    await page.wait_for_timeout(1500)

                    status = response.status if response else 0
                    html = await page.content()
                    body = await page.locator("body").inner_text(
                        timeout=5000
                    )

                    if restriction_detected(page.url, body, status):
                        print(
                            "Amazon access restriction/sign-in/CAPTCHA "
                            "detected. Stopping live extraction."
                        )
                        print("Saved-page classifications are above.")
                        break

                    live = extract_summary(html, asin)

                    title = live["title"] or saved["title"]
                    category = classify_product(title)

                    # Ask the browser to load the page's review section
                    # through normal scrolling.
                    try:
                        await page.locator(
                            "#customerReviews"
                        ).scroll_into_view_if_needed(timeout=10000)
                    except PlaywrightTimeoutError:
                        pass

                    await page.wait_for_timeout(2500)

                    html = await page.content()
                    body = await page.locator("body").inner_text(
                        timeout=5000
                    )

                    if restriction_detected(
                        page.url,
                        body,
                        status,
                    ):
                        print(
                            "Restriction detected while loading reviews. "
                            "Stopping without attempting to bypass it."
                        )
                        break

                    # Use any summary fields that were actually found.
                    live = extract_summary(html, asin)

                    print(f"Product name: {title or 'Not found'}")
                    print(f"Classification: {category}")
                    print(f"HTTP status: {status}")
                    print(
                        "Average rating: "
                        f"{live['average_rating'] or saved['average_rating'] or 'Not found'}"
                    )
                    print(
                        "Total ratings: "
                        f"{live['total_ratings'] or saved['total_ratings'] or 'Not found'}"
                    )

                    print("\nStar distribution:")
                    for field in STAR_FIELDS:
                        value = (
                            live.get(field)
                            if live.get(field) != ""
                            else saved.get(field, "")
                        )

                        label = field.replace("_percentage", "").replace(
                            "_", " "
                        )

                        print(
                            f"  {label}: "
                            f"{str(value) + '%' if value != '' else 'Not found'}"
                        )

                    reviews, card_count = extract_reviews(html, asin)

                    print(f"\nReview cards found: {card_count}")
                    print(f"Review records extracted: {len(reviews)}")

                    for review_number, review in enumerate(
                        reviews,
                        start=1,
                    ):
                        print("\n" + "." * 75)
                        print(f"REVIEW {review_number}")
                        print(f"ASIN: {review['asin']}")
                        print(f"Review ID: {review['review_id'] or 'Not shown'}")
                        print(f"Rating: {review['rating'] or 'Not shown'}")
                        print(f"Date: {review['date'] or 'Not shown'}")
                        print(
                            "Verified purchase: "
                            f"{review['verified_purchase']}"
                        )
                        print(f"Title: {review['title'] or 'Not shown'}")
                        print(f"Text: {review['text'] or 'Not shown'}")

                    total_reviews += len(reviews)

                except Exception as exc:
                    print(
                        f"Could not process this page: "
                        f"{type(exc).__name__}: {exc}"
                    )

                await page.wait_for_timeout(1200)

        finally:
            await browser.close()

    print("\n" + "=" * 90)
    print("FINAL TERMINAL SUMMARY")
    print("=" * 90)
    print(f"Product pages discovered: {len(products)}")
    print(f"Confirmed Gen 2 based on product title: {actual_gen2}")
    print(f"Review records printed: {total_reviews}")
    print("No CSV or JSON files were created.")


if __name__ == "__main__":
    asyncio.run(main())