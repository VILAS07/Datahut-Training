import requests
from scrapy import Selector
import json
import re
from urllib.parse import urljoin
from html import unescape


# ============================================================
# CONFIG
# ============================================================

PRODUCT_URL = "https://www.amazon.com/dp/B0GJTFXNRX"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36"
)

HEADERS = {
    "accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "upgrade-insecure-requests": "1",
    "user-agent": USER_AGENT,
}


# ============================================================
# SESSION
# ============================================================

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_text(value):
    """Clean whitespace from extracted text."""

    if not value:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def extract_first_text(selector, xpath):
    """Return first matching text."""

    value = selector.xpath(xpath).get()

    if value:
        return clean_text(value)

    return ""


def recursive_find_strings(obj, path="root"):
    """
    Recursively collect all string values from JSON.
    Used because Amazon can place HTML inside nested JSON objects.
    """

    results = []

    if isinstance(obj, dict):

        for key, value in obj.items():

            current_path = f"{path}.{key}"

            if isinstance(value, str):

                results.append(
                    {
                        "path": current_path,
                        "key": key,
                        "value": value
                    }
                )

            else:

                results.extend(
                    recursive_find_strings(
                        value,
                        current_path
                    )
                )

    elif isinstance(obj, list):

        for index, value in enumerate(obj):

            current_path = f"{path}[{index}]"

            if isinstance(value, str):

                results.append(
                    {
                        "path": current_path,
                        "key": str(index),
                        "value": value
                    }
                )

            else:

                results.extend(
                    recursive_find_strings(
                        value,
                        current_path
                    )
                )

    return results


def parse_reviews_from_html(html_content):
    """
    Parse Amazon review cards from HTML.

    Reviewer name is intentionally NOT collected.
    """

    selector = Selector(
        text=unescape(html_content)
    )

    review_cards = selector.xpath(
        '//div[@data-hook="review"]'
    )

    reviews = []

    for card in review_cards:

        # ----------------------------------------------------
        # REVIEW ID
        # ----------------------------------------------------

        review_id = card.xpath(
            './@id'
        ).get()

        if not review_id:

            review_id = card.xpath(
                './/*[@data-review-id]/@data-review-id'
            ).get()

        # ----------------------------------------------------
        # RATING
        # ----------------------------------------------------

        rating = card.xpath(
            './/i[@data-hook="review-star-rating"]'
            '//span[contains(@class,"a-icon-alt")]/text()'
        ).get()

        if not rating:

            rating = card.xpath(
                './/i[@data-hook="cmps-review-star-rating"]'
                '//span[contains(@class,"a-icon-alt")]/text()'
            ).get()

        if not rating:

            rating = card.xpath(
                './/span[contains(@class,"review-rating")]'
                '//span[contains(@class,"a-icon-alt")]/text()'
            ).get()

        rating = clean_text(rating)

        # ----------------------------------------------------
        # REVIEW TITLE
        # ----------------------------------------------------

        title_parts = card.xpath(
            './/*[@data-hook="review-title"]//text()'
        ).getall()

        title = clean_text(
            " ".join(title_parts)
        )

        # ----------------------------------------------------
        # REVIEW BODY
        # ----------------------------------------------------

        body_parts = card.xpath(
            './/*[@data-hook="review-body"]//text()'
        ).getall()

        review_text = clean_text(
            " ".join(body_parts)
        )

        # ----------------------------------------------------
        # REVIEW DATE
        # ----------------------------------------------------

        review_date = card.xpath(
            './/*[@data-hook="review-date"]/text()'
        ).get()

        review_date = clean_text(
            review_date
        )

        # ----------------------------------------------------
        # VERIFIED PURCHASE
        # ----------------------------------------------------

        verified_parts = card.xpath(
            './/*[@data-hook="avp-badge"]//text()'
        ).getall()

        verified_text = clean_text(
            " ".join(verified_parts)
        )

        verified_purchase = bool(
            verified_text
        )

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        reviews.append(
            {
                "review_id": review_id,
                "rating": rating,
                "review_title": title,
                "review_text": review_text,
                "review_date": review_date,
                "verified_purchase": verified_purchase,
            }
        )

    return reviews


# ============================================================
# HEADER
# ============================================================

print("=" * 100)
print("AMAZON - AIRTAG REVIEW FEASIBILITY CRAWLER")
print("=" * 100)


# ============================================================
# CRAWLER
# ============================================================

print("\n[PRODUCT]")
print(PRODUCT_URL)

try:

    product_response = session.get(
        PRODUCT_URL,
        timeout=30
    )

except requests.RequestException as e:

    print("[ERROR]", e)
    raise SystemExit


print("STATUS :", product_response.status_code)
print("SIZE   :", len(product_response.text))


if product_response.status_code != 200:

    print(
        "\n[ERROR] Product page request failed."
    )

    raise SystemExit


product_html = product_response.text

product_selector = Selector(
    text=product_html
)


# ============================================================
# PRODUCT PARSER
# ============================================================

print("\n" + "=" * 100)
print("PRODUCT PARSER")
print("=" * 100)


# ------------------------------------------------------------
# ASIN
# ------------------------------------------------------------

asin = product_selector.xpath(
    '//div[@id="averageCustomerReviews"]/@data-asin'
).get()

if not asin:

    asin_match = re.search(
        r'"(?:asin|ASIN)"\s*[:=]\s*["\']([A-Z0-9]{10})["\']',
        product_html
    )

    if asin_match:
        asin = asin_match.group(1)


print(
    "ASIN              :",
    asin
)


# ------------------------------------------------------------
# PRODUCT NAME
# ------------------------------------------------------------

product_name = product_selector.xpath(
    '//span[@id="productTitle"]/text()'
).get()

product_name = clean_text(
    product_name
)

print(
    "PRODUCT NAME      :",
    product_name
)


# ============================================================
# RATING
# ============================================================

print("\n" + "=" * 100)
print("RATING")
print("=" * 100)


# ------------------------------------------------------------
# AVERAGE RATING
# ------------------------------------------------------------

average_rating = product_selector.xpath(
    '//span[@data-hook="average-star-rating"]'
    '//span[contains(@class,"a-icon-alt")]/text()'
).get()

if not average_rating:

    average_rating = product_selector.xpath(
        '//span[@data-hook="rating-out-of-text"]/text()'
    ).get()

average_rating = clean_text(
    average_rating
)

print(
    "AVERAGE RATING    :",
    average_rating
)


# ------------------------------------------------------------
# TOTAL RATINGS
# ------------------------------------------------------------

total_ratings = product_selector.xpath(
    '//span[@data-hook="total-review-count"]/text()'
).get()

total_ratings = clean_text(
    total_ratings
)

print(
    "TOTAL RATINGS     :",
    total_ratings
)


# ============================================================
# STAR DISTRIBUTION
# ============================================================

print("\n" + "=" * 100)
print("STAR DISTRIBUTION")
print("=" * 100)


star_distribution = {}


for star in range(5, 0, -1):

    elements = product_selector.xpath(
        f'//a[@aria-label[contains(., "{star} stars")]]'
    )

    for element in elements:

        aria_label = element.xpath(
            './@aria-label'
        ).get()

        match = re.search(
            r'(\d+)\s*percent',
            aria_label or "",
            re.I
        )

        if match:

            star_distribution[star] = (
                match.group(1) + "%"
            )

            break


# ------------------------------------------------------------
# Fallback: use all histogram aria labels
# ------------------------------------------------------------

if len(star_distribution) < 5:

    histogram_elements = product_selector.xpath(
        '//a[contains(@aria-label,"percent of reviews")]'
    )

    for element in histogram_elements:

        aria_label = element.xpath(
            './@aria-label'
        ).get()

        match = re.search(
            r'(\d+)\s*percent of reviews have\s*(\d+)\s*stars',
            aria_label or "",
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
# REVIEW PAGE STATE
# ============================================================

print("\n" + "=" * 100)
print("REVIEW PAGE STATE")
print("=" * 100)


state_match = re.search(
    r'id="cr-state-object"'
    r'[^>]*'
    r'data-state=\'(.*?)\'',
    product_html,
    re.S
)


review_state = None


if state_match:

    raw_state = state_match.group(1)

    raw_state = unescape(
        raw_state
    )

    try:

        review_state = json.loads(
            raw_state
        )

    except json.JSONDecodeError:

        print(
            "Could not parse review state JSON."
        )


if review_state:

    print(
        "REVIEW STATE      : FOUND"
    )

    print(
        "ASIN FROM STATE   :",
        review_state.get("asin")
    )

    print(
        "LOCALE            :",
        review_state.get("locale")
    )

    print(
        "DEVICE TYPE       :",
        review_state.get("deviceType")
    )

    print(
        "REVIEWER TYPE     :",
        review_state.get("reviewerType")
    )

    print(
        "MEDLEY ENDPOINT   :",
        review_state.get(
            "medleyReviewsAjaxUrl"
        )
    )

else:

    print(
        "REVIEW STATE      : NOT FOUND"
    )


# ============================================================
# AMAZON RHF REVIEW REQUEST
# ============================================================

print("\n" + "=" * 100)
print("AMAZON REVIEW REQUEST")
print("=" * 100)


# This is the endpoint observed from the working browser request.

review_url = (
    "https://www.amazon.com/hz/rhf"
)


review_params = {

    "currentPageType":
        "CustomerReviews",

    "currentSubPageType":
        "remoteProduct",

    "excludeAsin":
        asin,

    "fieldKeywords":
        "",

    "k":
        "",

    "keywords":
        "",

    "search":
        "",

    "auditEnabled":
        "",

    "previewCampaigns":
        "",

    "forceWidgets":
        "",

    "searchAlias":
        "",

    "cardJSPresent":
        "true",
}


review_headers = {

    "accept":
        "*/*",

    "accept-language":
        "en-GB,en-US;q=0.9,en;q=0.8",

    "cache-control":
        "no-cache",

    "pragma":
        "no-cache",

    "referer":
        f"https://www.amazon.com/portal/customer-reviews/{asin}/",

    "sec-ch-ua":
        (
            '"Chromium";v="152", '
            '"Not?A_Brand";v="24", '
            '"Google Chrome";v="152"'
        ),

    "sec-ch-ua-mobile":
        "?0",

    "sec-ch-ua-platform":
        '"Linux"',

    "sec-fetch-dest":
        "empty",

    "sec-fetch-mode":
        "cors",

    "sec-fetch-site":
        "same-origin",

    "user-agent":
        USER_AGENT,

    "x-requested-with":
        "XMLHttpRequest",
}


print(
    "URL      :",
    review_url
)

print(
    "PARAMS   :",
    review_params
)


try:

    review_response = session.get(
        review_url,
        params=review_params,
        headers=review_headers,
        timeout=30
    )

except requests.RequestException as e:

    print(
        "[REVIEW REQUEST ERROR]",
        e
    )

    raise SystemExit


print(
    "STATUS   :",
    review_response.status_code
)

print(
    "SIZE     :",
    len(review_response.text)
)

print(
    "TYPE     :",
    review_response.headers.get(
        "content-type"
    )
)


# ============================================================
# SAVE RAW RESPONSE
# ============================================================

with open(
    "amazon_rhf_response.json",
    "w",
    encoding="utf-8"
) as file:

    file.write(
        review_response.text
    )


print(
    "SAVED    : amazon_rhf_response.json"
)


# ============================================================
# PARSE JSON
# ============================================================

print("\n" + "=" * 100)
print("JSON PARSER")
print("=" * 100)


if "application/json" not in (
    review_response.headers.get(
        "content-type",
        ""
    ).lower()
):

    print(
        "[WARNING] Response does not appear to be JSON."
    )

    raw_text = review_response.text

    try:

        amazon_data = json.loads(
            raw_text
        )

    except Exception:

        amazon_data = None

else:

    try:

        amazon_data = review_response.json()

    except ValueError:

        print(
            "[ERROR] Amazon response could not be decoded as JSON."
        )

        amazon_data = None


if amazon_data is None:

    print(
        "\nNo JSON data available."
    )

    raise SystemExit


print(
    "JSON TYPE:",
    type(amazon_data).__name__
)


# ============================================================
# SAVE PRETTY JSON
# ============================================================

with open(
    "amazon_rhf_pretty.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        amazon_data,
        file,
        indent=2,
        ensure_ascii=False
    )


print(
    "SAVED    : amazon_rhf_pretty.json"
)


# ============================================================
# TOP LEVEL STRUCTURE
# ============================================================

print("\n" + "=" * 100)
print("TOP LEVEL JSON STRUCTURE")
print("=" * 100)


if isinstance(
    amazon_data,
    dict
):

    print(
        "\nTOP LEVEL KEYS:"
    )

    for key in amazon_data.keys():

        print(
            " -",
            key
        )

elif isinstance(
    amazon_data,
    list
):

    print(
        "TOP LEVEL LIST LENGTH:",
        len(amazon_data)
    )


# ============================================================
# RECURSIVE STRING SEARCH
# ============================================================

print("\n" + "=" * 100)
print("SEARCHING AMAZON JSON")
print("=" * 100)


string_values = recursive_find_strings(
    amazon_data
)


print(
    "STRING VALUES FOUND:",
    len(string_values)
)


# ============================================================
# FIND REVIEW HTML / REVIEW CONTENT
# ============================================================

candidate_html = []


review_keywords = [

    "data-hook=\"review\"",
    "data-hook='review'",
    "review-body",
    "review-title",
    "review-date",
    "avp-badge",
    "review-star-rating",
    "customer-review",
]


for item in string_values:

    value = item["value"]

    value_lower = value.lower()

    score = 0

    for keyword in review_keywords:

        if keyword.lower() in value_lower:

            score += 1


    if score > 0:

        candidate_html.append(
            {
                "path": item["path"],
                "score": score,
                "value": value
            }
        )


candidate_html.sort(
    key=lambda x: x["score"],
    reverse=True
)


print(
    "CANDIDATE REVIEW STRINGS:",
    len(candidate_html)
)


# ============================================================
# SHOW CANDIDATES
# ============================================================

for index, item in enumerate(
    candidate_html[:10],
    1
):

    print(
        f"\nCANDIDATE #{index}"
    )

    print(
        "PATH:",
        item["path"]
    )

    print(
        "SCORE:",
        item["score"]
    )

    preview = item["value"]

    preview = preview.replace(
        "\n",
        " "
    )

    print(
        "PREVIEW:",
        preview[:1000]
    )


# ============================================================
# RAW REVIEW KEYWORD COUNTS
# ============================================================

print("\n" + "=" * 100)
print("RAW JSON KEYWORD COUNTS")
print("=" * 100)


raw_json = json.dumps(
    amazon_data,
    ensure_ascii=False
)


search_patterns = [

    "data-hook=\"review\"",
    "review-body",
    "review-title",
    "review-date",
    "avp-badge",
    "review-star-rating",
    "customer-review",
    "reviewId",
    "review_id",
    "Verified Purchase",

]


for pattern in search_patterns:

    count = raw_json.lower().count(
        pattern.lower()
    )

    print(
        f"{pattern:<30} : {count}"
    )


# ============================================================
# PARSE REVIEW CARDS FROM CANDIDATES
# ============================================================

print("\n" + "=" * 100)
print("REVIEW CARD EXTRACTION")
print("=" * 100)


all_reviews = []


for item in candidate_html:

    html_content = item["value"]

    parsed_reviews = parse_reviews_from_html(
        html_content
    )

    if parsed_reviews:

        print(
            "Reviews found in:",
            item["path"]
        )

        print(
            "Count:",
            len(parsed_reviews)
        )

        all_reviews.extend(
            parsed_reviews
        )


# ============================================================
# REMOVE DUPLICATES
# ============================================================

unique_reviews = []


seen = set()


for review in all_reviews:

    review_key = (

        review.get("review_id")
        or
        (
            review.get("rating", ""),
            review.get("review_title", ""),
            review.get("review_text", ""),
            review.get("review_date", "")
        )
    )

    if review_key in seen:
        continue

    seen.add(
        review_key
    )

    unique_reviews.append(
        review
    )


# ============================================================
# DISPLAY REVIEWS
# ============================================================

print("\n" + "=" * 100)
print("REVIEWS FOUND")
print("=" * 100)


print(
    "TOTAL UNIQUE REVIEWS:",
    len(unique_reviews)
)


for index, review in enumerate(
    unique_reviews[:10],
    1
):

    print(
        "\n" + "-" * 80
    )

    print(
        f"REVIEW #{index}"
    )

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
# SAVE REVIEWS
# ============================================================

with open(
    "amazon_reviews_test.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        unique_reviews,
        file,
        indent=2,
        ensure_ascii=False
    )


print(
    "\nSAVED REVIEWS:",
    "amazon_reviews_test.json"
)


# ============================================================
# FINDINGS
# ============================================================

print("\n" + "=" * 100)
print("FINDINGS")
print("=" * 100)


print(
    "Product page       :",
    "SUCCESS"
    if product_response.status_code == 200
    else "FAILED"
)


print(
    "ASIN               :",
    "FOUND"
    if asin
    else "NOT FOUND"
)


print(
    "Product name       :",
    "FOUND"
    if product_name
    else "NOT FOUND"
)


print(
    "Average rating     :",
    "FOUND"
    if average_rating
    else "NOT FOUND"
)


print(
    "Total ratings      :",
    "FOUND"
    if total_ratings
    else "NOT FOUND"
)


print(
    "Star distribution  :",
    "FOUND"
    if len(star_distribution) == 5
    else f"PARTIAL ({len(star_distribution)}/5)"
)


print(
    "Review endpoint    :",
    "FOUND"
)


print(
    "Review request     :",
    "SUCCESS"
    if review_response.status_code == 200
    else "FAILED"
)


print(
    "JSON response      :",
    "FOUND"
    if amazon_data is not None
    else "NOT FOUND"
)


print(
    "Review HTML/data   :",
    "FOUND"
    if candidate_html
    else "NOT FOUND"
)


print(
    "Individual reviews :",
    len(unique_reviews)
)


print("\nFiles generated:")
print(
    " - amazon_rhf_response.json"
)
print(
    " - amazon_rhf_pretty.json"
)
print(
    " - amazon_reviews_test.json"
)


print("\n" + "=" * 100)
print("AMAZON FEASIBILITY TEST COMPLETE")
print("=" * 100)