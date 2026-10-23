#!/usr/bin/env python3
"""
Fragrantica.fr product URL crawler (year -> gender -> designer filters).

Algolia only pages the first 1,000 results per query (page 34 at 30/page),
so each query is kept at 1,000 or fewer results:
  1. one query per release year
  2. a year over 1,000 is split by gender
  3. a gender slice over 1,000 is split by designer

URLs are printed and also appended to urls.csv (settings.URLS_FILE) (columns: id,pdp_url).
If you stop and re-run, it loads urls.csv first and skips products it
already has.

Run:
    python3 crawler.py            # all years
    python3 crawler.py 1990       # one year
    python3 crawler.py 1990-1999  # a range
"""

import csv
import os
import string
import sys
import time

import requests

from settings import (
    ALGOLIA_APP_ID as APP_ID, ALGOLIA_KEY as KEY, ALGOLIA_INDEX as INDEX,
    URLS_FILE as OUT_FILE,
)

BASE = f"https://{APP_ID}-dsn.algolia.net/1/indexes/{INDEX}"
URL = f"{BASE}/query"

PER_PAGE = 1000
LIMIT = 1000
DELAY = 1.5  # seconds between requests; raise it if you still get 429s

HEADERS = {
    "X-Algolia-Application-Id": APP_ID,
    "X-Algolia-API-Key": KEY.strip(),
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}

session = requests.Session()
session.headers.update(HEADERS)

seen = set()
total = 0


def load_existing():
    """Resume support: read ids already saved in urls.csv."""
    if not os.path.exists(OUT_FILE):
        return
    with open(OUT_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("id"):
                seen.add(row["id"])
    print(f"Resuming: {len(seen)} urls already in {OUT_FILE}")


def post(url, data):
    """POST that waits out 429 rate limits (30s, 60s, 120s ...)."""
    wait = 30
    r = None
    for _ in range(6):
        try:
            r = session.post(url, json=data, timeout=30)
        except requests.RequestException as e:
            print(f"   [network] {type(e).__name__}, retrying in {wait}s")
            time.sleep(wait)
            wait *= 2
            continue
        if r.status_code != 429:
            try:
                return r.json()
            except ValueError:
                return {}
        retry_after = r.headers.get("Retry-After")
        sleep_for = int(retry_after) if retry_after and retry_after.isdigit() else wait
        print(f"   [429 rate limit] waiting {sleep_for}s, then continuing...")
        time.sleep(sleep_for)
        wait *= 2
    return r.json() if r is not None else {}


def query(filters, page=0, per_page=PER_PAGE, fields=None):
    data = {"query": "", "hitsPerPage": per_page, "page": page,
            "facetFilters": filters}
    if fields:
        data["attributesToRetrieve"] = fields
    d = post(URL, data)
    if d.get("message"):
        print(f"   [api] {d['message'][:120]}")
    time.sleep(DELAY)
    return d


def count(filters):
    return query(filters, per_page=0).get("nbHits", 0)


def facet_list(attr, filters):
    data = {"query": "", "hitsPerPage": 0, "facetFilters": filters,
            "facets": [attr], "maxValuesPerFacet": 1000}
    d = post(URL, data)
    time.sleep(DELAY)
    return list(d.get("facets", {}).get(attr, {}).keys())


def designer_groups(filters):
    """One facet request returns every designer in the slice with its
    product count. Pack designers into OR-groups of <= LIMIT products, so
    a slice needs a handful of queries instead of hundreds.
    Returns (groups, products_covered)."""
    data = {"query": "", "hitsPerPage": 0, "facetFilters": filters,
            "facets": ["dizajner"], "maxValuesPerFacet": 1000}
    d = post(URL, data)
    time.sleep(DELAY)
    counts = d.get("facets", {}).get("dizajner", {})
    groups, cur, size = [], [], 0
    for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if cur and size + n > LIMIT:
            groups.append(cur)
            cur, size = [], 0
        cur.append(name)
        size += n
    if cur:
        groups.append(cur)
    return groups, sum(counts.values())


def all_designers(filters):
    """Walk letter prefixes, since a plain facet list stops at 1,000 names."""
    letters = string.ascii_lowercase + string.digits + "éèêëüöäçñøåł"
    found, todo = set(), list(letters)
    while todo:
        p = todo.pop(0)
        r = post(f"{BASE}/facets/dizajner/query",
                 {"facetQuery": p, "facetFilters": filters,
                  "maxFacetHits": 100})
        hits = r.get("facetHits", [])
        for h in hits:
            found.add(h["value"])
        if len(hits) >= 100:
            todo += [p + c for c in letters]
        time.sleep(DELAY)
    return sorted(found)


def scrape(filters, label, writer, out):
    """Print and save every product of one slice (<= LIMIT records)."""
    global total
    page = 0
    while True:
        d = query(filters, page=page, fields=["id", "slug"])
        hits = d.get("hits", [])
        for h in hits:
            pid = str(h["id"])
            if pid in seen:
                continue
            seen.add(pid)
            total += 1
            url = f"https://www.fragrantica.fr/parfum/{h['slug']}-{pid}.html"
            print(f"{len(seen)}. {url}")
            writer.writerow([pid, url])
        out.flush()
        if hits:
            print(f"   [{label}] page {page + 1}: {len(hits)} products, "
                  f"saved so far {len(seen)}")
        if not hits or d.get("message") or page + 1 >= d.get("nbPages", 0):
            break
        page += 1


def scrape_year(year, writer, out):
    print(f"\n=== YEAR {year} ===")
    n = count([f"godina:{year}"])
    print(f"year {year}: {n} products")
    if n == 0:
        return
    if n <= LIMIT:
        scrape([f"godina:{year}"], f"year {year}", writer, out)
        return
    print(f"year {year} is above the {LIMIT} limit -> splitting by gender")
    for gender in facet_list("spol", [f"godina:{year}"]):
        f2 = [f"godina:{year}", f"spol:{gender}"]
        n2 = count(f2)
        print(f"  year {year} / {gender}: {n2} products")
        if n2 == 0:
            continue
        if n2 <= LIMIT:
            scrape(f2, f"year {year} {gender}", writer, out)
            continue
        print(f"  still above {LIMIT} -> splitting by designer")
        groups, covered = designer_groups(f2)
        if covered >= n2:
            for i, g in enumerate(groups, 1):
                # inner list = OR between these designers
                f3 = f2 + [[f"dizajner:{x}" for x in g]]
                scrape(f3, f"year {year} {gender} group {i}/{len(groups)}",
                       writer, out)
            continue
        print("  too many designers for one facet call -> prefix walk")
        for designer in all_designers(f2):
            f3 = f2 + [f"dizajner:{designer}"]
            scrape(f3, f"year {year} {gender} {designer}", writer, out)


def main():
    # Quick key check
    d = post(URL, {"query": "", "hitsPerPage": 0})
    if d.get("nbHits", 0) <= 0:
        print("!! key check failed:", d.get("message", d))
        print("Copy a fresh toAbby string from view-source of the search "
              "page into KEY at the top.")
        sys.exit(1)
    site_total = d["nbHits"]

    load_existing()
    years = sorted(int(y) for y in facet_list("godina", []))
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if "-" in arg:
            a, b = arg.split("-", 1)
            years = [y for y in years if int(a) <= y <= int(b)]
        else:
            years = [int(arg)]
    print(f"Site total: {site_total} | limit per query: {LIMIT} | "
          f"years to crawl: {years}")

    new_file = not os.path.exists(OUT_FILE) or os.path.getsize(OUT_FILE) == 0
    with open(OUT_FILE, "a", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        if new_file:
            writer.writerow(["id", "pdp_url"])
        for year in years:
            scrape_year(year, writer, out)
    print(f"\nDONE. {len(seen)} product urls in {OUT_FILE} "
          f"(site total {site_total}).")


if __name__ == "__main__":
    main()