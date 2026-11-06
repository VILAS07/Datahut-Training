import re
import json
import logging
from time import sleep
from parsel import Selector
from mongoengine import connect
from settings import MONGO_COLLECTION_DATA, MONGO_DB, MONGO_HOST
from items import ProductItem, ProductUrlItem
from curl_cffi import requests


class Parser:
    """parser"""

    def __init__(self):
        self.queue = ''   # queue connect
        self.mongo = connect(db=MONGO_DB, host=MONGO_HOST, alias="default")  # mongo connect

    def start(self):
        """start code"""

        ##########used for fetching inputs from queue##########
        # while True:
        #     url = self.queue.get()
        #     if not url:
        #         break
        ##########used for fetching inputs from queue##########

        metas = [{'url': doc.url, 'keyword': doc.keyword, 'category': doc.category, 'retailer': doc.retailer, 'gender': doc.gender, 'rank': doc.rank, 'unique_id': doc.unique_id} for doc in ProductUrlItem.objects]
        for meta in metas:
            url = meta.get('url')
            if ProductItem.objects(unique_id=meta.get('unique_id')).first():
                continue
            try:
                response = requests.get(url, impersonate="chrome", timeout=60)
            except Exception as e:
                logging.warning(f"request failed {url} {e}")
                continue
            if response.status_code == 200:
                self.parse_item(url, response, meta)
            else:
                logging.warning(f"status {response.status_code} {url}")
            sleep(3)
            # else:
            #     self.queue.publish(url)##########used for requeuing

    def parse_item(self, url, response, meta):
        """item part"""

        sel = Selector(text=response.text)

        # XPATH
        CANONICAL_XPATH = '//link[@rel="canonical"]/@href'
        JSON_XPATH = '//script[@type="application/ld+json"]/text()'
        MATERIAL_XPATH = '//div[@data-testid="pdp-accordion-material_care"]//dl/div'
        DETAILS_XPATH = '//div[@data-testid="pdp-accordion-details"]//dl/div'
        FIT_XPATH = '//div[@data-testid="pdp-accordion-size_fit"]//dl/div'
        PAGE_DATA_XPATH = '//script[contains(text(),"displayPrice")]/text()'

        # EXTRACT
        canonical = sel.xpath(CANONICAL_XPATH).extract_first()
        product_json = sel.xpath(JSON_XPATH).extract_first()
        material_list = sel.xpath(MATERIAL_XPATH)
        details_list = sel.xpath(DETAILS_XPATH)
        fit_list = sel.xpath(FIT_XPATH)
        page_data = sel.xpath(PAGE_DATA_XPATH).extract_first()

        # CLEAN
        url = canonical if canonical else url
        data = json.loads(product_json) if product_json else {}
        data = data[0] if isinstance(data, list) else data
        variants = data.get('hasVariant') or [{}]

        product_name = (data.get('name') or "").strip()
        brand = (data.get('brand') or {}).get('name', "")
        color = (data.get('color') or "").strip()
        offers = variants[0].get('offers') or {}
        currency = offers.get('priceCurrency') or ""
        sizes = [x.get('size') for x in variants if x.get('size')]
        image = data.get('image', [""])[0].split("?")[0].strip() if data.get('image') else ""

        # price pattern - original price is always present, promotional price only on sale items
        page_data = page_data.replace('\\"', '"') if page_data else ""
        price_match = re.search(r'"displayPrice":\{"original":\{"formatted":"(.*?)"\}(?:,"promotional":\{"formatted":"(.*?)"\})?', page_data)
        original_price = re.sub(r"[^\d.]", "", price_match.group(1)) if price_match else ""
        promotional_price = re.sub(r"[^\d.]", "", price_match.group(2)) if price_match and price_match.group(2) else ""
        price = promotional_price if promotional_price else original_price
        discount = re.search(r'"productFlags":\[\{"formatted":"(-\d+%)"', page_data)
        discount = discount.group(1) if discount else ""

        material = []
        care = ""
        for attribute in material_list:
            key = attribute.xpath("normalize-space(./dt)").extract_first().rstrip(":").strip()
            value = attribute.xpath("normalize-space(./dd)").extract_first().strip()
            if key == "Care instructions":
                care = value
            else:
                material.append(f"{key}: {value}")
        material = ", ".join(material)

        description = []
        style = []
        for attribute in details_list:
            key = attribute.xpath("normalize-space(./dt)").extract_first().rstrip(":").strip()
            value = attribute.xpath("normalize-space(./dd)").extract_first().strip()
            if key != "Article number":
                description.append(f"{key}: {value}")
            if key in ("Pattern", "Neckline", "Collar", "Occasion", "Style"):
                style.append(f"{key}: {value}")
        description = ", ".join(description)
        style = ", ".join(style)

        fit = []
        for attribute in fit_list:
            key = attribute.xpath("normalize-space(./dt)").extract_first().rstrip(":").strip()
            value = attribute.xpath("normalize-space(./dd)").extract_first().strip()
            fit.append(f"{key}: {value}")
        fit = ", ".join(fit)

        product_type = re.search(r'"leadingCategory":\{"id":"\d+","name":"(.*?)"', page_data)
        product_type = product_type.group(1) if product_type else ""

        # ITEM YEILD
        item = {}
        item["url"] = url
        item["unique_id"] = f"{meta.get('keyword')}_{url}"
        item["keyword"] = meta.get('keyword')
        item["retailer"] = meta.get('retailer')
        item["rank"] = meta.get('rank')
        item["product_name"] = product_name
        item["brand"] = brand
        item["sizes"] = sizes
        item["description"] = description
        item["product_type"] = product_type
        item["category"] = meta.get('category')
        item["price"] = price
        item["original_price"] = original_price
        item["discount"] = discount
        item["currency"] = currency
        item["image"] = image
        item["color"] = color
        item["gender"] = meta.get('gender')
        item["material_composition"] = material
        item["care"] = care
        item["fit"] = fit
        item["style"] = style

        # product_item = ProductItem(**item)
        # self.mongo.process(product_item,collection=MONGO_COLLECTION_DATA)  # Mongo insert using items

        logging.info(item)
        try:
            # db[collection].insert_one(item)
            product_item = ProductItem(**item)
            product_item.save()
        except:
            pass

    def close(self):
        """connection close"""

        self.mongo.close()


if __name__ == "__main__":
    parser_obj = Parser()
    parser_obj.start()
    parser_obj.close()
