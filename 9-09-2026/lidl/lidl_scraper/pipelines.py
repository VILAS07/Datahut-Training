"""Pipelines for the Lidl scraper.

- DedupeByUrlPipeline: drop products whose URL was already collected.
- RequiredFieldsPipeline: a "valid" record needs Name and Price; ratings may be
  missing if a product has no reviews (we still keep the record but the spider
  counts validity as name+price present).
"""

import logging
from scrapy.exceptions import DropItem

log = logging.getLogger(__name__)


class DedupeByUrlPipeline:
    def __init__(self):
        self.seen = set()

    def process_item(self, item, spider):
        url = (item.get("url") or "").split("?")[0]
        if not url:
            raise DropItem("missing url")
        if url in self.seen:
            raise DropItem(f"duplicate product url: {url}")
        self.seen.add(url)
        return item


class RequiredFieldsPipeline:
    """Require name and price; fill missing numeric fields with empty string."""

    REQUIRED = ("name", "price")

    def process_item(self, item, spider):
        missing = [f for f in self.REQUIRED if not (item.get(f) or "").strip()]
        if missing:
            raise DropItem(f"missing required fields {missing}: {item.get('url')}")
        # normalise: strip whitespace everywhere
        for k, v in item.items():
            if isinstance(v, str):
                item[k] = v.strip()
        # ensure ratings exist as strings (may legitimately be '' when no reviews)
        for k in ("review_count", "quality", "price_rating", "availability"):
            if item.get(k) is None:
                item[k] = ""
        return item
