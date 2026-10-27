import csv
import logging
from time import sleep
from settings import MONGO_COLLECTION_DATA, file_name, FILE_HEADERS


class Export:
    """Post-Processing"""

    def __init__(writer):
        mongo = ''  # mongo connect
        writer = writer

    def start(self):
        """Export as CSV file"""

        writer.writerow(FILE_HEADERS)
        logging.info(FILE_HEADERS)

        for item in mongo.db[MONGO_COLLECTION_DATA].find(no_cursor_timeout=True):
            seller_url = item.get("seller_url")
            seller_name = item.get("seller_name")
            company_name = item.get("company_name")
            customer_rating = item.get("customer_rating")
            count_of_ratings = item.get("count_of_ratings")
            count_of_ratings = (
                count_of_ratings.replace(" ", "")
                .replace("pircējavērtējums", "")
                .replace("pircējuvērtējumi", "")
                .strip()
                if count_of_ratings
                else ""
            )
            count_of_offered_selection = item.get("count_of_offered_selection")
            count_of_offered_selection = (
                count_of_offered_selection.replace(" ", "").strip()
                if count_of_offered_selection
                else ""
            )
            category_of_selection_eng = item.get("category_of_selection_eng")
            if category_of_selection_eng:
                category_of_selection_eng = category_of_selection_eng.split(",")
                category_of_selection_eng = ",".join(
                    [cat.strip() for cat in category_of_selection_eng if cat.strip()]
                )

            category_of_selection_native = item.get("category_of_selection_1")
            if category_of_selection_native:
                category_of_selection_native = category_of_selection_native.split(",")
                category_of_selection_native = ",".join(
                    [cat.strip() for cat in category_of_selection_native if cat.strip()]
                )

            brands = item.get("brands")
            if brands:
                brands = brands.split(",")
                brands = ",".join([brand.strip() for brand in brands if brand.strip()])

            address = item.get("address")
            country = item.get("country")
            phone_number = item.get("phone_number")
            email = item.get("email")

            data = [
                seller_url,
                seller_name,
                company_name,
                address,
                country,
                phone_number,
                email,
                customer_rating,
                count_of_ratings,
                count_of_offered_selection,
                brands,
                category_of_selection_native,
                category_of_selection_eng,

            ]

            writer.writerow(data)


if __name__ == "__main__":
    with open(file_name, "a", encoding="utf-8") as file:
        writer_file = csv.writer(file, delimiter=",", quotechar='"')
        export = Export(writer_file)
        export.start()
        file.close()
