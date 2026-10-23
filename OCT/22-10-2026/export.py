import csv
import logging
import os
from items import CsvStore
from settings import FILE_NAME, FILE_HEADERS


class Export:
    """Writes final product rows to csv (resumable, no duplicates)"""

    def __init__(self):
        self.store = CsvStore(FILE_NAME, FILE_HEADERS, "product_url")

    def has(self, url):
        return self.store.has(url)

    def write(self, item):
        if self.store.add(item):
            logging.info(f"saved row {len(self.store.rows)}: {item.get('product_url')}")


if __name__ == "__main__":
    # standalone: de-duplicate / re-save the final csv
    export = Export()
    logging.info(f"{len(export.store.rows)} rows in {FILE_NAME}")