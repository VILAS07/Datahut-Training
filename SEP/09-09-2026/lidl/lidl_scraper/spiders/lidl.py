import scrapy


class LidlSpider(scrapy.Spider):
    name = "lidl"
    allowed_domains = [
        "sortiment.lidl.ch",
        "lidl.ch",
    ]

    start_urls = [
        "https://sortiment.lidl.ch/de/catalog/category/view/id/54/"
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.visited_products = set()

    def parse(self, response):

        product_links = response.xpath(
            '//a[@href]/@href'
        ).getall()

        for href in product_links:

            if "catalog/product/view" not in href:
                continue

            url = response.urljoin(href).split("?")[0]

            if url in self.visited_products:
                continue

            self.visited_products.add(url)

            yield scrapy.Request(
                url,
                callback=self.parse_product,
            )

        # Follow pagination indefinitely
        next_href = response.xpath(
            '//link[@rel="next"]/@href'
        ).get()

        if next_href:

            yield response.follow(
                next_href,
                callback=self.parse,
            )

        else:

            # Some Magento pages may use an anchor instead
            next_href = response.xpath(
                '//a[contains(@class,"next")]/@href'
            ).get()

            if next_href:

                yield response.follow(
                    next_href,
                    callback=self.parse,
                )

    def parse_product(self, response):

        name = response.xpath(
            '//h1[@class="page-title"]'
            '//span[@class="base"]/text()'
        ).get()

        price = response.xpath(
            '//strong[@itemprop="price"]/@content'
        ).get()

        review_count = response.xpath(
            '//span[@itemprop="reviewCount"]/text()'
        ).get()

        # Rating block
        rating_block = (
            '//div[contains(@class,"rating-group")]'
            '[.//span[@itemprop="reviewAspect" '
            'and normalize-space()="{aspect}"]]'
            '//span[@itemprop="ratingValue"]/text()'
        )

        quality = response.xpath(
            rating_block.format(
                aspect="Qualität"
            )
        ).get()

        price_rating = response.xpath(
            rating_block.format(
                aspect="Preis"
            )
        ).get()

        availability = response.xpath(
            rating_block.format(
                aspect="Verfügbarkeit"
            )
        ).get()

        # Fallback for name
        if not name:

            name = response.xpath(
                '//h1[contains(@class,"page-title")]//text()'
            ).get()

        # Fallback for price
        if not price:

            price = response.xpath(
                '//meta[@itemprop="price"]/@content'
            ).get()

        item = {
            "url": response.url.split("?")[0],
            "name": (name or "").strip(),
            "price": (price or "").strip(),
            "review_count": (review_count or "").strip(),
            "quality": (quality or "").strip(),
            "price_rating": (price_rating or "").strip(),
            "availability": (availability or "").strip(),
        }

        # Skip pages that are not actual products
        if not item["name"] or not item["price"]:

            self.logger.info(
                "Skipping invalid product: %s",
                response.url,
            )

            return

        self.logger.info(
            "Scraped: %s",
            item["name"],
        )

        yield item 