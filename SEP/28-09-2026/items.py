"""Data structure for a single MSC Direct product.

The field order of :data:`FIELDS` matches the order of the CSV columns written
by ``export.py``, so this module is the single source of truth for the schema.
"""

from dataclasses import dataclass
from typing import Dict, Optional

FIELDS = (
    "product_name",
    "brand",
    "msc_number",
    "manufacturer_number",
    "price",
    "availability",
    "description",
    "specifications",
    "image_url",
    "product_url",
)


@dataclass
class Product:
    """One MSC Direct product.

    Every field is optional: MSC does not render all of them on every page
    (for example a listing card carries no manufacturer number), so missing
    values are kept as ``None`` instead of being invented.
    """

    product_name: Optional[str] = None
    brand: Optional[str] = None
    msc_number: Optional[str] = None
    manufacturer_number: Optional[str] = None
    price: Optional[str] = None
    availability: Optional[str] = None
    description: Optional[str] = None
    specifications: Optional[str] = None
    image_url: Optional[str] = None
    product_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        """Return the product as a plain dictionary (one CSV row)."""
        return {field: getattr(self, field) for field in FIELDS}

    @classmethod
    def from_dict(cls, data: Dict[str, Optional[str]]) -> "Product":
        """Build a product from a parser dictionary, ignoring unknown keys."""
        return cls(**{field: data.get(field) for field in FIELDS})


def merge_records(
    base: Dict[str, Optional[str]], extra: Dict[str, Optional[str]]
) -> Dict[str, Optional[str]]:
    """Return ``base`` updated with every non-empty value from ``extra``.

    Used when a listing card is later enriched by its product detail page:
    detail page values win, but fields the detail page does not render (for
    example a card brand) are preserved.
    """
    merged = dict(base)
    for field, value in extra.items():
        if value not in (None, ""):
            merged[field] = value
    return merged

