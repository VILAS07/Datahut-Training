import json
import re
from urllib.parse import urljoin

from parsel import Selector

from items import PropertyItem
from settings import BASE_URL, REQUEST_TIMEOUT


class Parser:

    def clean(self, value):
        if value is None:
            return ""

        if isinstance(value, (dict, list)):
            return value

        value = re.sub(r"\s+", " ", str(value))
        return value.strip()

    def extract_json_ld(self, selector):
        """
        Extract the RealEstateListing JSON-LD object.
        """

        scripts = selector.xpath(
            "//script[@type='application/ld+json']/text()"
        ).getall()

        for script in scripts:

            script = script.strip()

            if not script:
                continue

            try:
                data = json.loads(script)
            except Exception:
                continue

            objects = []

            if isinstance(data, list):
                objects.extend(data)

            elif isinstance(data, dict):

                if isinstance(data.get("@graph"), list):
                    objects.extend(
                        data["@graph"]
                    )

                else:
                    objects.append(data)

            for obj in objects:

                if not isinstance(obj, dict):
                    continue

                obj_type = obj.get("@type", "")

                if isinstance(obj_type, list):
                    types = obj_type
                else:
                    types = [obj_type]

                if (
                    "RealEstateListing" in types
                    or "RealEstateListing" == obj_type
                ):
                    return obj

        return {}

    def get_json_value(self, data, key):
        """
        Safely retrieve a JSON-LD value.
        """

        value = data.get(key, "")

        if isinstance(value, list):

            if value:
                return value[0]

            return ""

        if isinstance(value, dict):
            return value

        return value

    def extract_license_section(self, body_text):
        """
        Extract Haraj's licensed-property section.
        """

        markers = [
            "معلومات العقارحسب الرخصة",
            "معلومات العقار حسب الرخصة",
            "Property Information according to the license",
            "Property information according to the license",
        ]

        start = -1

        for marker in markers:

            index = body_text.lower().find(
                marker.lower()
            )

            if index != -1:

                if start == -1 or index < start:
                    start = index

        if start == -1:
            return ""

        section = body_text[start:]

        stop_markers = [
            "Similar ads",
            "Similar Ads",
            "إعلانات مشابهة",
        ]

        positions = []

        for marker in stop_markers:

            index = section.lower().find(
                marker.lower()
            )

            if index != -1:
                positions.append(index)

        if positions:
            section = section[
                :min(positions)
            ]

        return section

    def get_license_value(
        self,
        text,
        labels,
        stop_labels=None
    ):
        """
        Extract one value from the license section.
        """

        if not text:
            return ""

        if stop_labels is None:

            stop_labels = [
                "Purpose of advertisement",
                "Unit price",
                "Property type",
                "Property age",
                "Property area",
                "Property facade",
                "Number of rooms",
                "Plan number",
                "Plot number",
                "Street width",
                "Property uses",
                "Property services",
                "Services",
                "Guarantees and duration",
                "Other obligations",
                "Description of property location",
                "License owner",
                "License expiry",
                "Advertiser number",
                "Authorization number",

                "غرض الإعلان",
                "سعر الوحدة",
                "نوع العقار",
                "عمر العقار",
                "مساحة العقار",
                "واجهة العقار",
                "عدد الغرف",
                "رقم المخطط",
                "رقم القطعة",
                "عرض الشارع",
                "استخدامات العقار",
                "خدمات العقار",
                "الضمانات ومدتها",
                "الالتزامات الآخرى على العقار",
                "وصف موقع العقار",
                "مالك الرخصة",
                "انتهاء الرخصة",
                "رقم المعلن",
                "رقم التصريح",
            ]

        label_pattern = "|".join(
            re.escape(label)
            for label in labels
        )

        stop_pattern = "|".join(
            re.escape(label)
            for label in stop_labels
        )

        pattern = (
            rf"(?:{label_pattern})"
            rf"\s*[:：]?\s*"
            rf"(.*?)"
            rf"(?=\s*(?:{stop_pattern})"
            rf"\s*[:：]?|$)"
        )

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL
        )

        if not match:
            return ""

        return self.clean(
            match.group(1)
        )

    def extract_location(self, license_section):
        """
        Extract location from the license section.
        """

        return self.get_license_value(
            license_section,
            [
                "Description of property location",
                "وصف موقع العقار",
            ]
        )

    def extract_city_district(
        self,
        location,
        description=""
    ):
        """
        Extract city and district.

        Examples:

        Tabuk Region, Tbwk, An Nazim
        -> Tbwk / An Nazim

        Eastern Region, Khobar, Al Khur
        -> Khobar / Al Khur

        City: Jeddah
        Neighborhood: Al-Bawadi
        -> Jeddah / Al-Bawadi
        """

        location = self.clean(
            location
        )

        if not location:
            location = ""

        city = ""
        district = ""

        # ---------------------------------------------
        # Explicit City / District labels
        # ---------------------------------------------

        city_match = re.search(
            r"(?:City|المدينة)"
            r"\s*[:：]\s*"
            r"([^,\n]+)",
            location,
            flags=re.IGNORECASE
        )

        district_match = re.search(
            r"(?:District|Neighborhood|الحي)"
            r"\s*[:：]\s*"
            r"([^,\n]+)",
            location,
            flags=re.IGNORECASE
        )

        if city_match:
            city = self.clean(
                city_match.group(1)
            )

        if district_match:
            district = self.clean(
                district_match.group(1)
            )

        if city or district:
            return city, district

        # ---------------------------------------------
        # Search description for explicit location
        # ---------------------------------------------

        city_match = re.search(
            r"(?:City|المدينة)"
            r"\s*[:：]\s*"
            r"([^,\n]+)",
            description,
            flags=re.IGNORECASE
        )

        district_match = re.search(
            r"(?:District|Neighborhood|الحي)"
            r"\s*[:：]\s*"
            r"([^,\n]+)",
            description,
            flags=re.IGNORECASE
        )

        if city_match:
            city = self.clean(
                city_match.group(1)
            )

        if district_match:
            district = self.clean(
                district_match.group(1)
            )

        if city or district:
            return city, district

        # ---------------------------------------------
        # Arabic format
        # ---------------------------------------------

        arabic_match = re.search(
            r"حي\s+(.+?)"
            r"\s+بمدينة\s+(.+?)(?:\.|$)",
            location
        )

        if arabic_match:

            district = self.clean(
                arabic_match.group(1)
            )

            city = self.clean(
                arabic_match.group(2)
            )

            return city, district

        # ---------------------------------------------
        # Comma-separated location
        # ---------------------------------------------

        parts = [
            self.clean(part)
            for part in location.split(",")
            if self.clean(part)
        ]

        if len(parts) >= 3:

            return (
                parts[-2],
                parts[-1]
            )

        if len(parts) == 2:

            return (
                parts[-1],
                ""
            )

        return "", ""

    def extract_price(self, description):
        """
        Extract asking price from the actual description.
        """

        if not description:
            return ""

        patterns = [

            r"(?:Asking\s+price)"
            r"\s*[:：]\s*"
            r"(.+?)(?=\n|$)",

            r"(?:Price)"
            r"\s*[:：]\s*"
            r"(.+?)(?=\n|$)",

            r"(?:السعر)"
            r"\s*[:：]\s*"
            r"(.+?)(?=\n|$)",

            r"(?:سعر\s+البيع)"
            r"\s*[:：]\s*"
            r"(.+?)(?=\n|$)",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                description,
                flags=re.IGNORECASE
            )

            if match:

                value = self.clean(
                    match.group(1)
                )

                # Remove obvious trailing text
                value = re.split(
                    r"\b(?:License holder|License expiration|Guarantees|Description of the property location)\b",
                    value,
                    flags=re.IGNORECASE
                )[0]

                return self.clean(value)

        return ""

    def extract_map_url(self, text):
        """
        Extract Google Maps URL.
        """

        patterns = [
            r"https?://maps\.google\.com/[^\s]+",
            r"https?://maps\.app\.goo\.gl/[^\s]+",
            r"https?://goo\.gl/maps/[^\s]+",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE
            )

            if match:

                return match.group(
                    0
                ).rstrip(
                    ".,);]"
                )

        return ""

    def extract_images(
        self,
        listing,
        page
    ):
        """
        Prefer images from RealEstateListing JSON-LD.
        """

        images = []

        json_images = listing.get(
            "image",
            []
        )

        if isinstance(
            json_images,
            str
        ):
            json_images = [
                json_images
            ]

        if isinstance(
            json_images,
            list
        ):

            for image in json_images:

                if not isinstance(
                    image,
                    str
                ):
                    continue

                image = urljoin(
                    BASE_URL,
                    image
                )

                if image not in images:
                    images.append(
                        image
                    )

        # Fallback to page images
        if not images:

            try:

                page_images = page.locator(
                    "img"
                ).evaluate_all(
                    """
                    imgs => imgs
                        .map(img =>
                            img.src ||
                            img.getAttribute('src')
                        )
                        .filter(Boolean)
                    """
                )

                for image in page_images:

                    image = urljoin(
                        BASE_URL,
                        image
                    )

                    if (
                        "haraj.com.sa"
                        in image
                        and image not in images
                    ):
                        images.append(
                            image
                        )

            except Exception:
                pass

        return images

    def parse(self, page, url):

        print(
            f"Parsing: {url}"
        )

        try:

            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=REQUEST_TIMEOUT * 1000
            )

            if response:

                print(
                    f"Parser status: "
                    f"{response.status}"
                )

            page.wait_for_timeout(
                1500
            )

        except Exception as e:

            print(
                f"Parser page error: {e}"
            )

            return None

        # ---------------------------------------------
        # HTML
        # ---------------------------------------------

        html = page.content()

        selector = Selector(
            text=html
        )

        body_text = self.clean(
            " ".join(
                selector.xpath(
                    "//body//text()"
                ).getall()
            )
        )

        # ---------------------------------------------
        # JSON-LD
        # ---------------------------------------------

        listing = self.extract_json_ld(
            selector
        )

        # ---------------------------------------------
        # AD ID
        # ---------------------------------------------

        ad_match = re.search(
            r"/(?:en/)?(\d+)(?:/|$)",
            url
        )

        ad_id = (
            ad_match.group(1)
            if ad_match
            else ""
        )

        # ---------------------------------------------
        # TITLE
        # ---------------------------------------------

        title = self.clean(
            listing.get(
                "name",
                ""
            )
        )

        if not title:

            title = self.clean(
                selector.xpath(
                    "//meta[@property='og:title']/@content"
                ).get()
                or ""
            )

        if not title:

            title = self.clean(
                selector.xpath(
                    "//title/text()"
                ).get()
                or ""
            )

        # ---------------------------------------------
        # DESCRIPTION
        # ---------------------------------------------

        description = self.clean(
            listing.get(
                "description",
                ""
            )
        )

        # Decode HTML entities
        description = (
            description
            .replace(
                "&ndash;",
                "-"
            )
            .replace(
                "&amp;",
                "&"
            )
            .replace(
                "&nbsp;",
                " "
            )
        )

        # ---------------------------------------------
        # SELLER
        # ---------------------------------------------

        seller = ""

        offers = listing.get(
            "offers",
            {}
        )

        if isinstance(
            offers,
            dict
        ):

            seller_data = offers.get(
                "seller",
                {}
            )

            if isinstance(
                seller_data,
                dict
            ):

                seller = self.clean(
                    seller_data.get(
                        "name",
                        ""
                    )
                )

        if not seller:

            seller_href = selector.xpath(
                "//a[contains(@href, '/users/')]/@href"
            ).get()

            if seller_href:

                match = re.search(
                    r"/users/([^/?#]+)",
                    seller_href
                )

                if match:

                    seller = self.clean(
                        match.group(1)
                    )

        # ---------------------------------------------
        # UPDATED
        # ---------------------------------------------

        updated = ""

        patterns = [
            r"\b\d+\s+(?:min|mins|minute|minutes|hr|hrs|hour|hours|day|days|week|weeks)\.?\s+ago\b",
            r"\b(?:just now|today|yesterday)\b",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                body_text,
                flags=re.IGNORECASE
            )

            if match:

                updated = self.clean(
                    match.group(0)
                )

                break

        # ---------------------------------------------
        # LICENSE SECTION
        # ---------------------------------------------

        license_section = (
            self.extract_license_section(
                body_text
            )
        )

        # ---------------------------------------------
        # LICENSE FIELDS
        # ---------------------------------------------

        purpose = self.get_license_value(
            license_section,
            [
                "Purpose of advertisement",
                "غرض الإعلان",
            ]
        )

        unit_price = self.get_license_value(
            license_section,
            [
                "Unit price",
                "سعر الوحدة",
            ]
        )

        property_type = self.get_license_value(
            license_section,
            [
                "Property type",
                "نوع العقار",
            ]
        )

        property_age = self.get_license_value(
            license_section,
            [
                "Property age",
                "عمر العقار",
            ]
        )

        area = self.get_license_value(
            license_section,
            [
                "Property area",
                "مساحة العقار",
            ]
        )

        rooms = self.get_license_value(
            license_section,
            [
                "Number of rooms",
                "عدد الغرف",
            ]
        )

        facade = self.get_license_value(
            license_section,
            [
                "Property facade",
                "واجهة العقار",
            ]
        )

        plan_number = self.get_license_value(
            license_section,
            [
                "Plan number",
                "رقم المخطط",
            ]
        )

        plot_number = self.get_license_value(
            license_section,
            [
                "Plot number",
                "رقم القطعة",
            ]
        )

        street_width = self.get_license_value(
            license_section,
            [
                "Street width",
                "عرض الشارع",
            ]
        )

        property_uses = self.get_license_value(
            license_section,
            [
                "Property uses",
                "استخدامات العقار",
            ]
        )

        services = self.get_license_value(
            license_section,
            [
                "Property services",
                "Services",
                "خدمات العقار",
            ]
        )

        guarantees = self.get_license_value(
            license_section,
            [
                "Guarantees and duration",
                "الضمانات ومدتها",
            ]
        )

        obligations = self.get_license_value(
            license_section,
            [
                "Other obligations",
                "الالتزامات الآخرى على العقار",
            ]
        )

        location_description = (
            self.extract_location(
                license_section
            )
        )

        license_owner = self.get_license_value(
            license_section,
            [
                "License owner",
                "مالك الرخصة",
                "License holder",
            ]
        )

        license_expiry = self.get_license_value(
            license_section,
            [
                "License expiry",
                "انتهاء الرخصة",
                "License expiration date",
            ]
        )

        advertiser_number = self.get_license_value(
            license_section,
            [
                "Advertiser number",
                "رقم المعلن",
            ]
        )

        authorization_number = self.get_license_value(
            license_section,
            [
                "Authorization number",
                "رقم التصريح",
            ]
        )

        # ---------------------------------------------
        # LOCATION
        # ---------------------------------------------

        city = ""
        district = ""

        address = listing.get(
            "address",
            {}
        )

        if isinstance(
            address,
            dict
        ):

            city = self.clean(
                address.get(
                    "addressLocality",
                    ""
                )
            )

        city2, district2 = (
            self.extract_city_district(
                location_description,
                description
            )
        )

        if city2:
            city = city2

        if district2:
            district = district2

        # ---------------------------------------------
        # ASKING PRICE
        # ---------------------------------------------

        price = self.extract_price(
            description
        )

        # ---------------------------------------------
        # MAP
        # ---------------------------------------------

        map_url = self.extract_map_url(
            body_text
        )

        # ---------------------------------------------
        # IMAGES
        # ---------------------------------------------

        images = self.extract_images(
            listing,
            page
        )

        # ---------------------------------------------
        # RESULT
        # ---------------------------------------------

        item = PropertyItem(
            url=url,
            ad_id=ad_id,
            title=title,
            city=city,
            district=district,
            seller=seller,
            updated=updated,
            description=description,
            price=price,
            currency="SAR",
            purpose=purpose,
            unit_price=unit_price,
            property_type=property_type,
            property_age=property_age,
            area=area,
            rooms=rooms,
            facade=facade,
            plan_number=plan_number,
            plot_number=plot_number,
            street_width=street_width,
            property_uses=property_uses,
            services=services,
            guarantees=guarantees,
            obligations=obligations,
            license_owner=license_owner,
            license_expiry=license_expiry,
            advertiser_number=advertiser_number,
            authorization_number=authorization_number,
            location_description=location_description,
            map_url=map_url,
            images=images,
        )

        print(
            f"Parsed: {title}"
        )

        return item