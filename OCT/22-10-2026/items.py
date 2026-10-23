import csv
import os


class CsvStore:
    """Tiny csv 'collection': append rows, ignore duplicates on `key`, resume from file."""

    def __init__(self, path, headers, key):
        self.path, self.headers, self.key = path, headers, key
        self.rows, self.keys = [], set()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path):
            with open(path, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    self.rows.append(row)
                    self.keys.add(row.get(key))
        else:
            with open(path, "w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow(headers)

    def has(self, value):
        return value in self.keys

    def add(self, item):
        """Append item (dict). Returns False if the key already exists."""
        if item.get(self.key) in self.keys:
            return False
        row = {h: self.clean(item.get(h)) for h in self.headers}
        with open(self.path, "a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=self.headers).writerow(row)
        self.rows.append(row)
        self.keys.add(item.get(self.key))
        return True

    @staticmethod
    def clean(value):
        if isinstance(value, list):
            return " | ".join(str(v).strip() for v in value if str(v).strip())
        return "" if value is None else value


CATEGORY_HEADERS = ["url", "category", "category_name"]
SUBCATEGORY_HEADERS = ["url", "category", "category_name", "subcategory"]
PRODUCT_URL_HEADERS = ["product_url", "category", "category_name", "subcategory",
                       "name", "brand", "price", "regular_price", "badge"]
DONE_HEADERS = ["url", "stage"]
FAILED_HEADERS = ["url", "stage"]