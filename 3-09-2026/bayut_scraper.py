from playwright.sync_api import sync_playwright
import csv
import json
import os
import re
from urllib.parse import urljoin


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://www.bayut.eg"
START_URL = "https://www.bayut.eg/en/egypt/properties-for-sale/"

CSV_FILE = "bayut_properties.csv"
CLEANED_FILE = "cleaned_data.txt"

# First run: keep TRUE.
# After one property successfully passes all 19 fields,
# change this to FALSE.
TEST_MODE = False

# RAW SCRAPE MODE:
# Missing fields are allowed. They remain empty and the property is saved.
STRICT_MODE = False


FIELDS = [
    "url",
    "reference_number",
    "id",
    "broker_display_name",
    "title",
    "property_type",
    "description",
    "location",
    "price",
    "currency",
    "bedrooms",
    "bathrooms",
    "furnished",
    "amenities",
    "details",
    "agent_name",
    "property_image_urls",
    "completion_status",
    "ownership",
]


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(text):
    if not text:
        return ""

    return re.sub(r"\s+", " ", str(text)).strip()


def initialize_csv():
    if not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0:

        with open(
            CSV_FILE,
            "w",
            newline="",
            encoding="utf-8"
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=FIELDS
            )

            writer.writeheader()


def extract_id(url):
    match = re.search(
        r"details-(\d+)",
        url
    )

    return match.group(1) if match else ""


# ============================================================
# JSON-LD
# ============================================================

def get_json_ld(page):

    docs = []

    try:

        scripts = page.locator(
            'script[type="application/ld+json"]'
        )

        for i in range(scripts.count()):

            try:

                raw = scripts.nth(i).text_content(
                    timeout=2000
                )

                if not raw:
                    continue

                data = json.loads(raw)

                if isinstance(data, list):
                    docs.extend(data)

                else:
                    docs.append(data)

            except Exception:
                continue

    except Exception:
        pass

    return docs


def get_property_jsonld(page):

    """
    Find Bayut's RealEstateListing JSON-LD
    and return:

        listing_json
        main_entity
    """

    for doc in get_json_ld(page):

        if not isinstance(doc, dict):
            continue

        graph = doc.get("@graph", [])

        if not isinstance(graph, list):
            continue

        for item in graph:

            if not isinstance(item, dict):
                continue

            if item.get("@type") == "RealEstateListing":

                main = item.get("mainEntity")

                if isinstance(main, dict):
                    return item, main

    return {}, {}


# ============================================================
# REFERENCE NUMBER
# ============================================================

def extract_reference(listing_json, page):

    # --------------------------------------------------------
    # 1. JSON-LD breadcrumb
    # --------------------------------------------------------

    try:

        breadcrumb = listing_json.get(
            "breadcrumb",
            {}
        )

        if isinstance(breadcrumb, dict):

            items = breadcrumb.get(
                "itemListElement",
                []
            )

            if isinstance(items, list):

                for item in reversed(items):

                    if not isinstance(item, dict):
                        continue

                    name = clean_text(
                        item.get("name", "")
                    )

                    if re.match(
                        r"Bayut\s*-\s*",
                        name,
                        re.I
                    ):
                        return name

    except Exception:
        pass


    # --------------------------------------------------------
    # 2. Visible page
    # --------------------------------------------------------

    try:

        body = clean_text(
            page.locator("body").inner_text()
        )

        match = re.search(
            r"(Bayut\s*-\s*[A-Za-z0-9\-]+)",
            body,
            re.I
        )

        if match:
            return match.group(1)

    except Exception:
        pass


    # --------------------------------------------------------
    # 3. Direct Reference element
    # --------------------------------------------------------

    selectors = [
        '[aria-label="Reference"]',
        'span[aria-label="Reference"]',
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)

            if locator.count() > 0:

                value = clean_text(
                    locator.first.inner_text()
                )

                if value:
                    return value

        except Exception:
            pass


    return ""


# ============================================================
# LOCATION
# ============================================================

def extract_location(main, listing_json, page):

    # --------------------------------------------------------
    # 1. Breadcrumb
    # --------------------------------------------------------

    try:

        breadcrumb = listing_json.get(
            "breadcrumb",
            {}
        )

        items = (
            breadcrumb.get("itemListElement", [])
            if isinstance(breadcrumb, dict)
            else []
        )

        names = []

        for item in items:

            if not isinstance(item, dict):
                continue

            name = clean_text(
                item.get("name", "")
            )

            if not name:
                continue

            # Remove Bayut reference
            if re.match(
                r"Bayut\s*-\s*",
                name,
                re.I
            ):
                continue

            # Remove category names
            if re.search(
                r"(properties|apartments|penthouses|villas|"
                r"townhouses|chalet|chalets|houses|duplexes|"
                r"studios|offices|shops|commercial|residential)"
                r"\s+for\s+(sale|rent)",
                name,
                re.I
            ):
                continue

            if re.search(
                r"^(Cairo|Alexandria)\s+"
                r"(Properties|Apartments|Penthouses|Villas|"
                r"Townhouses|Chalets|Houses)$",
                name,
                re.I
            ):
                continue

            if name not in names:
                names.append(name)


        if names:

            location_parts = list(
                reversed(names)
            )

            address = main.get(
                "address",
                {}
            )

            region = ""

            if isinstance(address, dict):

                region = clean_text(
                    address.get(
                        "addressRegion",
                        ""
                    )
                )

            if region:

                location_parts = [
                    x
                    for x in location_parts
                    if x.lower() != region.lower()
                ]

                location_parts.append(region)

            if location_parts:
                return ", ".join(location_parts)

    except Exception:
        pass


    # --------------------------------------------------------
    # 2. Property header
    # --------------------------------------------------------

    selectors = [
        '[aria-label="Property header"]',
        'div[aria-label="Property header"]',
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)

            if locator.count() > 0:

                value = clean_text(
                    locator.first.inner_text()
                )

                if value:
                    return value

        except Exception:
            pass


    # --------------------------------------------------------
    # 3. Visible body fallback
    # --------------------------------------------------------

    try:

        body = page.locator(
            "body"
        ).inner_text()

        lines = [
            clean_text(x)
            for x in body.splitlines()
            if clean_text(x)
        ]

        for line in lines[:150]:

            if "," not in line:
                continue

            if len(line) > 180:
                continue

            if any(
                key.lower() in line.lower()
                for key in [
                    "Cairo",
                    "New Cairo",
                    "Maadi",
                    "Alexandria",
                    "North Coast",
                    "Ras El Hekma",
                    "Matruh",
                    "Giza",
                    "October",
                    "Ain Sokhna",
                ]
            ):

                if "EGP" not in line:
                    return line

    except Exception:
        pass


    # --------------------------------------------------------
    # 4. JSON-LD address
    # --------------------------------------------------------

    try:

        address = main.get(
            "address",
            {}
        )

        if isinstance(address, dict):

            parts = []

            locality = clean_text(
                address.get(
                    "addressLocality",
                    ""
                )
            )

            region = clean_text(
                address.get(
                    "addressRegion",
                    ""
                )
            )

            if locality:
                parts.append(locality)

            if (
                region
                and region.lower()
                not in {
                    x.lower()
                    for x in parts
                }
            ):
                parts.append(region)

            if parts:
                return ", ".join(parts)

    except Exception:
        pass


    return ""


# ============================================================
# FURNISHED
# ============================================================

def extract_furnished(page):

    values = [
        "Unfurnished",
        "Furnished",
        "Partly Furnished",
    ]

    for value in values:

        try:

            locator = page.get_by_text(
                value,
                exact=True
            )

            if locator.count() > 0:

                for i in range(
                    min(locator.count(), 10)
                ):

                    try:

                        text = clean_text(
                            locator.nth(i).inner_text()
                        )

                        if text == value:
                            return value

                    except Exception:
                        continue

        except Exception:
            pass


    # --------------------------------------------------------
    # Fallback: aria-label
    # --------------------------------------------------------

    try:

        locator = page.locator(
            '[aria-label="Furnishing"]'
        )

        if locator.count() > 0:

            value = clean_text(
                locator.first.inner_text()
            )

            if value:
                return value

    except Exception:
        pass


    # --------------------------------------------------------
    # Fallback: body
    # --------------------------------------------------------

    try:

        body = clean_text(
            page.locator("body").inner_text()
        )

        match = re.search(
            r"\b(Unfurnished|Furnished|Partly Furnished)\b",
            body,
            re.I
        )

        if match:
            return match.group(1)

    except Exception:
        pass


    return ""


# ============================================================
# COMPLETION + OWNERSHIP
# ============================================================

def extract_completion_and_ownership(page):

    completion = ""
    ownership = ""

    try:

        body = clean_text(
            page.locator("body").inner_text()
        )

        # ----------------------------------------------------
        # Completion
        # ----------------------------------------------------

        completion_match = re.search(
            r"\bCompletion\b\s*:?\s*(Ready|Off-Plan)",
            body,
            re.I
        )

        if completion_match:

            completion = clean_text(
                completion_match.group(1)
            )


        # ----------------------------------------------------
        # Ownership
        # ----------------------------------------------------

        ownership_match = re.search(
            r"\bOwnership\b\s*:?\s*"
            r"(Primary|Resale|Secondary)",
            body,
            re.I
        )

        if ownership_match:

            ownership = clean_text(
                ownership_match.group(1)
            )


    except Exception:
        pass


    # --------------------------------------------------------
    # Direct selectors
    # --------------------------------------------------------

    if not completion:

        try:

            locator = page.locator(
                '[aria-label="Completion status"]'
            )

            if locator.count() > 0:

                completion = clean_text(
                    locator.first.inner_text()
                )

        except Exception:
            pass


    if not ownership:

        try:

            locator = page.locator(
                '[aria-label="Ownership"]'
            )

            if locator.count() > 0:

                ownership = clean_text(
                    locator.first.inner_text()
                )

        except Exception:
            pass


    return completion, ownership


# ============================================================
# AMENITIES
# ============================================================

def extract_amenities(page):

    """
    Current Bayut structure confirmed from the page:

        #property-amenity-dialog

            <span class="c0327f5b">
                Amenity name
            </span>

    We intentionally use the stable parent ID and the
    span element instead of depending on the hashed class.
    """

    values = []

    try:

        # ----------------------------------------------------
        # PRIMARY SELECTOR
        # ----------------------------------------------------

        locator = page.locator(
            "#property-amenity-dialog span"
        )

        count = locator.count()

        for i in range(count):

            try:

                text = clean_text(
                    locator.nth(i).inner_text(
                        timeout=1000
                    )
                )

                if not text:
                    continue

                # Ignore SVG/CSS garbage
                if re.search(
                    r"\.amenities-|fill:|stroke:|"
                    r"\{.*\}|^z$",
                    text,
                    re.I
                ):
                    continue

                # Avoid duplicate amenities
                if text not in values:
                    values.append(text)

            except Exception:
                continue


        if values:
            return ", ".join(values)


    except Exception:
        pass


    # --------------------------------------------------------
    # FALLBACK 2
    # --------------------------------------------------------

    try:

        locator = page.locator(
            "#property-amenity-dialog .c0327f5b"
        )

        for i in range(locator.count()):

            try:

                text = clean_text(
                    locator.nth(i).inner_text()
                )

                if (
                    text
                    and text not in values
                ):
                    values.append(text)

            except Exception:
                continue


        if values:
            return ", ".join(values)

    except Exception:
        pass


    # --------------------------------------------------------
    # FALLBACK 3
    # --------------------------------------------------------
    # Search all text under the dialog.
    # This is intentionally last because inner_text()
    # contains SVG/CSS noise on Bayut.

    try:

        dialog = page.locator(
            "#property-amenity-dialog"
        )

        if dialog.count() > 0:

            items = dialog.locator(
                "li"
            )

            for i in range(items.count()):

                try:

                    text = clean_text(
                        items.nth(i).inner_text()
                    )

                    if (
                        text
                        and len(text) < 150
                        and not re.search(
                            r"\.amenities-|fill:|stroke:|"
                            r"\{.*\}",
                            text,
                            re.I
                        )
                    ):

                        if text not in values:
                            values.append(text)

                except Exception:
                    continue


        if values:
            return ", ".join(values)

    except Exception:
        pass


    return ""


# ============================================================
# BROKER
# ============================================================

def extract_broker(page, main):

    # --------------------------------------------------------
    # 1. JSON-LD
    # --------------------------------------------------------

    try:

        seller = main.get(
            "seller",
            {}
        )

        if isinstance(seller, dict):

            member_of = seller.get(
                "memberOf",
                {}
            )

            if isinstance(member_of, dict):

                broker = clean_text(
                    member_of.get(
                        "name",
                        ""
                    )
                )

                if broker:
                    return broker

    except Exception:
        pass


    # --------------------------------------------------------
    # 2. Current Bayut agency element
    # --------------------------------------------------------

    selectors = [
        '[aria-label="Agency name"]',
        'span[aria-label="Agency name"]',
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)

            if locator.count() > 0:

                for i in range(
                    min(locator.count(), 10)
                ):

                    try:

                        value = clean_text(
                            locator.nth(i).inner_text()
                        )

                        if value:
                            return value

                    except Exception:
                        continue

        except Exception:
            pass


    return ""


# ============================================================
# AGENT
# ============================================================

def extract_agent(page, main):

    """
    IMPORTANT:

    Do NOT use broker/company as agent.

    If an actual individual agent cannot be found,
    return an empty string so strict validation skips
    the property.
    """

    broker = ""

    # --------------------------------------------------------
    # 1. JSON-LD seller
    # --------------------------------------------------------

    try:

        seller = main.get(
            "seller",
            {}
        )

        if isinstance(seller, dict):

            seller_name = clean_text(
                seller.get(
                    "name",
                    ""
                )
            )

            member_of = seller.get(
                "memberOf",
                {}
            )

            if isinstance(member_of, dict):

                broker = clean_text(
                    member_of.get(
                        "name",
                        ""
                    )
                )

            # Only accept seller as agent if it is
            # different from broker.
            if (
                seller_name
                and seller_name.lower()
                != broker.lower()
            ):
                return seller_name

    except Exception:
        pass


    # --------------------------------------------------------
    # 2. Direct Agent selector
    # --------------------------------------------------------

    selectors = [
        'a[aria-label="Agent name"]',
        '[aria-label="Agent name"]',
    ]

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            )

            if locator.count() > 0:

                for i in range(
                    min(locator.count(), 10)
                ):

                    try:

                        value = clean_text(
                            locator.nth(i).inner_text()
                        )

                        if (
                            value
                            and value.lower()
                            != broker.lower()
                        ):
                            return value

                    except Exception:
                        continue

        except Exception:
            pass


    # --------------------------------------------------------
    # 3. Search visible agent card
    # --------------------------------------------------------

    try:

        body = page.locator(
            "body"
        ).inner_text()

        lines = [
            clean_text(x)
            for x in body.splitlines()
            if clean_text(x)
        ]

        # Words that normally indicate a company,
        # section, button, or unrelated text.
        excluded = re.compile(
            r"(Property|Properties|Real Estate|"
            r"Developments|Compound|Homes|Home|"
            r"Broker|Agent|Egypt|Cairo|Responsive|"
            r"Email|Call|View|Green|Avenue|"
            r"Estate|Realty|Group|Development)",
            re.I
        )

        candidates = []

        for i, line in enumerate(lines):

            if not line:
                continue

            if line.lower() == broker.lower():
                continue

            if not (2 <= len(line.split()) <= 5):
                continue

            if len(line) > 80:
                continue

            if excluded.search(line):
                continue

            # Avoid obvious UI labels
            if re.fullmatch(
                r"(Responsive Broker|SuperAgent|"
                r"Agent|Broker|Email|Call|"
                r"View all properties)",
                line,
                re.I
            ):
                continue

            candidates.append(
                (i, line)
            )


        # Prefer candidates near agent/broker labels.
        keywords = re.compile(
            r"(Responsive Broker|SuperAgent|"
            r"Agent|Broker)",
            re.I
        )

        for i, line in enumerate(lines):

            if not keywords.search(line):
                continue

            nearby = candidates

            for candidate_index, candidate_name in nearby:

                if abs(candidate_index - i) <= 5:

                    if (
                        candidate_name.lower()
                        != broker.lower()
                    ):
                        return candidate_name

    except Exception:
        pass


    # --------------------------------------------------------
    # VERY IMPORTANT:
    # Do NOT return broker here.
    # --------------------------------------------------------

    return ""


# ============================================================
# IMAGES
# ============================================================

def extract_images(page, main):

    images = []

    # --------------------------------------------------------
    # 1. JSON-LD images
    # --------------------------------------------------------

    try:

        raw_images = main.get(
            "image",
            []
        )

        if isinstance(raw_images, str):
            raw_images = [raw_images]

        if isinstance(raw_images, list):

            for image in raw_images:

                if not isinstance(image, str):
                    continue

                image = image.strip()

                if not image:
                    continue

                if "images.bayut.eg" not in image:
                    continue

                # Prefer 800x600 images
                if "800x600" in image:

                    if image not in images:
                        images.append(image)

    except Exception:
        pass


    # --------------------------------------------------------
    # 2. DOM fallback
    # --------------------------------------------------------

    if not images:

        selectors = [
            'picture source[srcset*="800x600"]',
            'img[src*="800x600"]',
            'img[srcset*="800x600"]',
        ]

        for selector in selectors:

            try:

                locator = page.locator(
                    selector
                )

                for i in range(
                    locator.count()
                ):

                    try:

                        srcset = locator.nth(i).get_attribute(
                            "srcset"
                        )

                        src = locator.nth(i).get_attribute(
                            "src"
                        )

                        candidate = (
                            srcset
                            or src
                            or ""
                        )

                        # srcset may contain multiple
                        # URLs. Take first URL.
                        if candidate:

                            candidate = candidate.split(",")[0].strip()

                            candidate = candidate.split(" ")[0].strip()

                        if (
                            candidate
                            and "images.bayut.eg"
                            in candidate
                        ):

                            if candidate not in images:
                                images.append(candidate)

                    except Exception:
                        continue

                if images:
                    break

            except Exception:
                continue


    return images


# ============================================================
# PROPERTY EXTRACTION
# ============================================================

def extract_property(page):

    url = page.url

    property_id = extract_id(
        url
    )

    listing, main = get_property_jsonld(
        page
    )


    # --------------------------------------------------------
    # Initialize
    # --------------------------------------------------------

    title = ""
    property_type = ""
    description = ""
    price = ""
    currency = ""
    bedrooms = ""
    bathrooms = ""
    details = ""
    broker_display_name = ""
    agent_name = ""


    # --------------------------------------------------------
    # JSON-LD
    # --------------------------------------------------------

    if listing:

        # H1
        try:

            title = clean_text(
                page.locator(
                    "h1"
                ).first.inner_text()
            )

        except Exception:
            pass


        # Property type
        property_type = clean_text(
            main.get(
                "accommodationCategory",
                ""
            )
        )


        # Description
        description = clean_text(
            main.get(
                "description",
                ""
            )
        )


        # Price
        raw_price = main.get(
            "price"
        )

        if raw_price is not None:

            price = clean_text(
                str(raw_price)
            )


        # Currency
        currency = clean_text(
            main.get(
                "priceCurrency",
                ""
            )
        )


        # Bedrooms
        raw_bedrooms = main.get(
            "numberOfBedrooms"
        )

        if raw_bedrooms is not None:

            bedrooms = clean_text(
                str(raw_bedrooms)
            )


        # Bathrooms
        raw_bathrooms = main.get(
            "numberOfBathroomsTotal"
        )

        if raw_bathrooms is not None:

            bathrooms = clean_text(
                str(raw_bathrooms)
            )


        # Area
        floor_size = main.get(
            "floorSize"
        )

        if isinstance(
            floor_size,
            dict
        ):

            value = clean_text(
                floor_size.get(
                    "value",
                    ""
                )
            )

            unit = clean_text(
                floor_size.get(
                    "unitText",
                    ""
                )
            )

            if value:

                # Bayut normally uses Sq. M.
                if unit:
                    details = f"{value} Sq. M."
                else:
                    details = f"{value} Sq. M."

        elif floor_size:

            details = clean_text(
                str(floor_size)
            )


    # --------------------------------------------------------
    # Broker + agent
    # --------------------------------------------------------

    broker_display_name = extract_broker(
        page,
        main
    )

    agent_name = extract_agent(
        page,
        main
    )


    # --------------------------------------------------------
    # Visible fallbacks
    # --------------------------------------------------------

    if not title:

        try:

            title = clean_text(
                page.locator(
                    "h1"
                ).first.inner_text()
            )

        except Exception:
            pass


    # --------------------------------------------------------
    # Completion / ownership
    # --------------------------------------------------------

    completion_status, ownership = (
        extract_completion_and_ownership(
            page
        )
    )


    # --------------------------------------------------------
    # Furnished
    # --------------------------------------------------------

    furnished = extract_furnished(
        page
    )


    # --------------------------------------------------------
    # Amenities
    # --------------------------------------------------------

    amenities = extract_amenities(
        page
    )


    # --------------------------------------------------------
    # Images
    # --------------------------------------------------------

    images = extract_images(
        page,
        main
    )


    # ========================================================
    # VISIBLE PAGE FALLBACKS
    # ========================================================

    try:

        body = clean_text(
            page.locator(
                "body"
            ).inner_text()
        )


        # ----------------------------------------------------
        # Price
        # ----------------------------------------------------

        if not price:

            m = re.search(
                r"\bEGP\s*([\d,]+)",
                body,
                re.I
            )

            if m:

                price = (
                    m.group(1)
                    .replace(",", "")
                )


        # ----------------------------------------------------
        # Bedrooms
        # ----------------------------------------------------

        if not bedrooms:

            m = re.search(
                r"\b(\d+)\s+Beds?\b",
                body,
                re.I
            )

            if m:
                bedrooms = m.group(1)


        # ----------------------------------------------------
        # Bathrooms
        # ----------------------------------------------------

        if not bathrooms:

            m = re.search(
                r"\b(\d+)\s+Baths?\b",
                body,
                re.I
            )

            if m:
                bathrooms = m.group(1)


        # ----------------------------------------------------
        # Details
        # ----------------------------------------------------

        if not details:

            m = re.search(
                r"\b([\d,.]+)\s+Sq\.\s*M\.",
                body,
                re.I
            )

            if m:

                details = (
                    f"{m.group(1)} Sq. M."
                )


        # ----------------------------------------------------
        # Currency
        # ----------------------------------------------------

        if not currency:

            if re.search(
                r"\bEGP\b",
                body,
                re.I
            ):
                currency = "EGP"


    except Exception:
        pass


    # ========================================================
    # RETURN EXACTLY 19 FIELDS
    # ========================================================

    return {

        "url": url,

        "reference_number": extract_reference(
            listing,
            page
        ),

        "id": property_id,

        "broker_display_name":
            broker_display_name,

        "title": title,

        "property_type":
            property_type,

        "description":
            description,

        "location":
            extract_location(
                main,
                listing,
                page
            ),

        "price":
            price,

        "currency":
            currency,

        "bedrooms":
            bedrooms,

        "bathrooms":
            bathrooms,

        "furnished":
            furnished,

        "amenities":
            amenities,

        "details":
            details,

        "agent_name":
            agent_name,

        "property_image_urls":
            images,

        "completion_status":
            completion_status,

        "ownership":
            ownership,
    }


# ============================================================
# CLEAN DATA
# ============================================================

def clean_final_data(data):

    """
    Clean values without inventing missing information.

    Missing values stay empty.

    Strict validation happens afterward.
    """

    cleaned = {}

    for field in FIELDS:

        value = data.get(
            field
        )


        # ----------------------------------------------------
        # Images
        # ----------------------------------------------------

        if field == "property_image_urls":

            if isinstance(
                value,
                list
            ):

                images = [
                    clean_text(x)
                    for x in value
                    if clean_text(x)
                ]

                cleaned[field] = images

            else:

                cleaned[field] = []

            continue


        # ----------------------------------------------------
        # Normal fields
        # ----------------------------------------------------

        text = clean_text(
            value
        )

        if text.lower() in {
            "none",
            "null",
            "nan",
            "not specified",
        }:

            text = ""


        cleaned[field] = text


    # --------------------------------------------------------
    # Price formatting
    # --------------------------------------------------------

    if cleaned["price"]:

        raw = cleaned["price"].replace(
            ",",
            ""
        )

        if re.fullmatch(
            r"\d+(?:\.\d+)?",
            raw
        ):

            try:

                if "." in raw:

                    cleaned["price"] = (
                        f"{float(raw):,.2f}"
                        .rstrip("0")
                        .rstrip(".")
                    )

                else:

                    cleaned["price"] = (
                        f"{int(raw):,}"
                    )

            except Exception:
                pass


    return cleaned


# ============================================================
# STRICT VALIDATION
# ============================================================

def validate_property(data):

    """
    Property is valid ONLY if every one of the
    19 required fields has a real value.
    """

    missing = []

    for field in FIELDS:

        value = data.get(
            field
        )


        # ----------------------------------------------------
        # Images
        # ----------------------------------------------------

        if field == "property_image_urls":

            if (
                not isinstance(
                    value,
                    list
                )
                or not value
            ):

                missing.append(
                    field
                )

            continue


        # ----------------------------------------------------
        # Normal fields
        # ----------------------------------------------------

        if value is None:

            missing.append(
                field
            )

            continue


        text = clean_text(
            value
        )


        if (
            not text
            or text.lower()
            in {
                "null",
                "none",
                "nan",
                "not specified",
            }
        ):

            missing.append(
                field
            )


    return (
        len(missing) == 0,
        missing
    )


# ============================================================
# CSV ROW
# ============================================================

def csv_row(data):

    row = dict(
        data
    )

    row["property_image_urls"] = json.dumps(
        data["property_image_urls"],
        ensure_ascii=False
    )

    return row


# ============================================================
# SAVE
# ============================================================

def save_data(data):

    data = clean_final_data(
        data
    )


    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    with open(
        CSV_FILE,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=FIELDS
        )

        writer.writerow(
            csv_row(data)
        )


    # --------------------------------------------------------
    # cleaned_data.txt
    # --------------------------------------------------------

    with open(
        CLEANED_FILE,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            json.dumps(
                data,
                ensure_ascii=False
            )
            + "\n"
        )


# ============================================================
# DUPLICATE CHECK
# ============================================================

def already_scraped(url):

    if not os.path.exists(
        CSV_FILE
    ):
        return False


    try:

        with open(
            CSV_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            for row in csv.DictReader(f):

                if row.get(
                    "url"
                ) == url:

                    return True


    except Exception:
        pass


    return False


# ============================================================
# CAPTCHA
# ============================================================

def handle_captcha(page):

    try:

        if (
            "captcha"
            in page.url.lower()
            or "captcha"
            in page.title().lower()
        ):

            print(
                "\n⚠️ CAPTCHA detected."
            )

            print(
                "Solve it manually in the browser."
            )

            input(
                "\nPress ENTER after solving CAPTCHA... "
            )

            page.wait_for_timeout(
                3000
            )

            print(
                "Current URL:",
                page.url
            )

    except Exception:
        pass


# ============================================================
# PROPERTY URLS
# ============================================================

def get_property_urls(page):

    links = page.locator(
        'a[href*="/property/details-"]'
    )

    urls = []


    for i in range(
        links.count()
    ):

        try:

            href = links.nth(i).get_attribute(
                "href"
            )

            if not href:
                continue


            href = urljoin(
                BASE_URL,
                href
            )


            if (
                "/property/details-"
                in href
                and href not in urls
            ):

                urls.append(
                    href
                )


        except Exception:
            pass


    return urls


# ============================================================
# FIND NEXT BUTTON
# ============================================================

def find_next_button(page):
    """Find Bayut's pagination Next button using several selectors."""

    selectors = [
        'a[title="Next"]',
        'button[title="Next"]',
        'a[aria-label="Next"]',
        'button[aria-label="Next"]',
        'a[aria-label="Next page"]',
        'button[aria-label="Next page"]',
        'a:has-text("Next")',
        'button:has-text("Next")',
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector)

            for i in range(locator.count()):
                candidate = locator.nth(i)

                if candidate.is_visible():
                    return candidate

        except Exception:
            continue

    # Fallback: look near the bottom for an arrow button.
    try:
        candidates = page.locator("a, button")
        visible_candidates = []

        viewport = page.viewport_size or {"height": 768}
        height = viewport.get("height", 768)

        for i in range(candidates.count()):
            try:
                candidate = candidates.nth(i)

                if not candidate.is_visible():
                    continue

                box = candidate.bounding_box()
                if not box:
                    continue

                if box["y"] < height * 0.5:
                    continue

                text = clean_text(candidate.inner_text())
                aria = clean_text(
                    candidate.get_attribute("aria-label") or ""
                )
                title = clean_text(
                    candidate.get_attribute("title") or ""
                )

                combined = f"{text} {aria} {title}".lower()

                if "next" in combined:
                    return candidate

                svg_count = candidate.locator("svg").count()

                if not text and svg_count > 0:
                    visible_candidates.append(candidate)

            except Exception:
                continue

        if visible_candidates:
            return visible_candidates[-1]

    except Exception:
        pass

    return None


# ============================================================
# CLICK NEXT PAGE
# ============================================================

def click_next_page(page):
    """Scroll to the bottom, click Next, and verify a new listing page."""

    print("\n⬇️ Scrolling to bottom of listing page...")

    try:
        page.evaluate(
            """
            window.scrollTo({
                top: document.body.scrollHeight,
                behavior: 'instant'
            });
            """
        )
    except Exception:
        pass

    page.wait_for_timeout(2500)
    print("✅ Reached bottom.")

    old_urls = get_property_urls(page)
    old_url = page.url

    next_button = find_next_button(page)

    if not next_button:
        print("❌ Next page button not found.")
        return False

    # Check disabled state.
    try:
        if next_button.is_disabled():
            print("🏁 Next button is disabled.")
            return False
    except Exception:
        pass

    try:
        aria_disabled = (
            next_button.get_attribute("aria-disabled") or ""
        ).lower()
        class_name = (
            next_button.get_attribute("class") or ""
        ).lower()

        if aria_disabled == "true" or "disabled" in class_name:
            print("🏁 Next button is disabled.")
            return False

    except Exception:
        pass

    print("\n➡️ Clicking NEXT page...")

    try:
        next_button.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        next_button.click(timeout=10000)
    except Exception as e:
        print("❌ Could not click Next:", e)
        return False

    # Give Bayut time to navigate/update.
    page.wait_for_timeout(3000)

    try:
        page.wait_for_function(
            "oldUrl => window.location.href !== oldUrl",
            old_url,
            timeout=10000,
        )
    except Exception:
        pass

    page.wait_for_timeout(3000)
    handle_captcha(page)
    page.wait_for_timeout(2000)

    new_urls = get_property_urls(page)

    if new_urls and new_urls != old_urls:
        print("\n✅ Next listing page loaded.")
        print("Current listing URL:", page.url)
        print(f"Found {len(new_urls)} properties on new page.")
        return True

    if page.url != old_url:
        print("\n✅ Listing URL changed.")
        print("Current listing URL:", page.url)
        return True

    page.wait_for_timeout(3000)
    new_urls = get_property_urls(page)

    if new_urls and new_urls != old_urls:
        print("\n✅ Next listing page loaded.")
        print(f"Found {len(new_urls)} properties.")
        return True

    print("\n❌ Next page did not appear to load.")
    return False


# ============================================================
# MAIN
# ============================================================

with sync_playwright() as p:

    initialize_csv()

    print("\n" + "=" * 70)
    print("🚀 BAYUT PROPERTY SCRAPER - RAW DATA MODE")
    print("=" * 70)
    print("\nStrict mode:", STRICT_MODE)
    print("Test mode:", TEST_MODE)
    print("Missing fields will be saved as empty values.")

    browser = p.chromium.launch(
        headless=False
    )

    page = browser.new_page(
        viewport={
            "width": 1366,
            "height": 768,
        }
    )

    # ========================================================
    # OPEN FIRST LISTING PAGE
    # ========================================================

    print("\n🌐 Opening listing page...")

    page.goto(
        START_URL,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    page.wait_for_timeout(5000)
    handle_captcha(page)
    page.wait_for_timeout(2000)

    # ========================================================
    # PAGINATION LOOP
    # ========================================================

    page_number = 1

    while True:

        print("\n" + "#" * 70)
        print(f"📄 LISTING PAGE {page_number}")
        print("#" * 70)

        # If something unexpectedly left us on a property page,
        # return to the current listing URL.
        if "/property/details-" in page.url:
            print("⬅️ Current page is a property.")
            print("Returning to listing page...")

            try:
                page.goto(
                    START_URL,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                page.wait_for_timeout(4000)
                handle_captcha(page)
                page.wait_for_timeout(2000)
            except Exception as e:
                print("❌ Could not return to listing:", e)
                break

        listing_page_url = page.url

        print("Listing URL:", listing_page_url)

        property_urls = get_property_urls(page)

        print(
            f"\nFound {len(property_urls)} properties "
            f"on listing page {page_number}."
        )

        if not property_urls:
            print("❌ No property URLs found.")
            print("Stopping scraper.")
            break

        if TEST_MODE:
            print("\n🧪 TEST MODE: only the first property will be tested.")
            property_urls = property_urls[:1]

        # ====================================================
        # PROCESS CURRENT LISTING PAGE
        # ====================================================

        for index, property_url in enumerate(
            property_urls,
            start=1,
        ):

            print("\n" + "=" * 70)
            print(
                f"LISTING PAGE {page_number} | "
                f"PROPERTY {index}/{len(property_urls)}"
            )
            print("=" * 70)

            if already_scraped(property_url):
                print("Already exists in CSV. Skipping.")
                continue

            print("Opening:", property_url)

            try:
                page.goto(
                    property_url,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
            except Exception as e:
                print("❌ Navigation error:", e)
                continue

            page.wait_for_timeout(4000)
            handle_captcha(page)
            page.wait_for_timeout(2000)

            print("Current URL:", page.url)

            if "/property/details-" not in page.url:
                print("❌ Not on a property details page.")
                print("➡️ Moving to next property...")
                continue

            try:
                data = extract_property(page)
            except Exception as e:
                print("❌ Extraction error:", e)
                continue

            data = clean_final_data(data)

            # ====================================================
            # DISPLAY 19 FIELDS
            # ====================================================

            print("\n===== 19 FIELDS =====")

            for number, field in enumerate(FIELDS, 1):
                value = data[field]

                if field == "property_image_urls":
                    print(
                        f"{number}. {field}: "
                        f"{len(value)} images"
                    )

                    for image in value:
                        print("   ", image)
                else:
                    print(f"{number}. {field}: {value}")

            # ====================================================
            # CHECK COMPLETENESS - DO NOT SKIP
            # ====================================================

            valid, missing_fields = validate_property(data)

            if missing_fields:
                print("\n⚠️ PROPERTY HAS MISSING FIELDS")
                for field in missing_fields:
                    print(f"   ❌ {field}")
            else:
                print("\n✅ ALL 19 FIELDS PRESENT")

            # ====================================================
            # SAVE RAW DATA REGARDLESS OF MISSING FIELDS
            # ====================================================

            save_data(data)

            print("\n💾 PROPERTY SAVED")
            print("CSV:", CSV_FILE)
            print("TXT:", CLEANED_FILE)

            if TEST_MODE:
                print("\n🧪 ONE-PROPERTY TEST FINISHED.")
                break

        if TEST_MODE:
            print("\n🧪 TEST MODE COMPLETE.")
            break

        # ====================================================
        # RETURN TO CURRENT LISTING PAGE
        # ====================================================

        print("\n⬅️ Returning to listing page...")

        try:
            page.goto(
                listing_page_url,
                wait_until="domcontentloaded",
                timeout=60000,
            )
        except Exception as e:
            print("❌ Could not return to listing page:", e)
            break

        page.wait_for_timeout(4000)
        handle_captcha(page)
        page.wait_for_timeout(2000)

        # ====================================================
        # NEXT LISTING PAGE
        # ====================================================

        if not click_next_page(page):
            print("\n🏁 No more listing pages. Scraper finished.")
            break

        page_number += 1

    # ========================================================
    # FINISHED
    # ========================================================

    print("\n" + "=" * 70)
    print("🚀 BAYUT RAW SCRAPER FINISHED")
    print("=" * 70)

    print(
        "CSV:",
        os.path.abspath(CSV_FILE),
    )

    print(
        "TXT:",
        os.path.abspath(CLEANED_FILE),
    )

    input("\nPress ENTER to close browser... ")
    browser.close()
