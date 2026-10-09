import requests
from scrapy import Selector
import json
import re
from urllib.parse import urljoin


# ============================================================
# CONFIG
# ============================================================

PRODUCT_URL = "https://www.amazon.com/dp/B0GJTFXNRX"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}


session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# CRAWLER
# ============================================================

print("=" * 100)
print("AMAZON - AIRTAG REVIEW FEASIBILITY CRAWLER")
print("=" * 100)

print("\n[PRODUCT]")
print(PRODUCT_URL)

response = session.get(
    PRODUCT_URL,
    timeout=30
)

print("STATUS :", response.status_code)
print("SIZE   :", len(response.text))

if response.status_code != 200:
    print("\n[ERROR] Product page could not be downloaded.")
    exit()


html = response.text
selector = Selector(text=html)


# ============================================================
# PRODUCT PARSER
# ============================================================

print("\n" + "=" * 100)
print("PRODUCT PARSER")
print("=" * 100)


# -------------------------
# ASIN
# -------------------------

asin = selector.xpath(
    '//div[@id="averageCustomerReviews"]/@data-asin'
).get()

if not asin:
    asin_match = re.search(
        r'"(?:asin|ASIN)"\s*[:=]\s*["\']([A-Z0-9]{10})["\']',
        html
    )

    if asin_match:
        asin = asin_match.group(1)

print("ASIN              :", asin)


# -------------------------
# PRODUCT NAME
# -------------------------

product_name = selector.xpath(
    '//span[@id="productTitle"]/text()'
).get()

if product_name:
    product_name = " ".join(product_name.split())

print("PRODUCT NAME      :", product_name)


# ============================================================
# RATING
# ============================================================

print("\n" + "=" * 100)
print("RATING")
print("=" * 100)


# Average rating

average_rating = selector.xpath(
    '//span[@data-hook="average-star-rating"]/'
    'span[contains(@class,"a-icon-alt")]/text()'
).get()

if not average_rating:
    average_rating = selector.xpath(
        '//span[@data-hook="rating-out-of-text"]/text()'
    ).get()

print("AVERAGE RATING    :", average_rating)


# Total ratings

total_ratings = selector.xpath(
    '//span[@data-hook="total-review-count"]/text()'
).get()

if total_ratings:
    total_ratings = total_ratings.strip()

print("TOTAL RATINGS     :", total_ratings)


# ============================================================
# STAR DISTRIBUTION
# ============================================================

print("\n" + "=" * 100)
print("STAR DISTRIBUTION")
print("=" * 100)


star_distribution = {}

for star in range(5, 0, -1):

    xpath = (
        f'//a[contains(@href,"filterByStar='
        f'{"five" if star == 5 else "four" if star == 4 else "three" if star == 3 else "two" if star == 2 else "one"}'
        f'_star")]'
    )

    element = selector.xpath(xpath)

    if element:

        text = " ".join(
            element.xpath(".//text()").getall()
        )

        match = re.search(
            r'(\d+)%\s*$',
            text
        )

        if match:
            percentage = match.group(1) + "%"
        else:
            aria = element.xpath("./@aria-label").get()

            match = re.search(
                r'(\d+)\s*percent',
                aria or "",
                re.I
            )

            percentage = (
                match.group(1) + "%"
                if match else None
            )

        star_distribution[star] = percentage


# More reliable method using aria-label

if not star_distribution:

    for element in selector.xpath(
        '//a[contains(@aria-label,"percent of reviews")]'
    ):

        aria = element.xpath("./@aria-label").get()

        match = re.search(
            r'(\d+)\s*percent of reviews have (\d+) stars',
            aria or "",
            re.I
        )

        if match:
            percentage = match.group(1) + "%"
            star = int(match.group(2))

            star_distribution[star] = percentage


for star in range(5, 0, -1):
    print(
        f"{star} STAR            : "
        f"{star_distribution.get(star, 'NOT FOUND')}"
    )


# ============================================================
# REVIEW STATE
# ============================================================

print("\n" + "=" * 100)
print("REVIEW SYSTEM")
print("=" * 100)


state_match = re.search(
    r'<span[^>]+id="cr-state-object"[^>]+'
    r'data-state=\'(.*?)\'',
    html,
    re.S
)

review_state = None

if state_match:

    state_raw = state_match.group(1)

    try:
        review_state = json.loads(state_raw)

    except json.JSONDecodeError:

        # Sometimes HTML entities are present
        import html as html_module

        state_raw = html_module.unescape(state_raw)

        try:
            review_state = json.loads(state_raw)
        except Exception:
            review_state = None


if review_state:

    print("REVIEW STATE      : FOUND")

    review_endpoint = review_state.get(
        "medleyReviewsAjaxUrl"
    )

    csrf_token = review_state.get(
        "reviewsCsrfToken"
    )

    print("REVIEW ENDPOINT   :", review_endpoint)
    print(
        "CSRF TOKEN        :",
        "FOUND" if csrf_token else "NOT FOUND"
    )

else:

    print("REVIEW STATE      : NOT FOUND")
    review_endpoint = None
    csrf_token = None


# ============================================================
# REVIEW REQUEST
# ============================================================

print("\n" + "=" * 100)
print("REVIEW REQUEST")
print("=" * 100)


if not review_endpoint:

    print("[ERROR] Amazon review endpoint was not found.")
    exit()


review_url = urljoin(
    PRODUCT_URL,
    review_endpoint
)


review_params = {
    "asin": asin,
    "pageNumber": 1,
    "reviewerType": "all_reviews",
    "filterByStar": "",
    "formatType": "",
    "mediaType": "",
    "filterByLanguage": "",
    "filterByKeyword": "",
    "sortBy": "recent",
}


review_headers = {
    **HEADERS,
    "Referer": PRODUCT_URL,
    "Accept": "*/*",
    "X-Requested-With": "XMLHttpRequest",
}


if csrf_token:
    review_params["csrfToken"] = csrf_token


print("URL:", review_url)
print("PAGE:", 1)


try:

    review_response = session.get(
        review_url,
        params=review_params,
        headers=review_headers,
        timeout=30
    )

    print("STATUS:", review_response.status_code)
    print("SIZE  :", len(review_response.text))

except Exception as e:

    print("[REQUEST ERROR]", e)
    exit()


# ============================================================
# REVIEW PARSER
# ============================================================

print("\n" + "=" * 100)
print("REVIEW PARSER")
print("=" * 100)


review_html = review_response.text

review_selector = Selector(
    text=review_html
)


# Save response for inspection

with open(
    "amazon_review_response.html",
    "w",
    encoding="utf-8"
) as f:

    f.write(review_html)


print(
    "Saved response : amazon_review_response.html"
)


# ============================================================
# FIND REVIEW CARDS
# ============================================================

review_cards = review_selector.xpath(
    '//div[@data-hook="review"]'
)

print(
    "REVIEW CARDS FOUND:",
    len(review_cards)
)


# ============================================================
# PARSE INDIVIDUAL REVIEWS
# ============================================================

reviews = []


for card in review_cards:

    # --------------------------------
    # REVIEW ID
    # --------------------------------

    review_id = card.xpath(
        './@id'
    ).get()

    # --------------------------------
    # RATING
    # --------------------------------

    rating = card.xpath(
        './/i[@data-hook="review-star-rating"]'
        '//span[@class="a-icon-alt"]/text()'
    ).get()

    if not rating:

        rating = card.xpath(
            './/i[@data-hook="cmps-review-star-rating"]'
            '//span[@class="a-icon-alt"]/text()'
        ).get()

    # --------------------------------
    # TITLE
    # --------------------------------

    title = card.xpath(
        './/a[@data-hook="review-title"]//span/text()'
    ).get()

    if not title:

        title = card.xpath(
            './/span[@data-hook="review-title"]//text()'
        ).get()

    # --------------------------------
    # REVIEW TEXT
    # --------------------------------

    review_text = card.xpath(
        './/span[@data-hook="review-body"]//text()'
    ).getall()

    review_text = " ".join(
        x.strip()
        for x in review_text
        if x.strip()
    )

    # --------------------------------
    # REVIEW DATE
    # --------------------------------

    review_date = card.xpath(
        './/span[@data-hook="review-date"]/text()'
    ).get()

    if review_date:
        review_date = review_date.strip()

    # --------------------------------
    # VERIFIED PURCHASE
    # --------------------------------

    verified = card.xpath(
        './/span[@data-hook="avp-badge"]/text()'
    ).get()

    if verified:
        verified = verified.strip()

    # --------------------------------
    # SAVE
    # --------------------------------

    reviews.append({
        "review_id": review_id,
        "rating": rating,
        "review_title": title,
        "review_text": review_text,
        "review_date": review_date,
        "verified_purchase": bool(verified),
    })


# ============================================================
# DISPLAY RESULTS
# ============================================================

print("\n" + "=" * 100)
print("REVIEWS FOUND")
print("=" * 100)


for index, review in enumerate(
    reviews[:5],
    start=1
):

    print(f"\nREVIEW #{index}")
    print("-" * 60)

    print(
        "Review ID        :",
        review["review_id"]
    )

    print(
        "Rating           :",
        review["rating"]
    )

    print(
        "Title            :",
        review["review_title"]
    )

    print(
        "Date             :",
        review["review_date"]
    )

    print(
        "Verified Purchase:",
        review["verified_purchase"]
    )

    print(
        "Text             :",
        review["review_text"][:500]
    )


# ============================================================
# FINDINGS
# ============================================================

print("\n" + "=" * 100)
print("FINDINGS")
print("=" * 100)

print(
    "Product page       :",
    "SUCCESS" if response.status_code == 200 else "FAILED"
)

print(
    "Average rating     :",
    "FOUND" if average_rating else "NOT FOUND"
)

print(
    "Total ratings      :",
    "FOUND" if total_ratings else "NOT FOUND"
)

print(
    "Star distribution  :",
    "FOUND" if star_distribution else "NOT FOUND"
)

print(
    "Review endpoint    :",
    "FOUND" if review_endpoint else "NOT FOUND"
)

print(
    "Review response    :",
    "SUCCESS" if review_response.status_code == 200 else "BLOCKED/FAILED"
)

print(
    "Review cards       :",
    len(reviews)
)

print(
    "Review HTML saved  : amazon_review_response.html"
)

print("\n" + "=" * 100)
print("FEASIBILITY TEST COMPLETE")
print("=" * 100)