import csv


class CSVExporter:

    def export(self, products, filename="sephora_makeup.csv"):

        if not products:
            print("No products to export.")
            return

        fieldnames = [
            "url",
            "name",
            "brand",
            "price",
            "rating",
            "reviews",
            "image",
            "category",
            "product_size",
            "shades",
            "description",
            "ingredients",
            "how_to"
        ]

        with open(
            filename,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )

            writer.writeheader()
            writer.writerows(products)

        print("\nCSV exported successfully:", filename)
        print("Total records:", len(products))