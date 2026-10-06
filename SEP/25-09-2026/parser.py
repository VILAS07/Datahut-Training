from playwright.sync_api import sync_playwright
import json


class Parser:
    """Parse OpenSooq property listing using Playwright"""

    def __init__(self, url, page):
        self.url = url
        self.page = page

    def parse(self):
        """Open property page and extract listing data"""

        try:
            self.page.goto(
                self.url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            self.page.wait_for_timeout(2000)

            json_ld_list = self.page.locator(
                'script[type="application/ld+json"]'
            ).all_text_contents()

            for json_text in json_ld_list:

                try:
                    data = json.loads(json_text)

                except json.JSONDecodeError:
                    continue

                if data.get("@type") not in [
                    "Residence",
                    "Apartment"
                ]:
                    continue

                address = data.get("address", {})
                geo = data.get("geo", {})
                photo = data.get("photo", {})
                offers = data.get("offers", {})

                item = {
                    "url": self.url,
                    "title": data.get("name"),
                    "country": address.get("addressCountry"),
                    "region": address.get("addressRegion"),
                    "locality": address.get("addressLocality"),
                    "rooms": data.get("numberOfRooms"),
                    "latitude": geo.get("latitude"),
                    "longitude": geo.get("longitude"),
                    "image": photo.get("contentUrl"),
                    "price": offers.get("price"),
                    "currency": offers.get("priceCurrency"),
                    "price_valid_until": offers.get("priceValidUntil")
                }

                print("\n" + "=" * 80)
                print("PROPERTY DATA")
                print("=" * 80)

                for key, value in item.items():
                    print(f"{key}: {value}")

                print("=" * 80)

                return item

            print(f"No property JSON-LD found: {self.url}")
            return None

        except Exception as e:
            print(f"Error parsing {self.url}: {e}")
            return None
if __name__ == "__main__":

    url = "https://bh.opensooq.com/en/search/286140186"

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page()

        parser = Parser(url, page)

        data = parser.parse()

        browser.close()