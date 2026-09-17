import csv


def export_to_csv(items):
    """Save property data to CSV"""

    if not items:
        return

    with open(
        "output.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        fieldnames = items[0].keys()

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(items)