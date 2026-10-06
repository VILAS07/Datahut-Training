import csv

from settings import OUTPUT_FILE


def export_to_csv(items, filename=OUTPUT_FILE):
    """
    Export parsed property items to CSV.
    """

    if not items:
        print("No items to export.")
        return

    # Convert dataclass objects to dictionaries
    rows = []

    for item in items:

        if hasattr(item, "to_dict"):
            row = item.to_dict()

        elif hasattr(item, "__dict__"):
            row = item.__dict__.copy()

        else:
            row = dict(item)

        # Convert image list to a single CSV-friendly string
        if isinstance(row.get("images"), list):

            row["images"] = " | ".join(
                row["images"]
            )

        rows.append(row)

    # Use the fields from the first item as CSV columns
    fieldnames = list(
        rows[0].keys()
    )

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore"
        )

        writer.writeheader()

        writer.writerows(rows)

    print(
        f"Exported {len(rows)} items to {filename}"
    )