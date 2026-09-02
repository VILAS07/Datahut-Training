import requests
import settings
from bs4 import BeautifulSoup
from requests.exceptions import RequestException

class DataMiningError(Exception):
    pass


class BayutParser:
    def __init__(self):
        self.url = ""
        self.html = ""
        self.data = []

    def start(self):
        self.url = settings.URL
        print(f"Data Mining started from: {self.url}")

        self.fetch_html()
        self.parse_data()
        self.save_to_file()
        self.close()

    def parse_item(self, item):
        cleaned_item = item.strip()
        yield cleaned_item

    def close(self):
        print("Connection Closed")

    def fetch_html(self):
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            })
            response = session.get(self.url, timeout=15)
            response.raise_for_status()

            self.html = response.text
            with open("raw.html","w",encoding='utf-8') as file:
                file.write(self.html)

            print(f"HTML fetched successfully from: {self.url}")
            print("Raw HTML saved to raw.html")
        except RequestException as error:
            print(f"Failed to fetch the HTML: {error}")

    def parse_data(self):
        try:
            soup = BeautifulSoup(self.html, "html.parser")

            title = soup.title.get_text(strip=True) if soup.title else ""
            if "Captcha" in title or "captcha" in title or "كلمة التحقق" in title:
                for item in self.parse_item(title):
                    self.data.append(item)

                print(f"CAPTCHA/Verification page detected: {title}")
                return

            if title:
                for item in self.parse_item(title):
                    self.data.append(item)

            print(f"Data parsed successfully: {len(self.data)} item(s)")
        except Exception as error:
            raise DataMiningError(f"Parsing Failed : {error}") from error

    def save_to_file(self):
        with open("cleaned_data.txt", "w", encoding="utf-8") as file:
            for item in self.data:
                file.write(f"{item}\n")
        print("Cleaned data saved to cleaned_data.txt")

    def yield_lines_from_file(self):
        with open("cleaned_data.txt", "r", encoding="utf-8") as file:
            for line in file:
                yield line.strip()

    


parser = BayutParser()
parser.start()
for line in parser.yield_lines_from_file():
    print(line)


