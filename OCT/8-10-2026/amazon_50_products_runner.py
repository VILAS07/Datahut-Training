#!/usr/bin/env python3
"""Collect up to 50 Amazon search-result products using normal Playwright navigation,
then parse product pages with Scrapy XPath. Individual reviews are parsed only from
locally saved/authorized review HTML files; this script does not request live review
pages because the user's current Amazon review route is returning a Sign in page.

Outputs:
  amazon_products_50.csv / .json : product rating and star-distribution records
  amazon_reviews_50.csv / .json  : review records parsed from available local HTMLs

Local review HTML naming convention:
  review_html/<ASIN>.html
Example:
  review_html/B0GJTFXNRX.html
"""

import argparse
import asyncio
import csv
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus, urljoin

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from scrapy import Selector

BASE_URL = "https://www.amazon.com"
DEFAULT_QUERY = "Apple AirTag (2nd Generation)"
DEFAULT_MAX_PRODUCTS = 50
DEFAULT_MAX_SEARCH_PAGES = 8
DEFAULT_DELAY_SECONDS = 1.5
PRODUCTS_JSON = Path("amazon_products_50.json")
PRODUCTS_CSV = Path("amazon_products_50.csv")
REVIEWS_JSON = Path("amazon_reviews_50.json")
REVIEWS_CSV = Path("amazon_reviews_50.csv")
REVIEW_HTML_DIR = Path("review_html")

PRODUCT_COLUMNS = [
    "asin", "product_name", "product_url", "average_rating", "rating_text",
    "total_ratings", "total_ratings_text", "one_star_percent", "two_star_percent",
    "three_star_percent", "four_star_percent", "five_star_percent",
    "review_html_status",
]
REVIEW_COLUMNS = [
    "product_asin", "product_name", "product_url", "review_id", "rating",
    "rating_text", "review_title", "review_date", "review_date_label",
    "verified_purchase", "review_text",
]


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def joined_text(selector, xpath):
    return clean_text(" ".join(selector.xpath(xpath).getall()))


def save_text(path, value):
    Path(path).write_text(value, encoding="utf-8")


def check_access(status, html, url):
    if status in (403, 429, 503):
        raise RuntimeError(
            f"HTTP {status} returned for {url}; stopping without retries or bypasses."
        )
    if status is not None and status >= 400:
        raise RuntimeError(f"HTTP {status} returned for {url}.")

    page = Selector(text=html, type="html")
    title = joined_text(page, "//title//text()").lower()
    body = joined_text(page, "//body//text()").lower()
    markers = [
        "we limit review access when we detect unusual activity",
        "sorry, we just need to make sure you're not a robot",
        "enter the characters you see below",
        "access denied",
    ]
    if any(m in body for m in markers):
        raise RuntimeError(
            f"Access restriction or verification page returned for {url}; stopping."
        )
    if "validatecaptcha" in url.lower() or page.xpath(
        '//*[@id="captchacharacters"] | //*[@name="cvf_captcha_input"]'
    ):
        raise RuntimeError(f"CAPTCHA page returned for {url}; stopping.")
    if title == "sign in":
        raise RuntimeError(f"Sign-in page returned for {url}; stopping.")


def parse_search_results(html):
    page = Selector(text=html, type="html")
    cards = page.xpath('//*[@data-component-type="s-search-result"][@data-asin]')
    products = []
    for card in cards:
        asin = clean_text(card.xpath("./@data-asin").get())
        title = joined_text(card, ".//h2//span//text()")
        href = card.xpath('.//h2/ancestor::a[1]/@href').get()
        if not href:
            href = card.xpath('.//a[@href and .//h2]/@href').get()
        if not asin or not title or not href:
            continue
        url = urljoin(BASE_URL, href)
        products.append({"asin": asin, "name": title, "url": url})
    return products


def parse_product_page(html, search_item):
    page = Selector(text=html, type="html")
    title = joined_text(page, '//*[@id="productTitle"]//text()') or search_item["name"]

    rating_text = clean_text(page.xpath('//*[@id="acrPopover"]/@title').get())
    if not rating_text:
        rating_text = joined_text(
            page,
            '//*[@id="acrPopover"]//*[contains(@class,"a-icon-alt")]/text()',
        )
    rating_match = re.search(r"(\d+(?:\.\d+)?)", rating_text)
    average_rating = float(rating_match.group(1)) if rating_match else None

    total_ratings_text = joined_text(page, '//*[@id="acrCustomerReviewText"]//text()')
    total_match = re.search(r"([\d,]+)", total_ratings_text)
    total_ratings = int(total_match.group(1).replace(",", "")) if total_match else None

    distribution = {}
    for row in page.xpath('//*[@id="histogramTable"]//tr'):
        row_text = joined_text(row, ".//text()")
        star_match = re.search(r"\b([1-5])\s*stars?\b", row_text, re.I)
        pct_match = re.search(r"\b(\d{1,3})\s*%", row_text)
        if star_match and pct_match:
            distribution[f"{star_match.group(1)}_star_percent"] = int(pct_match.group(1))

    return {
        "asin": search_item["asin"],
        "product_name": title,
        "product_url": search_item["url"],
        "average_rating": average_rating,
        "rating_text": rating_text or None,
        "total_ratings": total_ratings,
        "total_ratings_text": total_ratings_text or None,
        "star_distribution": distribution,
        "review_html_status": "not_found_locally",
    }


def parse_one_review(card):
    review_id = clean_text(card.xpath("./@id").get())
    rating_text = joined_text(
        card,
        './/*[@data-hook="review-star-rating"]//span[contains(@class,"a-icon-alt")]/text()',
    )
    rating_match = re.search(r"(\d+(?:\.\d+)?)", rating_text)
    rating = float(rating_match.group(1)) if rating_match else None

    title = joined_text(
        card,
        './/a[@data-hook="review-title"]/span[normalize-space()]//text()',
    )
    date_label = joined_text(card, './/*[@data-hook="review-date"]//text()')
    date_match = re.search(r"\bon\s+(.+)$", date_label, re.I)
    review_date = clean_text(date_match.group(1)) if date_match else date_label
    text = joined_text(card, './/*[@data-hook="review-body"]//text()')
    badge = joined_text(card, './/*[@data-hook="avp-badge"]//text()')
    return {
        "review_id": review_id or None,
        "rating": rating,
        "rating_text": rating_text or None,
        "review_title": title or None,
        "review_date": review_date or None,
        "review_date_label": date_label or None,
        "verified_purchase": "verified purchase" in badge.lower(),
        "review_text": text or None,
    }


def find_local_review_html(asin):
    """Find a previously saved review HTML file for an ASIN."""
    per_asin_path = REVIEW_HTML_DIR / f"{asin}.html"
    if per_asin_path.exists():
        return per_asin_path
    # Reuse the existing saved capture for the user's AirTag test product.
    if asin == "B0GJTFXNRX" and Path("amazon_customer_reviews.html").exists():
        return Path("amazon_customer_reviews.html")
    return None


def parse_local_reviews(asin, product_name, product_url, html_path=None):
    # Parse saved review HTML only. No live review-page request is made.
    source_path = find_local_review_html(asin)
    if source_path is None:
        return []
    html = source_path.read_text(encoding="utf-8", errors="replace")
    page = Selector(text=html, type="html")
    cards = page.xpath('//*[@data-hook="review"]')
    reviews = []
    seen_ids = set()
    for card in cards:
        record = parse_one_review(card)
        rid = record.get("review_id")
        if rid and rid in seen_ids:
            continue
        if rid:
            seen_ids.add(rid)
        reviews.append({
            "product_asin": asin,
            "product_name": product_name,
            "product_url": product_url,
            **record,
        })
    return reviews


def write_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export_results(products, reviews):
    product_rows = []
    for p in products:
        dist = p.get("star_distribution", {})
        product_rows.append({
            "asin": p.get("asin"),
            "product_name": p.get("product_name"),
            "product_url": p.get("product_url"),
            "average_rating": p.get("average_rating"),
            "rating_text": p.get("rating_text"),
            "total_ratings": p.get("total_ratings"),
            "total_ratings_text": p.get("total_ratings_text"),
            "one_star_percent": dist.get("1_star_percent"),
            "two_star_percent": dist.get("2_star_percent"),
            "three_star_percent": dist.get("3_star_percent"),
            "four_star_percent": dist.get("4_star_percent"),
            "five_star_percent": dist.get("5_star_percent"),
            "review_html_status": p.get("review_html_status"),
        })
    PRODUCTS_JSON.write_text(json.dumps(products, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REVIEWS_JSON.write_text(json.dumps(reviews, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(PRODUCTS_CSV, product_rows, PRODUCT_COLUMNS)
    write_csv(REVIEWS_CSV, reviews, REVIEW_COLUMNS)
    print(f"Saved products: {PRODUCTS_JSON} and {PRODUCTS_CSV}")
    print(f"Saved reviews:  {REVIEWS_JSON} and {REVIEWS_CSV}")


async def goto_and_save(page, url, save_path):
    print(f"Opening {url}")
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except PlaywrightTimeoutError as exc:
        try:
            save_text(save_path, await page.content())
        except Exception:
            pass
        raise RuntimeError(f"Navigation timeout at {url}; stopped.") from exc
    status = response.status if response else None
    html = await page.content()
    save_text(save_path, html)
    print(f"HTTP {status}; saved {save_path}")
    check_access(status, html, url)
    return html


async def run_live(query, max_products, max_search_pages, delay):
    products_by_asin = {}
    product_records = []
    all_reviews = []
    print(f"Searching for up to {max_products} products: {query!r}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        try:
            context = await browser.new_context(locale="en-US")
            page = await context.new_page()
            for page_num in range(1, max_search_pages + 1):
                url = f"{BASE_URL}/s?k={quote_plus(query)}&page={page_num}"
                html = await goto_and_save(page, url, f"search_response_{page_num}.html")
                found = parse_search_results(html)
                if not found:
                    print(f"No product links detected on search page {page_num}; stopping discovery.")
                    break
                added = 0
                for item in found:
                    if item["asin"] not in products_by_asin:
                        products_by_asin[item["asin"]] = item
                        added += 1
                        if len(products_by_asin) >= max_products:
                            break
                print(f"Search page {page_num}: {len(found)} cards, {added} new unique products, total {len(products_by_asin)}")
                if len(products_by_asin) >= max_products:
                    break
                if added == 0:
                    print("No new ASINs on this search page; stopping discovery.")
                    break
                await asyncio.sleep(delay)

            if not products_by_asin:
                raise RuntimeError("No product links were extracted. Inspect saved search_response_*.html files.")

            print(f"\nFetching product details for {len(products_by_asin)} unique ASINs.")
            for index, item in enumerate(products_by_asin.values(), 1):
                print(f"\nProduct {index}/{len(products_by_asin)} — {item['asin']}")
                try:
                    html = await goto_and_save(page, item["url"], f"product_{item['asin']}.html")
                except RuntimeError as exc:
                    # Preserve already-collected records, then stop on access or navigation failure.
                    print(f"Stopping product collection: {exc}", file=sys.stderr)
                    break
                record = parse_product_page(html, item)
                local_review_file = REVIEW_HTML_DIR / f"{item['asin']}.html"
                record["review_html_status"] = (
                    "parsed_local_html" if find_local_review_html(item["asin"])
                    else "no_local_review_html; live review pages are not requested"
                )
                product_records.append(record)
                local_reviews = parse_local_reviews(
                    item["asin"], record["product_name"], item["url"], local_review_file
                )
                all_reviews.extend(local_reviews)
                print(f"Title: {record['product_name']}")
                print(f"Average rating: {record['average_rating']}; total ratings: {record['total_ratings']}")
                print(f"Local review records parsed: {len(local_reviews)}")
                await asyncio.sleep(delay)
        finally:
            await browser.close()
    export_results(product_records, all_reviews)
    print(f"\nFinished. Products saved: {len(product_records)}; review rows from local HTML: {len(all_reviews)}")
    print("Individual review fields are populated only where an accessible review HTML file exists in review_html/<ASIN>.html.")


def run_offline(search_html, max_products):
    products_by_asin = {}
    if search_html.is_file():
        source_files = [search_html]
    else:
        source_files = sorted(Path(".").glob("search_response_*.html"))
    if not source_files:
        raise RuntimeError(f"No saved search HTML found. Expected {search_html} or search_response_*.html.")
    for path in source_files:
        html = path.read_text(encoding="utf-8", errors="replace")
        items = parse_search_results(html)
        for item in items:
            products_by_asin.setdefault(item["asin"], item)
            if len(products_by_asin) >= max_products:
                break
        if len(products_by_asin) >= max_products:
            break

    # Include the known product from the previously saved product page even if
    # Amazon's current search results do not show that exact ASIN.
    known_product_path = Path("amazon_airtag.html")
    if known_product_path.exists() and "B0GJTFXNRX" not in products_by_asin:
        known_html = known_product_path.read_text(encoding="utf-8", errors="replace")
        known_page = Selector(text=known_html, type="html")
        known_name = joined_text(known_page, '//*[@id="productTitle"]//text()') or TARGET_PRODUCT_NAME
        products_by_asin["B0GJTFXNRX"] = {
            "asin": "B0GJTFXNRX",
            "name": known_name,
            "url": f"{BASE_URL}/dp/B0GJTFXNRX",
        }

    if not products_by_asin:
        raise RuntimeError("No product links could be parsed from saved search HTML.")

    product_records = []
    all_reviews = []
    for item in products_by_asin.values():
        product_path = Path(f"product_{item['asin']}.html")
        if item["asin"] == "B0GJTFXNRX" and Path("amazon_airtag.html").exists():
            product_path = Path("amazon_airtag.html")
        if not product_path.exists():
            print(f"Skipping product detail (no saved page): {item['asin']} — {item['name']}")
            continue
        html = product_path.read_text(encoding="utf-8", errors="replace")
        record = parse_product_page(html, item)
        local_review_file = REVIEW_HTML_DIR / f"{item['asin']}.html"
        record["review_html_status"] = "parsed_local_html" if find_local_review_html(item["asin"]) else "no_local_review_html"
        product_records.append(record)
        all_reviews.extend(parse_local_reviews(item["asin"], record["product_name"], item["url"], local_review_file))
    export_results(product_records, all_reviews)
    print(f"Offline complete: products with saved detail pages={len(product_records)}, review rows={len(all_reviews)}")


def main():
    parser = argparse.ArgumentParser(description="Collect up to 50 Amazon search products with Playwright + Scrapy XPath.")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Amazon search query")
    parser.add_argument("--max-products", type=int, default=DEFAULT_MAX_PRODUCTS, help="Maximum unique products (default: 50)")
    parser.add_argument("--max-search-pages", type=int, default=DEFAULT_MAX_SEARCH_PAGES, help="Maximum search pages to visit")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help="Pause between ordinary page navigations")
    parser.add_argument("--offline", action="store_true", help="Process locally saved HTML only")
    parser.add_argument("--search-html", type=Path, default=Path("search_response.html"), help="Saved search page path for offline mode")
    args = parser.parse_args()
    if not 1 <= args.max_products <= 50:
        parser.error("--max-products must be between 1 and 50")
    if args.offline:
        run_offline(args.search_html, args.max_products)
    else:
        asyncio.run(run_live(args.query, args.max_products, args.max_search_pages, args.delay))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"\nRUN STOPPED: {exc}", file=sys.stderr)
        raise SystemExit(1)
