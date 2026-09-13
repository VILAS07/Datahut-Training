"""Pipelines for the Flipkart scraper."""

import logging
from scrapy.exceptions import DropItem

log = logging.getLogger(__name__)


class DedupeByUrlPipeline:
    def __init__(self):
        self.seen = set()

    def process_item(self, item, spider):
        url = (item.get("product_url") or "").split("?")[0]
        if not url:
            raise DropItem("missing product_url")
        if url in self.seen:
            raise DropItem(f"duplicate product url: {url}")
        self.seen.add(url)
        return item


class RequiredFieldsPipeline:
    """A valid record needs name + price (the fields that define a product)."""

    def process_item(self, item, spider):
        for k, v in list(item.items()):
            if isinstance(v, str):
                item[k] = v.strip()
        if not (item.get("name") and item.get("price")):
            raise DropItem(f"missing name/price: {item.get('product_url')}")
        return item
