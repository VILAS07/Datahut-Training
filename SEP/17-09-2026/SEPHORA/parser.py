from parsel import Selector


class SephoraParser:

    # ==================================================
    # CATEGORY PRODUCT CARDS
    # ==================================================

    def parse_products(self, html):

        selector = Selector(text=html)

        products = []

        for card in selector.css("div.product-card"):

            product = {
                "url": card.css(
                    ".product-card-image-link::attr(href)"
                ).get(""),

                "name": card.css(
                    ".product-name::text"
                ).get("").strip(),

                "brand": card.css(
                    ".brand::text"
                ).get("").strip(),

                "price": card.css(
                    ".sell-price::text"
                ).get("").strip(),

                "rating": card.css(
                    ".stars::attr(style)"
                ).get(""),

                "reviews": card.css(
                    ".reviews-count::text"
                ).get("").strip(),

                "image": card.css(
                    ".product-card-image::attr(src)"
                ).get(""),

                "category": "Makeup"
            }

            products.append(product)

        return products


    # ==================================================
    # PRODUCT URLS
    # ==================================================

    def parse_product_urls(self, html):

        selector = Selector(text=html)

        urls = selector.css(
            "div.product-card "
            ".product-card-image-link::attr(href)"
        ).getall()

        return urls


    # ==================================================
    # PRODUCT DETAIL PAGE
    # ==================================================

    def parse_product_page(self, html, url=""):

        selector = Selector(text=html)

        product = {

            "url": url,

            "name": "",

            "brand": "",

            "price": "",

            "rating": "",

            "reviews": "",

            "image": "",

            "category": "Makeup",

            "product_size": "",

            "shades": "",

            "description": "",

            "ingredients": "",

            "how_to": ""
        }


        # ==================================================
        # NAME
        # ==================================================

        product["name"] = selector.xpath(
            'normalize-space('
            '//div[contains(@class, "product-heading")]/h1'
            ')'
        ).get("")


        # ==================================================
        # PRODUCT SIZE
        # ==================================================

        product["product_size"] = selector.xpath(
            'normalize-space('
            '//div[contains(@class, "product-heading")]/span'
            ')'
        ).get("")

        product["product_size"] = (
            product["product_size"]
            .replace("•", "")
            .strip()
        )


        # ==================================================
        # BRAND
        # ==================================================
        #
        # Sephora has many /brands/ links in the header menu.
        # The product brand link appears later in the page.
        #
        # [last()] prevents us from getting:
        # "Shop Sephora Collection"
        #
        # Example:
        # /brands/benefit-cosmetics
        # Benefit Cosmetics
        #
        # ==================================================

        product["brand"] = selector.xpath(
            'normalize-space('
            '(//a[contains(@href, "/brands/")])[last()]'
            ')'
        ).get("")


        # ==================================================
        # PRICE
        # ==================================================

        price_elements = selector.xpath(
            '//*[contains(normalize-space(text()), "$")]'
        )

        for element in price_elements:

            text = element.xpath(
                'normalize-space(string(.))'
            ).get("")

            if text.startswith("$"):

                product["price"] = text
                break


        # ==================================================
        # RATING
        # ==================================================
        #
        # Exact Sephora/Bazaarvoice element:
        #
        # <div itemprop="ratingValue"
        #      class="bv_avgRating_component_container">
        #      4.6
        # </div>
        #
        # ==================================================

        product["rating"] = selector.xpath(
            'normalize-space('
            '//div[@itemprop="ratingValue"]'
            ')'
        ).get("")


        # ==================================================
        # REVIEWS
        # ==================================================
        #
        # Exact review count:
        #
        # <meta itemprop="reviewCount" content="83">
        #
        # ==================================================

        product["reviews"] = selector.xpath(
            'normalize-space('
            '//meta[@itemprop="reviewCount"]/@content'
            ')'
        ).get("")


        # ==================================================
        # PRODUCT IMAGE
        # ==================================================

        image = selector.xpath(
            '//img[contains(@class, "product-header-image")]/@src'
        ).get("")


        # The product-header-image is lazy-loaded and may contain
        # a data:image placeholder.

        if (
            not image
            or image.startswith("data:image")
        ):

            image = selector.xpath(
                '//img['
                'contains(@class, "variant-image-border-space")'
                ' and not(starts-with(@src, "data:image"))'
                ']/@src'
            ).get("")


        product["image"] = image


        # ==================================================
        # SHADES
        # ==================================================

        shade_names = selector.xpath(
            '//img[contains(@class, "variant-swatch-image")]/@alt'
        ).getall()

        cleaned_shades = []

        for shade in shade_names:

            shade = shade.replace(
                " Swatch",
                ""
            ).strip()

            if (
                shade
                and shade not in cleaned_shades
            ):

                cleaned_shades.append(shade)

        product["shades"] = ", ".join(
            cleaned_shades
        )


        # ==================================================
        # DESCRIPTION
        # ==================================================

        description_elements = selector.xpath(
            '//div[contains(@class, "product-description")]'
            '//p[contains(@class, "product-filter-type-value")]'
        )

        description_parts = []

        for element in description_elements:

            text = element.xpath(
                'normalize-space(string(.))'
            ).get("")

            if text:

                description_parts.append(text)

        product["description"] = " | ".join(
            description_parts
        )


        # ==================================================
        # INGREDIENTS
        # ==================================================

        product["ingredients"] = selector.xpath(
            'normalize-space('
            '//div[contains(@class, "product-ingredients-values")]'
            ')'
        ).get("")


        # ==================================================
        # HOW TO
        # ==================================================

        product["how_to"] = selector.xpath(
            'normalize-space('
            '//div[contains(@class, "product-how-to-text")]'
            ')'
        ).get("")


        return product