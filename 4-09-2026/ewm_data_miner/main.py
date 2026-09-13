from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from settings import AGENTS_URL, MAX_AGENTS


class DataMiningError(Exception):
    """Raised when agent data cannot be parsed."""


class EWMParser:

    def __init__(self, url):
        self.url = url
        self.html = ""
        self.data = {}

    def start(self, page):
        self.fetch_html(page)
        self.data = self.parse_data(self.html)
        return self.data

    def fetch_html(self, page):
        try:
            page.goto(
                self.url,
                wait_until="domcontentloaded"
            )

            page.wait_for_timeout(2000)

            if "Just a moment" in page.title():
                print("\nCloudflare verification required.")
                print("Complete the verification in Chrome.")
                input(
                    "Press Enter after verification is complete... "
                )

                page.wait_for_timeout(3000)

                if "Just a moment" in page.title():
                    raise DataMiningError(
                        "Cloudflare verification was not completed"
                    )

            self.html = page.content()

        except Exception as error:
            raise DataMiningError(
                f"Failed to fetch {self.url}: {error}"
            )

    def parse_data(self, html):
        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        data = {
            "name": "",
            "license": "",
            "position": "",
            "office": "",
            "cell": "",
            "work_phone": "",
            "direct_line": "",
            "office_phone": "",
            "email": "",
            "website": "",
            "address": "",
            "profile_url": self.url,
            "image_url": "",
        }

        # Agent name, license, and office
        title = soup.select_one(
            ".listing-user-title"
        )

        if title:
            headings = title.find_all("h3")

            if headings:
                text = headings[0].get_text(
                    " ",
                    strip=True
                )

                parts = text.rsplit(" ", 1)

                if (
                    len(parts) == 2
                    and parts[1].isdigit()
                ):
                    data["name"] = parts[0]
                    data["license"] = parts[1]
                else:
                    data["name"] = text

            if len(headings) > 1:
                data["office"] = headings[1].get_text(
                    " ",
                    strip=True
                )

        # Agent image
        image = soup.select_one(
            ".listing-user-image a"
        )

        if image:
            style = image.get("style", "")

            if "url('" in style:
                data["image_url"] = (
                    style.split("url('", 1)[1]
                    .split("')", 1)[0]
                )

        # Position
        page_title = soup.select_one("h1")

        if page_title:
            heading = page_title.get_text(
                " ",
                strip=True
            )

            if " - " in heading:
                data["position"] = heading.rsplit(
                    " - ",
                    1
                )[1]

        # Phone numbers
        overview = soup.select_one(
            ".overview"
        )

        if overview:
            field_map = {
                "Cell": "cell",
                "Work Phone": "work_phone",
                "Direct Line": "direct_line",
                "Office": "office_phone",
            }

            for item in overview.select("li"):
                label = item.find("strong")
                value = item.find("span")

                if not label or not value:
                    continue

                key = label.get_text(
                    " ",
                    strip=True
                )

                if key in field_map:
                    data[field_map[key]] = (
                        value.get_text(
                            " ",
                            strip=True
                        )
                    )

            # Personal website
            website = overview.select_one(
                'a[href^="http"]'
            )

            if website:
                data["website"] = website.get(
                    "href",
                    ""
                )

        # Address
        contact_info = soup.select_one(
            "table.contact"
        )

        if contact_info:
            for row in contact_info.select("tr"):
                header = row.find("th")

                if not header:
                    continue

                label = header.get_text(
                    " ",
                    strip=True
                )

                if label == "Address:":
                    value = row.find("td")

                    if value:
                        data["address"] = (
                            value.get_text(
                                " ",
                                strip=True
                            )
                        )

                    break

        if not data["name"]:
            raise DataMiningError(
                f"Could not parse agent: {self.url}"
            )

        return data

    def parse_item(self):
        return self.parse_data(self.html)

    def save_to_file(self, data):
        with open(
            "output/cleaned_data.txt",
            "a",
            encoding="utf-8"
        ) as file:
            for key, value in data.items():
                file.write(
                    f"{key}: {value}\n"
                )

            file.write("\n")

    def close(self):
        pass


def collect_agent_urls(page):
    """Collect agent profile URLs from all roster pages."""

    agent_urls = set()
    current_url = AGENTS_URL
    visited_pages = set()

    while current_url:

        if current_url in visited_pages:
            break

        visited_pages.add(current_url)

        print(f"\nRoster page: {current_url}")

        try:
            page.goto(
                current_url,
                wait_until="domcontentloaded"
            )

            page.wait_for_timeout(2000)

        except Exception as error:
            raise DataMiningError(
                f"Failed to load roster page: {error}"
            )

        if "Just a moment" in page.title():
            print("\nCloudflare verification required.")
            print("Complete the verification in Chrome.")
            input(
                "Press Enter after verification is complete... "
            )

            page.wait_for_timeout(3000)

            if "Just a moment" in page.title():
                raise DataMiningError(
                    "Cloudflare verification was not completed"
                )

        soup = BeautifulSoup(
            page.content(),
            "html.parser"
        )

        links = soup.select(
            'a[href^="/agents/"]'
        )

        before = len(agent_urls)

        for link in links:
            href = link.get("href")

            if not href:
                continue

            full_url = (
                f"{AGENTS_URL.split('/agents.php')[0]}"
                f"{href}"
            )

            agent_urls.add(full_url)

            if (
                MAX_AGENTS is not None
                and len(agent_urls) >= MAX_AGENTS
            ):
                return list(agent_urls)[:MAX_AGENTS]

        print(
            f"New agents: "
            f"{len(agent_urls) - before}"
        )

        print(
            f"Total agents: "
            f"{len(agent_urls)}"
        )

        # Find the actual Next button
        next_link = soup.find(
            "a",
            string=lambda text:
            text and "Next" in text
        )

        if not next_link:
            # Fallback: search links containing Next
            for link in soup.find_all("a"):
                text = link.get_text(
                    " ",
                    strip=True
                )

                if text == "Next":
                    next_link = link
                    break

        if next_link:
            href = next_link.get("href")

            if href:
                if href.startswith("http"):
                    current_url = href
                else:
                    current_url = (
                        f"https://www.ewm.com{href}"
                    )
            else:
                current_url = None
        else:
            current_url = None

    return list(agent_urls)


def main():

    with sync_playwright() as p:

        browser = p.chromium.connect_over_cdp(
            "http://127.0.0.1:9222"
        )

        context = browser.contexts[0]

        if not context.pages:
            page = context.new_page()
        else:
            page = context.pages[0]

        print("Collecting agent URLs...")

        agent_urls = collect_agent_urls(page)

        print(
            f"\nTotal agent URLs: "
            f"{len(agent_urls)}"
        )

        # Start fresh output
        open(
            "output/cleaned_data.txt",
            "w",
            encoding="utf-8"
        ).close()

        successful = 0
        failed = 0

        for index, url in enumerate(
            agent_urls,
            start=1
        ):

            print(
                f"\n[{index}/{len(agent_urls)}] "
                f"{url}"
            )

            try:
                parser = EWMParser(url)

                data = parser.start(page)

                parser.save_to_file(data)

                successful += 1

                print(
                    f"Saved: {data['name']}"
                )

            except DataMiningError as error:

                failed += 1

                print(
                    f"Skipped: {error}"
                )

        print("\nScraping completed.")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")

        browser.close()


if __name__ == "__main__":
    main()