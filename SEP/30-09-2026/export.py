import csv

from settings import OUTPUT_FILE


FIELDS = [
    "keyword",
    "product_name",
    "size",
    "product_description",
    "category",
    "product_type",
    "price",
    "main_image",
    "pdp_url",
    "rank",
    "colour",
    "gender",
    "material",
    "fit_sizing",
    "occasion_style",
]


def export_csv(items):

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=FIELDS,
        )

        writer.writeheader()

        for item in items:

            writer.writerow(item)

    print()
    print("=" * 70)
    print("CSV EXPORT")
    print("=" * 70)

    print(
        f"File: {OUTPUT_FILE}"
    )

    print(
        f"Records: {len(items)}"
    )