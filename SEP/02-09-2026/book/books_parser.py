import requests
import books_settings

from bs4 import BeautifulSoup
from requests.exceptions import RequestException


class DataMiningError(Exception):
    pass


class BooksParser:
    def __init__(self):
        self.url = ""
        self.html = ""
        self.data = []
        self.session = requests.Session()

    def start(self):
        self.url = books_settings.URL
        print(f"Data Mining started from: {self.url}")

        self.fetch_html()
        self.parse_data()
        self.save_to_file()
        self.close()

    def fetch_html(self):
        try:
            response = self.session.get(
                self.url,
                timeout=15
            )
            response.raise_for_status()

            self.html = response.text

            with open(
                "books_raw.html",
                "w",
                encoding="utf-8"
            ) as file:
                file.write(self.html)

            print("HTML fetched successfully.")
            print("Raw HTML saved to books_raw.html")

        except RequestException as error:
            raise DataMiningError(
                f"Failed to fetch HTML: {error}"
            ) from error

    def parse_data(self):
        try:
            soup = BeautifulSoup(
                self.html,
                "html.parser"
            )

            books = soup.select("article.product_pod")

            for book in books:
                title = book.select_one("h3 a")
                price = book.select_one(".price_color")

                book_data = {
                    "name": title.get("title", "").strip(),
                    "price": price.get_text(strip=True)
                    if price else None,
                }

                self.data.append(book_data)

            print(
                f"Data parsed successfully: "
                f"{len(self.data)} book(s)"
            )

        except Exception as error:
            raise DataMiningError(
                f"Parsing failed: {error}"
            ) from error

    def parse_item(self, item):
        cleaned_item = {
            key: str(value).strip()
            for key, value in item.items()
        }

        yield cleaned_item

    def save_to_file(self):
        with open(
            "books_data.txt",
            "w",
            encoding="utf-8"
        ) as file:
            for item in self.data:
                file.write(
                    f"Name: {item['name']}\n"
                    f"Price: {item['price']}\n"
                    f"{'-' * 40}\n"
                )

        print("Book data saved to books_data.txt")

    def yield_lines_from_file(self):
        with open(
            "books_data.txt",
            "r",
            encoding="utf-8"
        ) as file:
            for line in file:
                yield line.strip()

    def close(self):
        self.session.close()
        print("Connection Closed")


parser = BooksParser()
parser.start()

print("\nReading data using generator:\n")

for line in parser.yield_lines_from_file():
    print(line)