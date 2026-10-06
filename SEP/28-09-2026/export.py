"""CSV export for the scraped MSC Direct products."""

import csv
import logging
from typing import Iterable, Union

from items import FIELDS, Product

LOGGER = logging.getLogger(__name__)


def to_row(product: Union[Product, dict]) -> dict:
    """Return a CSV row dictionary for a Product or a plain record dict."""
    if isinstance(product, Product):
        return product.to_dict()
    return {field: product.get(field) for field in FIELDS}


def save_to_csv(products: Iterable, path: str) -> str:
    """Write the products to ``path`` as CSV and return the file name.

    The columns are exactly: product_name, brand, msc_number,
    manufacturer_number, price, availability, description, specifications,
    image_url, product_url.
    """
    rows = [to_row(product) for product in products]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    LOGGER.info("Exported %d products to %s", len(rows), path)
    return path

