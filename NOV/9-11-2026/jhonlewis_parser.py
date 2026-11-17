import logging
import requests
from parsel import Selector
from pymongo import MongoClient
import json
from jhonlewis_settings import MONGO_HOST, MONGO_DB, MONGO_COLLECTION_DATA, MONGO_COLLECTION_RESPONSE, HEADERS
class Parser:
    """parser"""

    def __init__(self):
        self.mongo = MongoClient(MONGO_HOST)  # mongo connect
        self.db = self.mongo[MONGO_DB]
        self.collection = self.db[MONGO_COLLECTION_DATA]
        self.url_collection = self.db[MONGO_COLLECTION_RESPONSE]
        self.queue = ''


    def start(self):
        """start code"""

        ##########used for fetching inputs from queue##########
        # while True:
        #     url = self.queue.get()
        #     if not url:
        #         break
        ##########used for fetching inputs from queue##########

        metas = list(self.url_collection.find({},{'_id':0}))
        for meta in metas:
            url = meta.get('product_url')
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                self.parse_item(url, response)
            else:
                logging.error(f"Failed to fetch URL: {url} with status code: {response.status_code}")


    
    
    
        
    def parse_item(self, url, response):
        """Extract product details from the product page."""

        sel = Selector(text=response.text)

        # EXTRACT JSON-LD
        json_data = sel.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).get()

        data = json.loads(json_data) if json_data else {}

        offers = data.get("offers", [])
        if isinstance(offers, dict):
            offers = [offers]

        price = offers[0].get("price", "") if offers else ""

        # XPATH
        IMAGES_XPATH = '//img[contains(@src, "johnlewiscontent.com/i/JohnLewis/") and not(contains(@src, "wid=34"))]/@src'
        BREADCRUMBS_XPATH = '//nav[@data-test="breadcrumbs"]//ol/li//text()'
        SIZES_XPATH = '//*[@data-testid="size:option:button"]//text()'
        SIZE_FIT_XPATH = '//*[@data-testid="product:size-and-fit:list"]//text()'

        # EXTRACT PRODUCT DETAILS
        product_name = data.get("name", "")
        description = data.get("description", "")
        brand = data.get("brand", {}).get("name", "")
        unique_id = data.get("productId", "")
        category = data.get("category", "")

        images = sel.xpath(IMAGES_XPATH).getall()
        breadcrumbs_list = sel.xpath(BREADCRUMBS_XPATH).getall()

        # EXTRACT SIZES
        sizes = " | ".join(
            x.strip()
            for x in sel.xpath(SIZES_XPATH).getall()
            if x.strip()
        )

        # EXTRACT FIT AND SIZING
        size_fit = " | ".join(
            x.strip()
            for x in sel.xpath(SIZE_FIT_XPATH).getall()
            if x.strip()
        )

        # EXTRACT MATERIAL
        material = data.get("material", "")

        if isinstance(material, list):
            material = " | ".join(
                str(x).strip() for x in material if x
            )

        # CLEAN DATA
        product_name = product_name.strip() if product_name else ""
        description = description.strip() if description else ""

        images = list(dict.fromkeys(
            "https:" + x if x.startswith("//") else x
            for x in images
        ))

        breadcrumbs = [
            " ".join(x.split())
            for x in breadcrumbs_list
            if x.strip()
        ]
        breadcrumbs = ">".join(breadcrumbs)

        # ITEM YIELD
        item = {
            "unique_id": unique_id,
            "pdp_url": url,
            "product_name": product_name,
            "price": price,
            "brand": brand,
            "product_description": description,
            "breadcrumb": breadcrumbs,
            "category": category,
            "image_url": images[0] if images else "",
            "material": material,
            "fit_sizing": size_fit,
            "size": sizes,
            "gender": "Women"
        }

        logging.info(item)

        try:
            self.collection.insert_one(item)
            logging.info("Product saved Successfully")
        except Exception as e:
            logging.error(f"Error saving product: {e}")






    def close(self):
        """connection close"""

        self.mongo.close()

if __name__ == "__main__":
    parser_obj = Parser()
    parser_obj.start()
    parser_obj.close()
