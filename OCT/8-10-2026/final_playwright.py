#!/usr/bin/env python3

"""
Amazon Product and Review Scraper
=================================

Browser navigation : Playwright + Chromium
HTML extraction    : Scrapy Selector + XPath
Output             : JSON and CSV

Live mode:
    Opens the known product and its first reviews page using
    normal browser navigation.

Offline mode:
    Parses previously saved HTML files without network requests.

No BeautifulSoup, proxy rotation, session-cookie injection,
or CAPTCHA/access-restriction bypasses.
"""

import argparse
import asyncio
import csv
import json
import re
import sys
from pathlib import Path

from scrapy import Selector
from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://www.amazon.com"

TARGET_ASIN = "B0GJTFXNRX"

TARGET_PRODUCT_NAME = (
    "Apple AirTag (2nd Generation): Tracker for Keychain, "
    "Wallet, and More; Locator with Sound; Simple One-Tap "
    "Setup with iPhone or iPad; Key Finder with up to "
    "1.5X Precision Finding Range"
)

PRODUCT_HTML = Path("amazon_airtag.html")
REVIEWS_HTML = Path("amazon_customer_reviews.html")

JSON_OUTPUT = Path("amazon_reviews.json")
CSV_OUTPUT = Path("amazon_reviews.csv")

TIMEOUT_MS = 45000


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(value):
    """Normalize whitespace in a string."""
    return re.sub(r"\s+", " ", value or "").strip()


def joined_text(selector, xpath):
    """Extract text nodes using Scrapy XPath."""
    values = selector.xpath(xpath).getall()
    return clean_text(" ".join(values))


def normalize_title(value):
    """Normalize a title for comparison."""
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        (value or "").lower(),
    ).strip()


# ============================================================
# ACCESS CHECKS
# ============================================================

def check_access(status, html, url):
    """
    Detect HTTP errors and common access-restriction pages.

    The runner stops on a restriction instead of attempting
    to bypass it.
    """

    if status in (403, 429, 503):
        raise RuntimeError(
            f"HTTP {status} received from {url}. "
            "The runner stopped without retrying or bypassing "
            "the restriction."
        )

    if status is not None and status >= 400:
        raise RuntimeError(
            f"HTTP {status} received from {url}."
        )

    page = Selector(
        text=html,
        type="html",
    )

    body_text = joined_text(
        page,
        "//body//text()",
    ).lower()

    restriction_phrases = [
        "we limit review access when we detect unusual activity",
        "sorry, we just need to make sure you're not a robot",
        "enter the characters you see below",
        "access denied",
    ]

    for phrase in restriction_phrases:
        if phrase in body_text:
            raise RuntimeError(
                "Amazon returned an access-restriction or "
                "verification page. The runner has stopped."
            )

    captcha = page.xpath(
        '//*[@id="captchacharacters"]'
        ' | //*[@name="cvf_captcha_input"]'
    )

    if captcha or "validatecaptcha" in url.lower():
        raise RuntimeError(
            "Amazon returned a CAPTCHA page. "
            "The runner has stopped."
        )


# ============================================================
# PRODUCT EXTRACTION
# ============================================================

def parse_product(
    html,
    asin,
    product_url,
    fallback_name=None,
):
    """Extract product details using Scrapy and XPath."""

    page = Selector(
        text=html,
        type="html",
    )

    # Product title
    product_name = joined_text(
        page,
        '//*[@id="productTitle"]//text()',
    )

    if not product_name:
        product_name = fallback_name

    # Average rating
    rating_text = clean_text(
        page.xpath(
            '//*[@id="acrPopover"]/@title'
        ).get()
    )

    if not rating_text:
        rating_text = joined_text(
            page,
            '//*[@id="acrPopover"]'
            '//*[contains(@class, "a-icon-alt")]/text()',
        )

    rating_match = re.search(
        r"(\d+(?:\.\d+)?)",
        rating_text,
    )

    average_rating = (
        float(rating_match.group(1))
        if rating_match
        else None
    )

    # Total ratings
    total_ratings_text = joined_text(
        page,
        '//*[@id="acrCustomerReviewText"]//text()',
    )

    total_match = re.search(
        r"([\d,]+)",
        total_ratings_text,
    )

    total_ratings = (
        int(total_match.group(1).replace(",", ""))
        if total_match
        else None
    )

    # Star distribution
    star_distribution = {}

    rows = page.xpath(
        '//*[@id="histogramTable"]//tr'
    )

    for row in rows:
        row_text = joined_text(
            row,
            ".//text()",
        )

        star_match = re.search(
            r"\b([1-5])\s*stars?\b",
            row_text,
            flags=re.IGNORECASE,
        )

        percentage_match = re.search(
            r"\b(\d{1,3})\s*%",
            row_text,
        )

        if star_match and percentage_match:
            star = star_match.group(1)

            star_distribution[
                f"{star}_star_percent"
            ] = int(percentage_match.group(1))

    return {
        "asin": asin,
        "name": product_name or None,
        "url": product_url,
        "average_rating": average_rating,
        "rating_text": rating_text or None,
        "total_ratings": total_ratings,
        "total_ratings_text": total_ratings_text or None,
        "star_distribution": star_distribution,
    }


# ============================================================
# REVIEW EXTRACTION
# ============================================================

def parse_review(card):
    """Extract one review card using XPath."""

    # Review ID
    review_id = clean_text(
        card.xpath("./@id").get()
    )

    # Review rating
    rating_text = joined_text(
        card,
        './/*[@data-hook="review-star-rating"]'
        '//span[contains(@class, "a-icon-alt")]/text()',
    )

    rating_match = re.search(
        r"(\d+(?:\.\d+)?)",
        rating_text,
    )

    rating = (
        float(rating_match.group(1))
        if rating_match
        else None
    )

    # Review title
    review_title = joined_text(
        card,
        './/a[@data-hook="review-title"]'
        '/span[normalize-space()]//text()',
    )

    # Review date label
    date_label = joined_text(
        card,
        './/*[@data-hook="review-date"]//text()',
    )

    # Date after "on", when present
    date_match = re.search(
        r"\bon\s+(.+)$",
        date_label,
        flags=re.IGNORECASE,
    )

    review_date = (
        clean_text(date_match.group(1))
        if date_match
        else date_label
    )

    # Review body
    review_text = joined_text(
        card,
        './/*[@data-hook="review-body"]//text()',
    )

    # Verified Purchase
    badge_text = joined_text(
        card,
        './/*[@data-hook="avp-badge"]//text()',
    )

    verified_purchase = (
        "verified purchase" in badge_text.lower()
    )

    # Reviewer names are deliberately not collected.
    return {
        "review_id": review_id or None,
        "rating": rating,
        "rating_text": rating_text or None,
        "review_title": review_title or None,
        "review_date": review_date or None,
        "review_date_label": date_label or None,
        "verified_purchase": verified_purchase,
        "review_text": review_text or None,
    }


def parse_reviews(html):
    """Extract all review cards present in the supplied HTML."""

    page = Selector(
        text=html,
        type="html",
    )

    cards = page.xpath(
        '//*[@data-hook="review"]'
    )

    if not cards:
        raise RuntimeError(
            "No review cards were found in the HTML. "
            "The response may not contain accessible reviews."
        )

    reviews = []
    seen_ids = set()

    for card in cards:
        review = parse_review(card)
        review_id = review["review_id"]

        # Remove duplicate IDs within this page.
        if review_id and review_id in seen_ids:
            continue

        if review_id:
            seen_ids.add(review_id)

        reviews.append(review)

    return reviews


# ============================================================
# OUTPUT: JSON AND CSV
# ============================================================

def save_outputs(product, reviews):
    """Save product and review data to JSON and CSV."""

    data = {
        "product": product,
        "review_count": len(reviews),
        "reviews": reviews,
    }

    JSON_OUTPUT.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    csv_columns = [
        "product_asin",
        "product_name",
        "product_url",
        "average_rating",
        "total_ratings",
        "one_star_percent",
        "two_star_percent",
        "three_star_percent",
        "four_star_percent",
        "five_star_percent",
        "review_id",
        "rating",
        "rating_text",
        "review_title",
        "review_date",
        "review_date_label",
        "verified_purchase",
        "review_text",
    ]

    distribution = product.get(
        "star_distribution",
        {},
    )

    star_column_names = {
        1: "one_star_percent",
        2: "two_star_percent",
        3: "three_star_percent",
        4: "four_star_percent",
        5: "five_star_percent",
    }

    with CSV_OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=csv_columns,
        )

        writer.writeheader()

        for review in reviews:
            row = {
                "product_asin": product.get("asin"),
                "product_name": product.get("name"),
                "product_url": product.get("url"),
                "average_rating": product.get("average_rating"),
                "total_ratings": product.get("total_ratings"),
                "review_id": review.get("review_id"),
                "rating": review.get("rating"),
                "rating_text": review.get("rating_text"),
                "review_title": review.get("review_title"),
                "review_date": review.get("review_date"),
                "review_date_label": review.get("review_date_label"),
                "verified_purchase": review.get("verified_purchase"),
                "review_text": review.get("review_text"),
            }

            for star in range(1, 6):
                column = star_column_names[star]

                row[column] = distribution.get(
                    f"{star}_star_percent"
                )

            writer.writerow(row)

    print(f"JSON saved: {JSON_OUTPUT}")
    print(f"CSV saved:  {CSV_OUTPUT}")


# ============================================================
# SUMMARY
# ============================================================

def print_summary(product, reviews):
    """Print a summary of the extracted data."""

    unique_ids = {
        review["review_id"]
        for review in reviews
        if review.get("review_id")
    }

    print("\n" + "=" * 55)
    print("SCRAPER RESULTS")
    print("=" * 55)

    print(f"Product: {product.get('name')}")
    print(f"ASIN: {product.get('asin')}")
    print(f"Product URL: {product.get('url')}")
    print(f"Average rating: {product.get('average_rating')}")
    print(f"Total ratings: {product.get('total_ratings')}")
    print(
        f"Star distribution: "
        f"{product.get('star_distribution')}"
    )

    print(f"Review cards parsed: {len(reviews)}")
    print(f"Unique review IDs: {len(unique_ids)}")

    print(
        "Reviews with ratings:",
        sum(r.get("rating") is not None for r in reviews),
    )

    print(
        "Reviews with dates:",
        sum(bool(r.get("review_date")) for r in reviews),
    )

    print(
        "Reviews with text:",
        sum(bool(r.get("review_text")) for r in reviews),
    )

    print(
        "Verified purchases:",
        sum(bool(r.get("verified_purchase")) for r in reviews),
    )

    print(f"JSON: {JSON_OUTPUT}")
    print(f"CSV:  {CSV_OUTPUT}")
    print("=" * 55)


# ============================================================
# OFFLINE MODE
# ============================================================

def run_offline():
    """Parse the existing saved HTML files without network access."""

    print("MODE: OFFLINE — no network requests")

    if not PRODUCT_HTML.is_file():
        raise RuntimeError(
            f"Product HTML file not found: {PRODUCT_HTML}"
        )

    if not REVIEWS_HTML.is_file():
        raise RuntimeError(
            f"Reviews HTML file not found: {REVIEWS_HTML}"
        )

    product_html = PRODUCT_HTML.read_text(
        encoding="utf-8",
        errors="replace",
    )

    reviews_html = REVIEWS_HTML.read_text(
        encoding="utf-8",
        errors="replace",
    )

    product_url = f"{BASE_URL}/dp/{TARGET_ASIN}"

    product = parse_product(
        product_html,
        TARGET_ASIN,
        product_url,
        fallback_name=TARGET_PRODUCT_NAME,
    )

    reviews = parse_reviews(reviews_html)

    save_outputs(product, reviews)
    print_summary(product, reviews)


# ============================================================
# PLAYWRIGHT BROWSER NAVIGATION
# ============================================================

async def open_page(browser_page, url, save_path):
    """Open a page normally and save its returned HTML."""

    print(f"\nOpening: {url}")

    try:
        response = await browser_page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=TIMEOUT_MS,
        )
    except PlaywrightTimeoutError as exc:
        # Preserve the currently available HTML for inspection.
        try:
            html = await browser_page.content()

            Path(save_path).write_text(
                html,
                encoding="utf-8",
            )
        except Exception:
            pass

        raise RuntimeError(
            f"Navigation timed out for {url}. "
            "The runner stopped."
        ) from exc

    status = response.status if response else None

    # The browser may render the page, so capture its current HTML.
    html = await browser_page.content()

    Path(save_path).write_text(
        html,
        encoding="utf-8",
    )

    print(f"HTTP status: {status}")
    print(f"Saved response: {save_path}")

    check_access(status, html, url)

    return html


async def run_live():
    """
    Navigate directly to the known product and its first
    reviews page. No search-result matching is needed.
    """

    product_url = f"{BASE_URL}/dp/{TARGET_ASIN}"

    reviews_url = (
        f"{BASE_URL}/product-reviews/{TARGET_ASIN}/"
        "?reviewerType=all_reviews"
        "&sortBy=recent"
        "&pageNumber=1"
    )

    print("MODE: LIVE — Playwright + Scrapy XPath")
    print(f"Target ASIN: {TARGET_ASIN}")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=False,
        )

        try:
            context = await browser.new_context(
                locale="en-US",
            )

            browser_page = await context.new_page()

            # ------------------------------------------
            # Step 1: Product page
            # ------------------------------------------

            print("\nSTEP 1/2: PRODUCT PAGE")

            product_html = await open_page(
                browser_page,
                product_url,
                "product_response.html",
            )

            product = parse_product(
                product_html,
                TARGET_ASIN,
                product_url,
            )

            if not product.get("name"):
                raise RuntimeError(
                    "Product title was not found in the "
                    "returned product page HTML."
                )

            print(f"Product: {product['name']}")
            print(f"Rating: {product['average_rating']}")
            print(f"Total ratings: {product['total_ratings']}")

            # ------------------------------------------
            # Step 2: Reviews page
            # ------------------------------------------

            print("\nSTEP 2/2: REVIEWS PAGE")

            reviews_html = await open_page(
                browser_page,
                reviews_url,
                "reviews_response.html",
            )

            reviews = parse_reviews(reviews_html)

            # ------------------------------------------
            # Save output
            # ------------------------------------------

            save_outputs(product, reviews)
            print_summary(product, reviews)

        finally:
            await browser.close()


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Amazon product and review scraper using "
            "Playwright and Scrapy XPath."
        )
    )

    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Parse saved HTML files without opening a browser "
            "or sending network requests."
        ),
    )

    args = parser.parse_args()

    if args.offline:
        run_offline()
    else:
        asyncio.run(run_live())


if __name__ == "__main__":
    try:
        main()

    except (
        RuntimeError,
        OSError,
        ValueError,
    ) as exc:
        print(
            f"\nSCRAPER STOPPED: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)