import argparse
import csv
import random
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path("amazon_profile")
OUT_DIR = Path("output")
BASE = "https://www.amazon.com"

STARS = ["five_star", "four_star", "three_star", "two_star", "one_star"]
SORTS = ["recent", "helpful"]
MAX_PAGES = 10  # Amazon stops serving pages after ~10 per filter

REVIEW_FIELDS = [
    "asin", "review_id", "rating", "title", "review_text",
    "review_date", "review_date_raw", "verified_purchase", "snapshot_date",
]
PRODUCT_FIELDS = [
    "asin", "product_title", "avg_rating", "total_ratings",
    "pct_5_star", "pct_4_star", "pct_3_star", "pct_2_star", "pct_1_star",
    "snapshot_date",
]


def pause(lo=2.0, hi=5.0):
    time.sleep(random.uniform(lo, hi))


def blocked(page) -> bool:
    url = page.url.lower()
    if "signin" in url or "/ap/" in url or "captcha" in url:
        return True
    return page.locator("form[action*='validateCaptcha']").count() > 0


def text_of(node, selector):
    el = node.locator(selector).first
    if el.count() == 0:
        return ""
    return (el.inner_text() or "").strip()


def parse_rating(s):
    m = re.search(r"([\d.]+) out of 5", s)
    return float(m.group(1)) if m else None


def parse_date(raw):
    m = re.search(r" on (.+)$", raw)
    if not m:
        return ""
    try:
        return datetime.strptime(m.group(1).strip(), "%B %d, %Y").date().isoformat()
    except ValueError:
        return ""


def get_product_summary(page, asin):
    page.goto(f"{BASE}/dp/{asin}", wait_until="domcontentloaded")
    pause()
    if blocked(page):
        raise RuntimeError("Sign-in or CAPTCHA page. Run `login` and solve it by hand.")

    row = {f: "" for f in PRODUCT_FIELDS}
    row["asin"] = asin
    row["snapshot_date"] = date.today().isoformat()
    row["product_title"] = text_of(page, "#productTitle")

    avg = text_of(page, "#averageCustomerReviews .a-icon-alt")
    row["avg_rating"] = parse_rating(avg) or ""
    row["total_ratings"] = re.sub(
        r"[^\d]", "", text_of(page, "#acrCustomerReviewText")
    )

    # Histogram rows carry aria-labels like "72 percent of reviews have 5 stars"
    labels = page.locator("#histogramTable a[aria-label]").evaluate_all(
        "els => els.map(e => e.getAttribute('aria-label'))"
    )
    for lab in labels:
        m = re.search(r"(\d+) percent of reviews have (\d) star", lab or "")
        if m:
            row[f"pct_{m.group(2)}_star"] = int(m.group(1))
    return row


def scrape_reviews(page, asin, target, seen):
    new_rows = []
    snapshot = date.today().isoformat()

    for star in STARS:
        for sort in SORTS:
            if len(seen) + len(new_rows) >= target:
                return new_rows
            for pg in range(1, MAX_PAGES + 1):
                url = (
                    f"{BASE}/product-reviews/{asin}/"
                    f"?reviewerType=all_reviews&filterByStar={star}"
                    f"&sortBy={sort}&pageNumber={pg}"
                )
                page.goto(url, wait_until="domcontentloaded")
                pause()
                if blocked(page):
                    print("Stopped: Amazon asked for sign-in/CAPTCHA. "
                          "Run `login`, then re-run.", file=sys.stderr)
                    return new_rows

                cards = page.locator("[data-hook='review']")
                n = cards.count()
                if n == 0:
                    break

                added = 0
                for i in range(n):
                    c = cards.nth(i)
                    rid = c.get_attribute("id") or ""
                    if not rid or rid in seen:
                        continue
                    rating = parse_rating(
                        text_of(c, "[data-hook='review-star-rating'], "
                                   "[data-hook='cmps-review-star-rating']")
                        or (c.locator(".a-icon-alt").first.text_content() or "")
                    )
                    title_el = c.locator("[data-hook='review-title'] span").last
                    title = (title_el.inner_text().strip()
                             if title_el.count() else "")
                    raw_date = text_of(c, "[data-hook='review-date']")
                    row = {
                        "asin": asin,
                        "review_id": rid,
                        "rating": rating if rating is not None else "",
                        "title": title,
                        "review_text": text_of(c, "[data-hook='review-body']"),
                        "review_date": parse_date(raw_date),
                        "review_date_raw": raw_date,
                        "verified_purchase": c.locator(
                            "[data-hook='avp-badge']").count() > 0,
                        "snapshot_date": snapshot,
                    }
                    seen.add(rid)
                    new_rows.append(row)
                    added += 1
                    if len(seen) >= target:
                        return new_rows

                print(f"  {asin} {star}/{sort} p{pg}: +{added} "
                      f"(total {len(seen)})")
                if n < 10:
                    break  # last page for this filter
    return new_rows


def load_seen(path, asin):
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        return {r["review_id"] for r in csv.DictReader(f) if r["asin"] == asin}


def append_csv(path, fields, rows):
    if not rows:
        return
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        w.writerows(rows)


def cmd_login():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=False, locale="en-US")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(f"{BASE}/ap/signin")
        input("Sign in in the browser window, then press Enter here... ")
        ctx.close()
    print("Session saved.")


def cmd_scrape(asins, target, headless):
    OUT_DIR.mkdir(exist_ok=True)
    reviews_csv = OUT_DIR / "reviews.csv"
    products_csv = OUT_DIR / "products.csv"

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=headless, locale="en-US")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for asin in asins:
            print(f"== {asin}")
            try:
                append_csv(products_csv, PRODUCT_FIELDS,
                           [get_product_summary(page, asin)])
            except RuntimeError as e:
                print(e, file=sys.stderr)
                break

            # `seen` holds IDs from earlier runs, so only new reviews are added
            # and the target counts the whole collection for this product.
            seen = load_seen(reviews_csv, asin)
            rows = scrape_reviews(page, asin, target, seen)
            append_csv(reviews_csv, REVIEW_FIELDS, rows)
            print(f"  saved {len(rows)} new reviews for {asin}")
        ctx.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login")
    sc = sub.add_parser("scrape")
    sc.add_argument("asins", nargs="+")
    sc.add_argument("--target", type=int, default=300)
    sc.add_argument("--headless", action="store_true")
    a = ap.parse_args()

    if a.cmd == "login":
        cmd_login()
    else:
        cmd_scrape(a.asins, a.target, a.headless)