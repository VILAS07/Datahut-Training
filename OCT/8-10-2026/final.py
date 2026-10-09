import asyncio
import csv
import json
import re
from pathlib import Path

from scrapy import Selector
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


BASE_DIR = Path.cwd()

PRODUCT_CSV = BASE_DIR / "amazon_products_final.csv"
PRODUCT_JSON = BASE_DIR / "amazon_products_final.json"
REVIEWS_CSV = BASE_DIR / "amazon_reviews_final.csv"
REVIEWS_JSON = BASE_DIR / "amazon_reviews_final.json"

STAR_FIELDS = [
    "5_star_percentage",
    "4_star_percentage",
    "3_star_percentage",
    "2_star_percentage",
    "1_star_percentage",
]

PRODUCT_FIELDS = [
    "asin",
    "product_name",
    "average_rating",
    "total_ratings",
    *STAR_FIELDS,
    "product_url",
    "source_file",
    "fetch_status",
    "review_cards_found",
]

REVIEW_FIELDS = [
    "asin",
    "product_name",
    "review_id",
    "rating",
    "review_date",
    "review_title",
    "review_text",
    "verified_purchase",
    "source_file",
]


def clean(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


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


def first_attribute(selector, css, attribute):
    try:
        return clean(selector.css(css).attrib.get(attribute, ""))
    except Exception:
        return ""


def extract_product_summary(html, asin, source_file):
    selector = Selector(text=html)

    product_name = first_text(
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
            "#averageCustomerReviews .a-icon-alt",
        ],
    )

    average_rating = ""
    match = re.search(
        r"([0-5](?:\.\d+)?)\s*out of\s*5",
        rating_text,
        re.I,
    )
    if match:
        average_rating = float(match.group(1))

    total_text = first_text(
        selector,
        [
            '[data-hook="total-review-count"]',
            "#acrCustomerReviewText",
        ],
    )

    if not total_text:
        total_text = first_attribute(
            selector,
            "#acrCustomerReviewText",
            "aria-label",
        )

    total_ratings = ""
    match = re.search(
        r"([\d,]+)\s*(?:global\s+)?ratings?\b",
        total_text,
        re.I,
    )

    if match:
        total_ratings = int(match.group(1).replace(",", ""))
    else:
        match = re.fullmatch(r"\s*\(?\s*([\d,]+)\s*\)?\s*", total_text)
        if match:
            total_ratings = int(match.group(1).replace(",", ""))

    distribution = {field: "" for field in STAR_FIELDS}

    for node in selector.css("#histogramTable a[aria-label]"):
        label = clean(node.attrib.get("aria-label", ""))

        star_match = re.search(r"\b([1-5])\s*stars?\b", label, re.I)
        percent_match = re.search(
            r"([\d.]+)\s*percent\b",
            label,
            re.I,
        )

        if star_match and percent_match:
            star = int(star_match.group(1))
            percentage = float(percent_match.group(1))
            distribution[f"{star}_star_percentage"] = percentage

    return {
        "asin": asin,
        "product_name": product_name,
        "average_rating": average_rating,
        "total_ratings": total_ratings,
        **distribution,
        "product_url": f"https://www.amazon.com/dp/{asin}",
        "source_file": source_file,
        "fetch_status": "not_attempted",
        "review_cards_found": 0,
    }


def extract_reviews(html, asin, product_name, source_file):
    selector = Selector(text=html)

    # Standard Amazon review cards.
    cards = selector.xpath('//*[@data-hook="review"]')

    if not cards:
        cards = selector.xpath('//*[@data-review-id]')

    results = []

    for card in cards:
        card_id = clean(
            card.attrib.get("id", "")
            or card.attrib.get("data-review-id", "")
        )

        review_id = re.sub(r"^customer_review-", "", card_id)

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

        rating = ""
        match = re.search(
            r"([1-5](?:\.\d+)?)\s*out of\s*5",
            rating_text,
            re.I,
        )
        if match:
            rating = float(match.group(1))

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

        full_card_text = clean(card.xpath("string(.)").get())
        verified = (
            "Yes"
            if "verified purchase" in full_card_text.lower()
            else "No"
        )

        # Do not collect reviewer names.
        if not (review_id or title or review_text):
            continue

        results.append({
            "asin": asin,
            "product_name": product_name,
            "review_id": review_id,
            "rating": rating,
            "review_date": review_date,
            "review_title": title,
            "review_text": review_text,
            "verified_purchase": verified,
            "source_file": source_file,
        })

    return results, len(cards)


def access_restricted(url, body_text):
    url = url.lower()
    body = body_text.lower()

    if "/ap/signin" in url or "validatecaptcha" in url:
        return True

    phrases = [
        "we limit review access when we detect unusual activity",
        "unusual activity on an account",
        "enter the characters you see below",
    ]

    return any(phrase in body for phrase in phrases)


def save_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def save_json(path, rows):
    with path.open("w", encoding="utf-8") as file:
        json.dump(rows, file, indent=2, ensure_ascii=False)


def save_outputs(products, reviews):
    save_csv(PRODUCT_CSV, products, PRODUCT_FIELDS)
    save_json(PRODUCT_JSON, products)

    save_csv(REVIEWS_CSV, reviews, REVIEW_FIELDS)
    save_json(REVIEWS_JSON, reviews)


def review_key(review):
    if review.get("review_id"):
        return review.get("asin", ""), review["review_id"]

    return (
        review.get("asin", ""),
        review.get("review_date", ""),
        review.get("rating", ""),
        review.get("review_title", ""),
        review.get("review_text", ""),
    )


async def main():
    # Find only product_<10-character-ASIN>.html files.
    product_files = sorted(
        path
        for path in BASE_DIR.glob("product_*.html")
        if re.fullmatch(
            r"product_([A-Z0-9]{10})\.html",
            path.name,
            re.I,
        )
    )

    if not product_files:
        print("ERROR: No product_<ASIN>.html files found.")
        return

    # Build summaries from all saved pages first.
    products = []
    product_by_asin = {}

    for path in product_files:
        match = re.fullmatch(
            r"product_([A-Z0-9]{10})\.html",
            path.name,
            re.I,
        )
        asin = match.group(1).upper()

        html = path.read_text(encoding="utf-8", errors="replace")
        row = extract_product_summary(html, asin, path.name)

        products.append(row)
        product_by_asin[asin] = row

    asins = [row["asin"] for row in products]
    print(f"Found {len(asins)} saved products.")
    print("Product summaries extracted locally.")

    # Reuse existing review rows only when their ASIN matches this catalog.
    reviews = []
    seen = set()

    old_reviews_file = BASE_DIR / "amazon_reviews_from_saved_html.json"

    if old_reviews_file.exists():
        try:
            old_reviews = json.loads(
                old_reviews_file.read_text(encoding="utf-8")
            )

            for review in old_reviews:
                if review.get("asin") not in product_by_asin:
                    continue

                key = review_key(review)
                if key not in seen:
                    seen.add(key)
                    reviews.append(review)
        except Exception as exc:
            print(f"Could not import existing review rows: {exc}")

    # Save all locally available product data before browser work begins.
    save_outputs(products, reviews)

    async with async_playwright() as playwright:
        # Standard Chromium browser; no stealth or CAPTCHA bypass.
        browser = await playwright.chromium.launch(headless=False)
        page = await browser.new_page(locale="en-US")
        page.set_default_navigation_timeout(45000)

        stopped_for_restriction = False

        try:
            for index, asin in enumerate(asins, start=1):
                row = product_by_asin[asin]
                url = f"https://www.amazon.com/dp/{asin}"

                print(f"\n[{index}/{len(asins)}] {asin}")

                try:
                    response = await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=45000,
                    )

                    await page.wait_for_timeout(1500)
                    html = await page.content()
                    body = await page.locator("body").inner_text(
                        timeout=5000
                    )

                    if access_restricted(page.url, body):
                        row["fetch_status"] = "stopped_access_restriction"
                        stopped_for_restriction = True
                        print(
                            "Amazon sign-in/CAPTCHA/access restriction "
                            "detected. Stopping live requests."
                        )
                        save_outputs(products, reviews)
                        break

                    # Refresh product summary from the live page.
                    live_row = extract_product_summary(
                        html,
                        asin,
                        row["source_file"],
                    )

                    for field in [
                        "product_name",
                        "average_rating",
                        "total_ratings",
                        *STAR_FIELDS,
                    ]:
                        if live_row.get(field) != "":
                            row[field] = live_row[field]

                    row["fetch_status"] = (
                        f"http_{response.status}"
                        if response is not None
                        else "page_loaded"
                    )

                    # Trigger the product page's lazy-loaded review widget
                    # through normal scrolling.
                    try:
                        await page.locator(
                            "#customerReviews"
                        ).scroll_into_view_if_needed(timeout=10000)
                    except PlaywrightTimeoutError:
                        pass

                    await page.wait_for_timeout(2500)

                    try:
                        await page.wait_for_function(
                            """() =>
                                document.querySelectorAll(
                                    '[data-hook="review"], [data-review-id]'
                                ).length > 0
                            """,
                            timeout=5000,
                        )
                    except PlaywrightTimeoutError:
                        pass

                    html = await page.content()
                    body = await page.locator("body").inner_text(
                        timeout=5000
                    )

                    if access_restricted(page.url, body):
                        row["fetch_status"] = "stopped_access_restriction"
                        stopped_for_restriction = True
                        print(
                            "Restriction appeared while loading reviews. "
                            "Stopping; no retry or bypass."
                        )
                        save_outputs(products, reviews)
                        break

                    # Parse summary again in case the widget added fields.
                    live_row = extract_product_summary(
                        html,
                        asin,
                        row["source_file"],
                    )

                    for field in [
                        "product_name",
                        "average_rating",
                        "total_ratings",
                        *STAR_FIELDS,
                    ]:
                        if live_row.get(field) != "":
                            row[field] = live_row[field]

                    new_reviews, card_count = extract_reviews(
                        html,
                        asin,
                        row.get("product_name", ""),
                        f"live_product_page_{asin}",
                    )

                    row["review_cards_found"] = card_count

                    added = 0
                    for review in new_reviews:
                        key = review_key(review)

                        if key not in seen:
                            seen.add(key)
                            reviews.append(review)
                            added += 1

                    row["fetch_status"] = (
                        f"loaded_{card_count}_review_cards"
                    )

                    print(
                        f"Rating: {row['average_rating'] or 'not found'} | "
                        f"Total ratings: {row['total_ratings'] or 'not found'}"
                    )
                    print(
                        f"Review cards on page: {card_count} | "
                        f"New review rows: {added}"
                    )

                except Exception as exc:
                    row["fetch_status"] = (
                        f"navigation_error: {type(exc).__name__}"
                    )
                    print(f"Page failed: {type(exc).__name__}: {exc}")

                # Save progress after every product, so interrupted work
                # does not erase results already collected.
                save_outputs(products, reviews)

                # Gentle pacing between product pages.
                await page.wait_for_timeout(1200)

        finally:
            await browser.close()

        if stopped_for_restriction:
            print(
                "\nLive processing stopped because Amazon indicated a "
                "restriction. Existing local product summaries were saved."
            )

    save_outputs(products, reviews)

    print("\n" + "=" * 65)
    print("FINISHED")
    print("=" * 65)
    print(f"Products in output: {len(products)}")
    print(f"Individual review rows: {len(reviews)}")
    print(f"Products CSV: {PRODUCT_CSV.name}")
    print(f"Products JSON: {PRODUCT_JSON.name}")
    print(f"Reviews CSV: {REVIEWS_CSV.name}")
    print(f"Reviews JSON: {REVIEWS_JSON.name}")


if __name__ == "__main__":
    asyncio.run(main())