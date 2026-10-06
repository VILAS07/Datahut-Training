import scrapy


class NawySpider(scrapy.Spider):
    name = "nawy"
    allowed_domains = ["nawy.com"]

    start_url = "https://www.nawy.com/search?category=property"

    # =========================================================
    # START
    # =========================================================

    async def start(self):

        yield scrapy.Request(
            self.start_url,
            meta={
                "playwright": True,
                "playwright_include_page": True,
            },
            callback=self.parse,
            errback=self.errback_close_page,
        )

    # =========================================================
    # SEARCH PAGE
    # =========================================================

    async def parse(self, response):

        page = response.meta["playwright_page"]

        try:

            # -------------------------------------------------
            # INFINITE SCROLL
            # -------------------------------------------------

            previous_count = 0
            no_new_count = 0

            for scroll_number in range(50):

                # ---------------------------------------------
                # GET CURRENT PROPERTY URLS
                # ---------------------------------------------

                property_urls = await page.locator(
                    'a[href*="/property/"]'
                ).evaluate_all(
                    """links => links.map(link => link.href)"""
                )

                property_urls = list(
                    dict.fromkeys(property_urls)
                )

                current_count = len(property_urls)

                self.logger.info(
                    f"Scroll {scroll_number + 1}: "
                    f"{current_count} properties found"
                )

                # ---------------------------------------------
                # CHECK IF WE HAVE NEW PROPERTIES
                # ---------------------------------------------

                if current_count == previous_count:

                    no_new_count += 1

                else:

                    no_new_count = 0

                previous_count = current_count

                # ---------------------------------------------
                # STOP IF NOTHING NEW AFTER 5 ATTEMPTS
                # ---------------------------------------------

                if no_new_count >= 5:

                    self.logger.info(
                        "No new properties loaded. "
                        "Stopping scroll."
                    )

                    break

                # ---------------------------------------------
                # SCROLL THE PROPERTY LIST CONTAINER
                # ---------------------------------------------

                scroll_result = await page.locator(
                    'a[href*="/property/"]'
                ).first.evaluate(
                    """
                    (link) => {

                        let element = link.parentElement;

                        while (element) {

                            const style =
                                window.getComputedStyle(element);

                            const canScroll =
                                element.scrollHeight >
                                element.clientHeight + 100;

                            const isScrollable =
                                style.overflowY === "auto" ||
                                style.overflowY === "scroll";

                            if (
                                canScroll &&
                                isScrollable
                            ) {

                                const oldScrollTop =
                                    element.scrollTop;

                                element.scrollTop +=
                                    element.clientHeight;

                                return {
                                    found: true,
                                    oldScrollTop:
                                        oldScrollTop,
                                    newScrollTop:
                                        element.scrollTop,
                                    scrollHeight:
                                        element.scrollHeight,
                                    clientHeight:
                                        element.clientHeight
                                };
                            }

                            element = element.parentElement;
                        }

                        // Fallback:
                        // scroll the main page if no internal
                        // scroll container is found.

                        window.scrollBy(
                            0,
                            window.innerHeight
                        );

                        return {
                            found: false,
                            windowScrollY:
                                window.scrollY
                        };
                    }
                    """
                )

                self.logger.info(
                    f"Scroll result: {scroll_result}"
                )

                # ---------------------------------------------
                # WAIT FOR NEW PROPERTIES
                # ---------------------------------------------

                await page.wait_for_timeout(2500)

            # =================================================
            # FINAL PROPERTY URL COLLECTION
            # =================================================

            final_urls = await page.locator(
                'a[href*="/property/"]'
            ).evaluate_all(
                """links => links.map(link => link.href)"""
            )

            final_urls = list(
                dict.fromkeys(final_urls)
            )

            self.logger.info(
                f"Total property URLs collected: "
                f"{len(final_urls)}"
            )

            # =================================================
            # SCRAPE EACH PROPERTY
            # =================================================

            for url in final_urls:

                yield scrapy.Request(
                    url,
                    callback=self.parse_property,
                )

        finally:

            await page.close()

    # =========================================================
    # PLAYWRIGHT ERROR HANDLER
    # =========================================================

    async def errback_close_page(self, failure):

        page = failure.request.meta.get(
            "playwright_page"
        )

        if page:

            await page.close()

    # =========================================================
    # PROPERTY DETAILS
    # =========================================================

    def parse_property(self, response):

        yield {

            # -------------------------------------------------
            # URL
            # -------------------------------------------------

            "URL": response.url,

            # -------------------------------------------------
            # NAME
            # -------------------------------------------------

            "Name": response.xpath(
                '//h1/text()'
            ).get(),

            # -------------------------------------------------
            # PRICE
            # -------------------------------------------------

            "Starting Price": response.xpath(
                '//div[@class="property-price-details"]//p/text()'
            ).get(),

            "Max Price": response.xpath(
                '//div[@class="price-data max-price"]'
                '//p[@class="headline-1 price"]/text()'
            ).get(),

            # -------------------------------------------------
            # DESCRIPTION
            # -------------------------------------------------

            "Description": response.xpath(
                '//div[@class="text-container"]/div/p/text()'
            ).getall(),

            # -------------------------------------------------
            # LOCATION
            # -------------------------------------------------

            "Location": response.xpath(
                '//span[contains(@class, "text-2")]'
                '[contains(., ",")]/text()'
            ).get(),

            # -------------------------------------------------
            # BEDROOMS
            # -------------------------------------------------

            "Bedrooms": response.xpath(
                '//div[@class="rowData"]'
                '[div/text()="Bedrooms"]'
                '/div[2]/text()'
            ).get(),

            # -------------------------------------------------
            # BATHROOMS
            # -------------------------------------------------

            "Bathrooms": response.xpath(
                '//div[@class="rowData"]'
                '[div/text()="Bathrooms"]'
                '/div[2]/text()'
            ).get(),

            # -------------------------------------------------
            # DELIVERY
            # -------------------------------------------------

            "Delivery": response.xpath(
                '//div[@class="rowData"]'
                '[div/text()="Delivery In"]'
                '/div[2]/text()'
            ).get(),

            # -------------------------------------------------
            # FINISHING
            # -------------------------------------------------

            "Finishing": response.xpath(
                '//div[@class="rowData"]'
                '[div/text()="Finishing"]'
                '/div[2]/text()'
            ).get(),

            # -------------------------------------------------
            # AMENITIES
            # -------------------------------------------------

            "Amenity": response.xpath(
                '//div[@class="amenity"]/span/text()'
            ).getall(),

            # -------------------------------------------------
            # PROPERTY TYPE
            # -------------------------------------------------

            "Property Type": response.xpath(
                '//div[@class="header"]/div[1]/text()'
            ).get(),

            # -------------------------------------------------
            # AREA
            # -------------------------------------------------

            "Area": response.xpath(
                '//div[@class="header"]/div[2]//text()'
            ).getall(),

            # -------------------------------------------------
            # COMPOUND
            # -------------------------------------------------

            "Compound": response.xpath(
                '//div[@class="rowData"]'
                '[div/text()="Compound"]'
                '//span/text()'
            ).get(),

            # -------------------------------------------------
            # SALE TYPE
            # -------------------------------------------------

            "Sale Type": response.xpath(
                '//div[@class="rowData"]'
                '[div/text()="Sale Type"]'
                '/div[2]/text()'
            ).get(),

            # -------------------------------------------------
            # INSTALLMENT
            # -------------------------------------------------

            "Installment Amount": response.xpath(
                '//div[@class="installments-section"]'
                '//span[@class="value"]/text()'
            ).get(),

            "Currency": response.xpath(
                '//div[@class="installments-section"]'
                '//span[@class="currency"]/text()'
            ).get(),

            "Installment Frequency": response.xpath(
                '//div[@class="installments-section"]'
                '//span[@class="monthly"]/text()'
            ).get(),

            # -------------------------------------------------
            # DOWN PAYMENT
            # -------------------------------------------------

            "Down Payment": response.xpath(
                '//div[@class="down-payment"]'
                '/span[@class="value"]/text()'
            ).get(),

            # -------------------------------------------------
            # INSTALLMENT YEARS
            # -------------------------------------------------

            "Installment Years": response.xpath(
                '//span[@class="installment-years"]/text()'
            ).get(),
        }