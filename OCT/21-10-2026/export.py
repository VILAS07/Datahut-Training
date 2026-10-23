import csv
import logging

from items import connect_db, close_db
from settings import (
    MONGO_DB, MONGO_COLLECTION_DATA,
    FILE_NAME_PRODUCTS, FILE_NAME_REVIEWS, FILE_HEADERS, REVIEW_HEADERS,
)


def join(values, sep=" | "):
    return sep.join(str(v) for v in values) if values else ""


class Export:
    """Post-Processing: Mongo -> two csv files
    products csv: one row per perfume
    reviews csv : one row per review (linked by product_id)"""

    def __init__(self):
        self.mongo = connect_db()

    def start(self):
        """Export as CSV files"""

        # utf-8-sig so Excel opens french accents and the euro sign correctly
        with open(FILE_NAME_PRODUCTS, "w", newline="", encoding="utf-8-sig") as pf, \
                open(FILE_NAME_REVIEWS, "w", newline="", encoding="utf-8-sig") as rf:
            product_writer = csv.writer(pf, quoting=csv.QUOTE_ALL)
            review_writer = csv.writer(rf, quoting=csv.QUOTE_ALL)
            product_writer.writerow(FILE_HEADERS)
            review_writer.writerow(REVIEW_HEADERS)
            logging.info(FILE_HEADERS)

            products = reviews = 0
            for item in self.mongo.get_database(MONGO_DB)[MONGO_COLLECTION_DATA].find(no_cursor_timeout=True):
                accords = join(
                    [f"{a.get('accord')}:{a.get('strength'):g}" for a in item.get("main_accords", [])]
                )
                also_like = join(
                    [f"{a.get('name')} ({a.get('brand')}) {a.get('url')}" for a in item.get("also_like", [])]
                )
                row = dict(item)
                row["main_accords"] = accords
                row["top_notes"] = join(item.get("top_notes"))
                row["middle_notes"] = join(item.get("middle_notes"))
                row["base_notes"] = join(item.get("base_notes"))
                row["also_like"] = also_like
                product_writer.writerow([row.get(h, "") if row.get(h) is not None else "" for h in FILE_HEADERS])
                products += 1

                for review in item.get("reviews", []):
                    review_row = {
                        "website": item.get("website"),
                        "extraction_date": item.get("extraction_date"),
                        "product_id": item.get("product_id"),
                        "pdp_url": item.get("pdp_url"),
                        "product_name": item.get("product_name"),
                    }
                    review_row.update(review)
                    review_writer.writerow(
                        [review_row.get(h, "") if review_row.get(h) is not None else "" for h in REVIEW_HEADERS]
                    )
                    reviews += 1
        logging.info(f"exported {products} products -> {FILE_NAME_PRODUCTS}, "
                     f"{reviews} reviews -> {FILE_NAME_REVIEWS}")

    def close(self):
        """connection close"""
        close_db()


if __name__ == "__main__":
    export_obj = Export()
    export_obj.start()
    export_obj.close()
