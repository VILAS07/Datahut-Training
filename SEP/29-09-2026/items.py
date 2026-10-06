"""Data structures for a single John Lewis product.

This module is the single source of truth for the product schema: ``parser.py``
fills a :class:`ProductItem`, and ``exporter.py`` upserts it into MongoDB keyed
on :data:`UPSERT_KEY` so re-running the scraper never creates duplicates.

Nothing here performs I/O - crawling, parsing and exporting live in the other
modules.

Nested sub-documents use :class:`TypedDict` aliases instead of bare ``dict`` so
that ``parser.py`` has an explicit contract for what it must build (size
variants, review summaries, related-product stubs, ...).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple, TypedDict

# John Lewis product URLs end in a numeric id, e.g.
# https://www.johnlewis.com/barbour-icons-lowerdale-gilet/p115694591
PRODUCT_ID_PATTERN = re.compile(r"/p(\d+)(?!\d)", re.IGNORECASE)

DEFAULT_CURRENCY = "GBP"

#: MongoDB upsert key. ``product_id`` is derived from the URL when not supplied,
#: so adding a new product URL to ``settings.py`` is enough to get a stable,
#: duplicate-free document.
UPSERT_KEY = "product_id"


# ---------------------------------------------------------------------------
# Nested sub-document shapes
# ---------------------------------------------------------------------------


class SizeVariant(TypedDict, total=False):
    """One entry of the "Choose a size" selector."""

    name: str
    available: bool
    price: Optional[float]
    url: Optional[str]


class DeliveryInfo(TypedDict, total=False):
    """Delivery options and returns policy block."""

    summary: Optional[str]
    delivery_options: List[str]
    returns_policy: Optional[str]
    returns_window_days: Optional[int]


class ReviewSummary(TypedDict, total=False):
    """Aggregate rating block plus the individual customer reviews."""

    average_rating: Optional[float]
    total_reviews: Optional[int]
    recommended_percent: Optional[int]
    reviews: List[Dict[str, Any]]


class RelatedProduct(TypedDict, total=False):
    """Stub for a "You may also like" / "Recently viewed" tile."""

    product_id: Optional[str]
    product_name: Optional[str]
    price: Optional[float]
    product_url: Optional[str]
    image_url: Optional[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def product_id_from_url(url: Optional[str]) -> Optional[str]:
    """Return the numeric John Lewis product id for ``url``.

    ``https://www.johnlewis.com/barbour-icons-lowerdale-gilet/p115694591``
    -> ``"115694591"``. Returns ``None`` when the URL has no id segment.
    """
    if not url:
        return None
    match = PRODUCT_ID_PATTERN.search(url)
    return match.group(1) if match else None


def utc_now() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(value: Optional[datetime]) -> datetime:
    """Return ``value`` as a timezone-aware UTC datetime, defaulting to now.

    Naive datetimes are assumed to already be UTC. pymongo stores aware
    datetimes as real BSON dates, so they can be range-queried in MongoDB.
    """
    if not isinstance(value, datetime):
        return utc_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_empty(value: Any) -> bool:
    """True for values that carry no scraped information."""
    return value is None or value == "" or value == [] or value == {}


# ---------------------------------------------------------------------------
# The item itself
# ---------------------------------------------------------------------------


@dataclass
class ProductItem:
    """One John Lewis product.

    Every field is optional and defaults to empty: the site renders only some
    sections per product (a discontinued item has no size selector, a niche
    brand has no reviews), so missing data stays empty rather than invented.
    """

    product_id: str = ""
    product_name: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    currency: str = DEFAULT_CURRENCY
    sizes: List[SizeVariant] = field(default_factory=list)
    availability: Optional[str] = None
    product_url: Optional[str] = None
    product_images: List[str] = field(default_factory=list)
    description: Optional[str] = None
    product_specification: Dict[str, str] = field(default_factory=dict)
    delivery_and_returns: DeliveryInfo = field(default_factory=dict)
    customer_reviews: ReviewSummary = field(default_factory=dict)
    related_products: List[RelatedProduct] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        """Normalise values and back-fill ``product_id`` from the URL."""
        if not self.product_id and self.product_url:
            self.product_id = product_id_from_url(self.product_url) or ""

        self.currency = (self.currency or DEFAULT_CURRENCY).strip().upper()

        self.sizes = list(self.sizes or [])
        self.product_images = [str(url) for url in (self.product_images or [])]
        self.product_specification = dict(self.product_specification or {})
        self.delivery_and_returns = dict(self.delivery_and_returns or {})
        self.customer_reviews = dict(self.customer_reviews or {})
        self.related_products = list(self.related_products or [])
        self.scraped_at = ensure_utc(self.scraped_at)

    # -- serialisation -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return every field as a plain ``dict``, ready for pymongo."""
        return asdict(self)

    def filled_dict(self) -> Dict[str, Any]:
        """Return only the fields that actually carry data.

        The exporter uses this for ``$set`` so that a page section which fails
        to render this run (reviews, specifications, ...) does not blank out a
        good value stored by an earlier run. ``product_id`` is always kept
        because it is the upsert key.
        """
        return {
            name: value
            for name, value in self.to_dict().items()
            if name == UPSERT_KEY or not _is_empty(value)
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProductItem":
        """Build an item from a parser dict or Mongo document.

        Unknown keys are ignored, so the parser can pass a wider dict.
        """
        known = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})

    # -- helpers -----------------------------------------------------------

    def mark_scraped(self, when: Optional[datetime] = None) -> "ProductItem":
        """Stamp the scrape time and return ``self`` for chaining."""
        self.scraped_at = ensure_utc(when)
        return self


#: Field names in declaration order - handy for projections and validation.
FIELD_NAMES: Tuple[str, ...] = tuple(f.name for f in fields(ProductItem))
