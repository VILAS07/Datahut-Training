import csv
import json
import re
from pathlib import Path
from datetime import datetime

from scrapy import Selector


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path.cwd()

PRODUCT_GLOB = "product_*.html"

PRODUCT_CSV = BASE_DIR / "amazon_products_50_enriched.csv"
PRODUCT_JSON = BASE_DIR / "amazon_products_50_enriched.json"

REVIEWS_CSV = BASE_DIR / "amazon_reviews_from_saved_html.csv"
REVIEWS_JSON = BASE_DIR / "amazon_reviews_from_saved_html.json"

REPORT_CSV = BASE_DIR / "amazon_local_page_report.csv"

# Extra saved HTML files that might contain individual review cards.
EXTRA_REVIEW_FILES = [
    "amazon_customer_reviews.html",
    "product_response.html",
    "reviews_response.html",
    "amazon_review_response.html",
    "amazon_airtag.html",
]

STAR_KEYS = [
    "5_star_percentage",
    "4_star_percentage",
    "3_star_percentage",
    "2_star_percentage",
    "1_star_percentage",
]


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(value):
    """Normalize whitespace in extracted text."""
    if value is None:
        return ""

    value = str(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def read_html(path):
    """Read an HTML file using UTF-8, with a fallback encoding."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"Could not read {path.name}: {exc}")
        return ""


def first_node_text(root, selectors):
    """Return the first non-empty text found by a list of CSS selectors."""
    for css_selector in selectors:
        try:
            nodes = root.css(css_selector)

            for node in nodes:
                value = clean_text(node.xpath("string(.)").get())

                if value:
                    return value

        except Exception:
            continue

    return ""


def first_attribute(root, selectors):
    """Return the first non-empty attribute found by CSS selectors."""
    for css_selector, attribute in selectors:
        try:
            value = root.css(css_selector).attrib.get(attribute, "")

            if value:
                return clean_text(value)

        except Exception:
            continue

    return ""


def extract_asin(html, path):
    """Extract an ASIN without using unrelated recommendation products."""

    # Most reliable for files named product_B000000000.html.
    filename_match = re.fullmatch(
        r"product_([A-Z0-9]{10})\.html",
        path.name,
        flags=re.IGNORECASE,
    )

    if filename_match:
        return filename_match.group(1).upper()

    selector = Selector(text=html)

    # ASIN on a product-page element.
    for xpath in [
        '//*[@id="ASIN"]/@value',
        '//*[@id="averageCustomerReviews"]/@data-asin',
        '//*[@id="dp"]/@data-asin',
    ]:
        try:
            value = selector.xpath(xpath).get()

            if value and re.fullmatch(r"[A-Z0-9]{10}", value.strip(), re.I):
                return value.strip().upper()

        except Exception:
            pass

    # ASIN in a product or review URL embedded in the saved HTML.
    patterns = [
        r"/product-reviews/([A-Z0-9]{10})",
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
    ]

    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)

        if match:
            return match.group(1).upper()

    # Some Amazon pages contain a product ASIN in JSON data.
    patterns = [
        r'"currentAsin"\s*:\s*"([A-Z0-9]{10})"',
        r'"asin"\s*:\s*"([A-Z0-9]{10})"',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)

        if match:
            return match.group(1).upper()

    return ""


# ============================================================
# PRODUCT SUMMARY EXTRACTION
# ============================================================

def extract_average_rating(selector):
    """Extract the average product rating, e.g. 4.5."""

    candidates = []

    candidates.append(
        first_attribute(
            selector,
            [
                ("#acrPopover", "title"),
                ('[data-hook="rating-out-of-text"]', "aria-label"),
            ],
        )
    )

    candidates.append(
        first_node_text(
            selector,
            [
                "#acrPopover span.a-icon-alt",
                "#averageCustomerReviews span.a-icon-alt",
                '[data-hook="rating-out-of-text"]',
            ],
        )
    )

    for candidate in candidates:
        if not candidate:
            continue

        match = re.search(r"([0-5](?:\.\d+)?)\s*out of\s*5", candidate, re.I)

        if match:
            return float(match.group(1))

        match = re.search(r"\b([0-5]\.\d+)\b", candidate)

        if match:
            return float(match.group(1))

    return ""


def extract_total_ratings(selector):
    """Extract the total rating count, e.g. 2,561."""

    text = first_node_text(
        selector,
        [
            "#acrCustomerReviewText",
            "#averageCustomerReviews #acrCustomerReviewText",
            '[data-hook="cr-link-text"]',
        ],
    )

    if text:
        match = re.search(r"([\d,]+)\s+(?:global\s+)?ratings?\b", text, re.I)

        if match:
            return int(match.group(1).replace(",", ""))

    # Try the text in the product-review summary section.
    summary_text = clean_text(
        selector.xpath('string//*[@id="averageCustomerReviews"]').get()
    )

    match = re.search(
        r"([\d,]+)\s+(?:global\s+)?ratings?\b",
        summary_text,
        re.I,
    )

    if match:
        return int(match.group(1).replace(",", ""))

    return ""


def parse_star_percentage(text):
    """
    Parse star percentages from values such as:
      '78 percent of reviews have 5 stars'
      '5 stars 78%'
    """
    text = clean_text(text)

    star_match = re.search(r"\b([1-5])\s*stars?\b", text, re.I)

    if not star_match:
        return None, None

    star = int(star_match.group(1))

    percentage_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:%|\bpercent\b)",
        text,
        re.I,
    )

    if not percentage_match:
        return None, None

    percentage = float(percentage_match.group(1))

    return star, percentage


def extract_star_distribution(selector):
    """Extract the product's five-star-to-one-star distribution."""

    distribution = {
        "5_star_percentage": "",
        "4_star_percentage": "",
        "3_star_percentage": "",
        "2_star_percentage": "",
        "1_star_percentage": "",
    }

    histogram_nodes = selector.xpath('//*[@id="histogramTable"]')

    for histogram in histogram_nodes:
        # Check aria-labels and titles in the histogram.
        for attribute in ["aria-label", "title"]:
            values = histogram.xpath(f'.//*[@{attribute}]/@{attribute}').getall()

            for value in values:
                star, percentage = parse_star_percentage(value)

                if star is not None and percentage is not None:
                    distribution[f"{star}_star_percentage"] = percentage

        # Also check the visible text in each histogram row.
        rows = histogram.xpath(".//tr")

        for row in rows:
            row_text = clean_text(row.xpath("string(.)").get())

            star, percentage = parse_star_percentage(row_text)

            if star is not None and percentage is not None:
                distribution[f"{star}_star_percentage"] = percentage

    # Some pages use links instead of accessible table rows.
    if not any(value != "" for value in distribution.values()):
        for node in selector.css(
            '#histogramTable a, #histogramTable [role="row"]'
        ):
            combined_text = clean_text(
                node.attrib.get("aria-label", "")
                + " "
                + node.attrib.get("title", "")
                + " "
                + node.xpath("string(.)").get()
            )

            star, percentage = parse_star_percentage(combined_text)

            if star is not None and percentage is not None:
                distribution[f"{star}_star_percentage"] = percentage

    return distribution


def extract_product_summary(html, path):
    """Extract product summary fields from one saved product HTML page."""

    selector = Selector(text=html)

    asin = extract_asin(html, path)

    title = first_node_text(
        selector,
        [
            "#productTitle",
            'span[data-hook="product-title"]',
            "h1 span#title",
        ],
    )

    average_rating = extract_average_rating(selector)
    total_ratings = extract_total_ratings(selector)
    distribution = extract_star_distribution(selector)

    summary = {
        "asin": asin,
        "product_name": title,
        "average_rating": average_rating,
        "total_ratings": total_ratings,
        **distribution,
        "source_file": path.name,
    }

    return summary


# ============================================================
# INDIVIDUAL REVIEW EXTRACTION
# ============================================================

def first_review_text(card, selectors):
    """Read a review field using multiple possible Amazon selectors."""

    for css_selector in selectors:
        try:
            nodes = card.css(css_selector)

            for node in nodes:
                text = clean_text(node.xpath("string(.)").get())

                if text:
                    return text

        except Exception:
            continue

    return ""


def extract_review_id(card):
    """Extract the review ID from a review card's id attribute."""

    card_id = clean_text(card.attrib.get("id", ""))

    if card_id.startswith("customer_review-"):
        return card_id[len("customer_review-"):]

    return card_id


def extract_review_date(raw_date):
    """Extract the date portion from Amazon's review-date text."""

    raw_date = clean_text(raw_date)

    # Example: Reviewed in the United States on August 18, 2026
    match = re.search(
        r"\bon\s+("
        r"(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+\d{4}"
        r")",
        raw_date,
        re.I,
    )

    if match:
        return clean_text(match.group(1)).replace("  ", " ")

    # Other possible date format: 18 August 2026
    match = re.search(
        r"\b\d{1,2}\s+"
        r"(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{4}\b",
        raw_date,
        re.I,
    )

    if match:
        return match.group(0)

    # ISO-style date.
    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", raw_date)

    if match:
        return match.group(0)

    return raw_date


def extract_review_rating(card):
    """Extract a review's star rating."""

    rating_text = first_review_text(
        card,
        [
            '[data-hook="review-star-rating"]',
            '[data-hook="cmps-review-star-rating"]',
            'i.review-rating span.a-icon-alt',
            'i[data-hook="review-star-rating"] span.a-icon-alt',
        ],
    )

    if not rating_text:
        rating_text = first_attribute(
            card,
            [
                ('[data-hook="review-star-rating"]', "title"),
                ('[data-hook="cmps-review-star-rating"]', "title"),
            ],
        )

    match = re.search(r"\b([1-5](?:\.\d+)?)\s*out of\s*5", rating_text, re.I)

    if match:
        return float(match.group(1))

    return ""


def extract_review_card(card, asin, product_name, source_file):
    """Extract review data without collecting reviewer names."""

    review_id = extract_review_id(card)

    title = first_review_text(
        card,
        [
            '[data-hook="reviewTitle"]',
            '[data-hook="review-title"]',
            'a[data-hook="review-title"] span',
        ],
    )

    # Remove a rating phrase if it was accidentally included in the title.
    title = re.sub(
        r"^\s*[1-5](?:\.\d+)?\s*out of\s*5 stars\s*",
        "",
        title,
        flags=re.I,
    ).strip()

    rating = extract_review_rating(card)

    raw_date = first_review_text(
        card,
        [
            '[data-hook="review-date"]',
        ],
    )

    review_date = extract_review_date(raw_date)

    # Prefer the actual review-text element over its surrounding container.
    review_text = first_review_text(
        card,
        [
            '[data-hook="reviewText"]',
            '[data-hook="review-body"]',
            '[data-hook="reviewTextContainer"]',
        ],
    )

    verified_text = first_review_text(
        card,
        [
            '[data-hook="avp-badge"]',
            '[data-hook="avp-badge-linkless"]',
        ],
    )

    verified_purchase = (
        "Yes"
        if "verified purchase" in verified_text.lower()
        else "No"
    )

    return {
        "asin": asin,
        "product_name": product_name,
        "review_id": review_id,
        "rating": rating,
        "review_date": review_date,
        "review_title": title,
        "review_text": review_text,
        "verified_purchase": verified_purchase,
        "source_file": source_file,
    }


def extract_review_cards(html, path, product_lookup):
    """Extract review cards actually present in a saved HTML file."""

    selector = Selector(text=html)
    asin = extract_asin(html, path)

    product_name = ""

    if asin and asin in product_lookup:
        product_name = product_lookup[asin].get("product_name", "")

    # Avoid assigning reviews to a random product when the ASIN is unknown.
    if not asin:
        asin = ""

    cards = selector.xpath('//*[@data-hook="review"]')

    review_rows = []

    for card in cards:
        review = extract_review_card(
            card=card,
            asin=asin,
            product_name=product_name,
            source_file=path.name,
        )

        # Ignore empty elements that are not useful review records.
        if (
            review["review_id"]
            or review["review_text"]
            or review["review_title"]
        ):
            review_rows.append(review)

    return review_rows, len(cards), asin


# ============================================================
# SAVE OUTPUT FILES
# ============================================================

def save_csv(path, rows, fieldnames):
    """Save a list of dictionaries as a UTF-8 CSV file."""

    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)


def save_json(path, rows):
    """Save a list of dictionaries as a JSON file."""

    with path.open("w", encoding="utf-8") as file:
        json.dump(rows, file, indent=2, ensure_ascii=False)


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("AMAZON SAVED HTML EXTRACTOR")
    print("=" * 70)
    print(f"Working directory: {BASE_DIR}")
    print("Mode: local HTML only; no network requests")
    print()

    # --------------------------------------------------------
    # 1. Load the 50 product pages
    # --------------------------------------------------------

    product_files = []

    for path in sorted(BASE_DIR.glob(PRODUCT_GLOB)):
        # Only accept product_<10-character-ASIN>.html files.
        # This excludes product_response.html.
        if re.fullmatch(
            r"product_[A-Z0-9]{10}\.html",
            path.name,
            flags=re.IGNORECASE,
        ):
            product_files.append(path)

    print(f"Product HTML pages found: {len(product_files)}")

    products = []
    product_lookup = {}

    report_rows = []

    for path in product_files:
        html = read_html(path)

        if not html:
            continue

        product = extract_product_summary(html, path)
        products.append(product)

        if product["asin"]:
            product_lookup[product["asin"]] = product

        _, card_count, _ = extract_review_cards(
            html,
            path,
            product_lookup,
        )

        histogram_count = sum(
            1 for key in STAR_KEYS
            if product.get(key, "") != ""
        )

        report_rows.append({
            "source_file": path.name,
            "asin": product["asin"],
            "product_name_found": bool(product["product_name"]),
            "average_rating_found": product["average_rating"] != "",
            "total_ratings_found": product["total_ratings"] != "",
            "star_percentages_found": histogram_count,
            "individual_review_cards_found": card_count,
        })

    product_fields = [
        "asin",
        "product_name",
        "average_rating",
        "total_ratings",
        "5_star_percentage",
        "4_star_percentage",
        "3_star_percentage",
        "2_star_percentage",
        "1_star_percentage",
        "source_file",
    ]

    save_csv(PRODUCT_CSV, products, product_fields)
    save_json(PRODUCT_JSON, products)

    # --------------------------------------------------------
    # 2. Extract reviews from product pages and extra pages
    # --------------------------------------------------------

    review_source_files = list(product_files)

    for filename in EXTRA_REVIEW_FILES:
        path = BASE_DIR / filename

        if path.exists() and path not in review_source_files:
            review_source_files.append(path)

    all_reviews = []
    seen_reviews = set()
    review_report = {}

    for path in review_source_files:
        html = read_html(path)

        if not html:
            continue

        review_rows, card_count, asin = extract_review_cards(
            html,
            path,
            product_lookup,
        )

        review_report[path.name] = {
            "source_file": path.name,
            "asin_detected": asin,
            "review_cards_found": card_count,
            "review_records_extracted": len(review_rows),
        }

        for review in review_rows:
            review_id = clean_text(review.get("review_id", ""))

            # De-duplicate by ASIN + review ID when the ID exists.
            if review_id:
                unique_key = (
                    review.get("asin", ""),
                    review_id,
                )
            else:
                unique_key = (
                    review.get("asin", ""),
                    review.get("source_file", ""),
                    review.get("review_date", ""),
                    review.get("rating", ""),
                    review.get("review_text", ""),
                )

            if unique_key in seen_reviews:
                continue

            seen_reviews.add(unique_key)
            all_reviews.append(review)

    review_fields = [
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

    save_csv(REVIEWS_CSV, all_reviews, review_fields)
    save_json(REVIEWS_JSON, all_reviews)

    # --------------------------------------------------------
    # 3. Build a report showing which pages contained data
    # --------------------------------------------------------

    for filename, info in review_report.items():
        if filename in {row["source_file"] for row in report_rows}:
            for row in report_rows:
                if row["source_file"] == filename:
                    row["individual_review_cards_found"] = info[
                        "review_cards_found"
                    ]
                    break
        else:
            report_rows.append({
                "source_file": info["source_file"],
                "asin": info["asin_detected"],
                "product_name_found": "",
                "average_rating_found": "",
                "total_ratings_found": "",
                "star_percentages_found": "",
                "individual_review_cards_found": info[
                    "review_cards_found"
                ],
            })

    report_fields = [
        "source_file",
        "asin",
        "product_name_found",
        "average_rating_found",
        "total_ratings_found",
        "star_percentages_found",
        "individual_review_cards_found",
    ]

    save_csv(REPORT_CSV, report_rows, report_fields)

    # --------------------------------------------------------
    # 4. Print summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)
    print(f"Product pages processed: {len(products)}")
    print(f"Individual review records extracted: {len(all_reviews)}")

    products_with_ratings = sum(
        1 for product in products
        if product["average_rating"] != ""
    )

    products_with_total = sum(
        1 for product in products
        if product["total_ratings"] != ""
    )

    products_with_histogram = sum(
        1 for product in products
        if any(product.get(key, "") != "" for key in STAR_KEYS)
    )

    print(f"Products with average rating: {products_with_ratings}")
    print(f"Products with total ratings count: {products_with_total}")
    print(f"Products with star distribution: {products_with_histogram}")

    print()
    print("OUTPUT FILES")
    print(f"1. {PRODUCT_CSV.name}")
    print(f"2. {PRODUCT_JSON.name}")
    print(f"3. {REVIEWS_CSV.name}")
    print(f"4. {REVIEWS_JSON.name}")
    print(f"5. {REPORT_CSV.name}")

    print()
    print("REVIEW SOURCE DETAILS")

    for filename, info in review_report.items():
        print(
            f"{filename}: "
            f"{info['review_cards_found']} cards found, "
            f"{info['review_records_extracted']} records extracted"
        )

    if not all_reviews:
        print()
        print(
            "NOTE: No individual review records were extracted. "
            "The saved HTML files may contain only product summaries, "
            "or Amazon may have returned a sign-in/restricted page. "
            "The script does not download or bypass restricted content."
        )

    print()
    print("Done.")


if __name__ == "__main__":
    main()