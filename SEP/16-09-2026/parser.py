import json

import requests
from parsel import Selector


class Parser:
    """Parse OpenSooq property listing"""

    def __init__(self, url):
        self.url = url

    def parse(self):
        """Request and extract listing data"""

        response = requests.get(
            self.url,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=30
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code != 200:
            return None

        selector = Selector(text=response.text)

        json_ld_list = selector.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall()

        for json_text in json_ld_list:

            try:
                data = json.loads(json_text)

                if data.get("@type") not in [
                    "Residence",
                    "Apartment"
                ]:
                    continue

                address = data.get(
                    "address",
                    {}
                )

                geo = data.get(
                    "geo",
                    {}
                )

                photo = data.get(
                    "photo",
                    {}
                )

                offers = data.get(
                    "offers",
                    {}
                )

                item = {
                    "url": self.url,
                    "title": data.get("name"),
                    "country": address.get(
                        "addressCountry"
                    ),
                    "region": address.get(
                        "addressRegion"
                    ),
                    "locality": address.get(
                        "addressLocality"
                    ),
                    "rooms": data.get(
                        "numberOfRooms"
                    ),
                    "latitude": geo.get(
                        "latitude"
                    ),
                    "longitude": geo.get(
                        "longitude"
                    ),
                    "image": photo.get(
                        "contentUrl"
                    ),
                    "price": offers.get(
                        "price"
                    ),
                    "currency": offers.get(
                        "priceCurrency"
                    ),
                    "price_valid_until": offers.get(
                        "priceValidUntil"
                    )
                }

                return item

            except json.JSONDecodeError:
                continue

        return None


if __name__ == "__main__":

    url = "https://bh.opensooq.com/en/search/286140186"

    parser = Parser(url)

    data = parser.parse()

    print(data)