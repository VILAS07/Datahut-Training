#!/usr/bin/env python3
"""
Morrisons Groceries (UK) -- PDP Ratings & Reviews extractor.
curl-only: plain HTTP GET with urllib, no browser / no Playwright / no Selenium.

How it works (verified live 2026-11-19 from this VM):
  1. PDP data comes from the site's own BOP JSON API:
         GET /api/webproductpagews/v5/products/bop?retailerProductId=<id>
     It returns the UUID productId plus ratingSummary {overallRating, count}.
     The same average/count also sits in the PDP HTML as JSON-LD
     aggregateRating, but the BOP API is cleaner and gives price, brand,
     category path and images in one call.
  2. Individual reviews come from the site's own reviews API:
         GET /api/ecomreviews/v1/products/<UUID productId>/reviews
     Query params (all optional): sortOptionId=NEWEST|OLDEST|HIGHEST_RATED|
     LOWEST_RATED|HIGHEST_HELPFUL, pageSize, nextPage=<opaque token>.
     Default page = 5 reviews, default sort = NEWEST.
     Response: reviews[], metadata.nextPage (pass it back as ?nextPage=...),
     ratingHistogram [1*,2*,3*,4*,5*], media[], reviewCount (text reviews,
     present on page 1 only -- later pages return 0).

  Important counts -- they differ on purpose:
     ratingSummary.count (BOP) / JSON-LD ratingCount = ALL ratings,
         including rating-only submissions with no text.
     reviewCount (reviews API) = reviews WITH text.
     e.g. milk 103112099: 89 ratings, 65 text reviews, histogram sums to 89.

  Blocking: plain GET with a browser User-Agent returns HTTP 200, no login,
  no captcha seen from this VM. AWS WAF sits in front, so keep a small
  delay between calls and do not hammer the site.

Usage:
  python3 morrisons_reviews.py 103112099
  python3 morrisons_reviews.py https://groceries.morrisons.com/products/morrisons-semi-skimmed-british-milk-4-pints/103112099 --sort HIGHEST_RATED --max-pages 2
  python3 morrisons_reviews.py 103112099 113642624 114090534 --out morrisons_reviews.csv

Output: one CSV row per individual review, plus a summary printed to stdout.
Columns: retailer_product_id, product_id, product_name, brand, price_gbp,
  avg_rating, rating_count, text_review_count, star_1, star_2, star_3,
  star_4, star_5, review_id, review_headline, review_rating, review_text,
  reviewer_nickname, review_date, verified_purchase, helpful_votes, has_media
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://groceries.morrisons.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
SORTS = ["NEWEST", "OLDEST", "HIGHEST_RATED", "LOWEST_RATED", "HIGHEST_HELPFUL"]


def get_json(url):
    """Plain GET returning parsed JSON (raises on HTTP error)."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def retailer_id_from(arg):
    """Accept a bare retailer id or a full PDP URL; return the numeric id."""
    m = re.search(r"/(\d+)(?:[/?#]|$)", arg)
    if m:
        return m.group(1)
    if arg.isdigit():
        return arg
    raise ValueError(f"cannot find a numeric product id in: {arg!r}")


def fetch_bop(retailer_product_id):
    """PDP JSON: UUID productId, name, price, brand, ratingSummary, category."""
    url = (
        f"{BASE}/api/webproductpagews/v5/products/bop"
        f"?retailerProductId={retailer_product_id}"
    )
    data = get_json(url)
    product = data["product"]
    rating = product.get("ratingSummary") or {}
    category = " > ".join(
        c.get("categoryName", "") for c in (data.get("bopData") or {}).get("breadcrumbs", [])
    )
    return {
        "retailer_product_id": retailer_product_id,
        "product_id": product.get("productId"),
        "product_name": product.get("name"),
        "brand": product.get("brand"),
        "price_gbp": (product.get("price") or {}).get("amount"),
        "available": product.get("available"),
        "category_path": category,
        "avg_rating": rating.get("overallRating"),
        "rating_count": rating.get("count"),
    }


def fetch_reviews(product_id, sort="NEWEST", page_size=None, max_pages=None,
                  delay=0.5):
    """All text reviews for one product, following metadata.nextPage.

    Returns (reviews, review_count, histogram). review_count / histogram are
    only populated on page 1, so they are captured there and kept.
    """
    reviews, review_count, histogram = [], None, None
    params = {"sortOptionId": sort}
    if page_size:
        params["pageSize"] = str(page_size)
    page = 0
    while True:
        page += 1
        qs = urllib.parse.urlencode(params)
        url = f"{BASE}/api/ecomreviews/v1/products/{product_id}/reviews?{qs}"
        data = get_json(url)
        if page == 1:
            review_count = data.get("reviewCount")
            histogram = data.get("ratingHistogram")
        reviews.extend(data.get("reviews") or [])
        nxt = (data.get("metadata") or {}).get("nextPage")
        if not nxt or (max_pages and page >= max_pages):
            break
        params["nextPage"] = nxt
        if delay:
            time.sleep(delay)
    return reviews, review_count, histogram


def fetch_product_reviews(retailer_product_id, sort="NEWEST", page_size=None,
                          max_pages=None, delay=0.5):
    """Full PDP + reviews for one retailer product id. Returns (meta, rows)."""
    meta = fetch_bop(retailer_product_id)
    if not meta["product_id"]:
        raise RuntimeError(f"no productId in BOP response for {retailer_product_id}")
    reviews, text_count, histogram = fetch_reviews(
        meta["product_id"], sort=sort, page_size=page_size,
        max_pages=max_pages, delay=delay,
    )
    meta["text_review_count"] = text_count
    stars = histogram or [None] * 5
    meta.update({
        "star_1": stars[0], "star_2": stars[1], "star_3": stars[2],
        "star_4": stars[3], "star_5": stars[4],
    })
    rows = []
    for r in reviews:
        rows.append({
            **{k: meta[k] for k in (
                "retailer_product_id", "product_id", "product_name", "brand",
                "price_gbp", "avg_rating", "rating_count", "text_review_count",
                "star_1", "star_2", "star_3", "star_4", "star_5")},
            "review_id": r.get("id"),
            "review_headline": r.get("headline"),
            "review_rating": r.get("rating"),
            "review_text": r.get("comments"),
            "reviewer_nickname": r.get("nickname"),
            "review_date": (r.get("createdDate") or "")[:10],
            "verified_purchase": r.get("isVerifiedBuyer"),
            "helpful_votes": r.get("helpfulVotes"),
            "has_media": bool(r.get("media")),
        })
    return meta, rows


FIELDS = [
    "retailer_product_id", "product_id", "product_name", "brand", "price_gbp",
    "avg_rating", "rating_count", "text_review_count",
    "star_1", "star_2", "star_3", "star_4", "star_5",
    "review_id", "review_headline", "review_rating", "review_text",
    "reviewer_nickname", "review_date", "verified_purchase",
    "helpful_votes", "has_media",
]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("products", nargs="*", default=[],
                    help="retailer product id(s) or PDP URL(s). "
                         "If omitted, runs a 1-page demo on 103112099 "
                         "(Morrisons Semi Skimmed British Milk 4 Pints).")
    ap.add_argument("--sort", default="NEWEST", choices=SORTS)
    ap.add_argument("--page-size", type=int, default=None)
    ap.add_argument("--max-pages", type=int, default=None,
                    help="cap pages per product (default: all)")
    ap.add_argument("--delay", type=float, default=0.5,
                    help="seconds between paged calls (default 0.5)")
    ap.add_argument("--out", default=None, help="CSV output path")
    args = ap.parse_args(argv)

    if not args.products:
        print("No product given -- running a 1-page demo on 103112099 "
              "(Morrisons Semi Skimmed British Milk 4 Pints).")
        print("Usage: python3 morrisons_reviews.py 103112099 113642624 "
              "--out morrisons_reviews.csv")
        args.products = ["103112099"]
        if args.max_pages is None:
            args.max_pages = 1

    out = open(args.out, "w", newline="", encoding="utf-8") if args.out else None
    writer = csv.DictWriter(out, fieldnames=FIELDS) if out else None
    if writer:
        writer.writeheader()

    for arg in args.products:
        rid = retailer_id_from(arg)
        try:
            meta, rows = fetch_product_reviews(
                rid, sort=args.sort, page_size=args.page_size,
                max_pages=args.max_pages, delay=args.delay)
        except urllib.error.HTTPError as e:
            print(f"{rid}: HTTP {e.code} -- {e.reason}", file=sys.stderr)
            continue
        except Exception as e:  # noqa: BLE001 - report and move to next product
            print(f"{rid}: FAILED -- {e}", file=sys.stderr)
            continue
        print(f"{rid} | {meta['product_name']} | £{meta['price_gbp']} | "
              f"avg {meta['avg_rating']}/5 from {meta['rating_count']} ratings, "
              f"{meta['text_review_count']} text reviews, "
              f"histogram 1-5* {meta['star_1']}/{meta['star_2']}/{meta['star_3']}/"
              f"{meta['star_4']}/{meta['star_5']} | fetched {len(rows)} reviews")
        if writer:
            writer.writerows(rows)
        if args.delay:
            time.sleep(args.delay)

    if out:
        out.close()
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()