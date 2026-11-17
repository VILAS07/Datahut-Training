import logging
import json
import requests
from parsel import Selector
from pymongo import MongoClient
from jhonlewis_settings import HEADERS, BASE_URL, MONGO_HOST, MONGO_DB, MONGO_COLLECTION_RESPONSE, MONGO_COLLECTION_URL_FAILED

class Crawler:
    """Crawling Urls"""

    def __init__(self):
        self.mongo = MongoClient(MONGO_HOST)
        self.mongo.admin.command('ping')
        print("MongoDB connected successfully!")
        self.mongo = MongoClient(MONGO_HOST)  # connect mongodb
        self.db = self.mongo[MONGO_DB]  # connect mongodb database
        self.collection = self.db[MONGO_COLLECTION_RESPONSE]  # connect mongodb collection
        self.failed_collection = self.db[MONGO_COLLECTION_URL_FAILED]  # connect mongodb collection for failed urls
        self.queue = ''  # connect queue if needed

    def start(self):
        """Requesting Start url"""

        ##########used for fetching inputs from queue##########
        # while True:
        #     data = self.queue.get()
        #     if not data:
        #         logging.warning("No item in queue")
        #         break
        ##########used for fetching inputs from queue##########

        metas = [
            {'category': 'Dress', 'keyword': 'Mini dress'},
            {'category': 'Dress', 'keyword': 'Midi dress'},
            {'category': 'Dress', 'keyword': 'Maxi dress'},
            {'category': 'Dress', 'keyword': 'Summer dress'},
            {'category': 'Dress', 'keyword': 'Knitted dress'},

            {'category': 'Jeans', 'keyword': 'Wide leg jeans'},
            {'category': 'Jeans', 'keyword': 'Straight leg jeans'},
            {'category': 'Jeans', 'keyword': 'Skinny jeans'},
            {'category': 'Jeans', 'keyword': 'Flared jeans'},
            {'category': 'Jeans', 'keyword': 'High waist jeans'},

            {'category': 'Knitwear', 'keyword': 'Fine-knit jumper'},
            {'category': 'Knitwear', 'keyword': 'Fine-knit cardigan'},
            {'category': 'Knitwear', 'keyword': 'Turtleneck jumper'},
            {'category': 'Knitwear', 'keyword': 'Oversized jumper'},
            {'category': 'Knitwear', 'keyword': 'Knitted top'},

            {'category': 'Tops', 'keyword': 'Crop top'},
            {'category': 'Tops', 'keyword': 'Tank top'},
            {'category': 'Tops', 'keyword': 'Vest top'},
            {'category': 'Tops', 'keyword': 'Long sleeve top'},
            {'category': 'Tops', 'keyword': 'Knitted top'}
        ]
        for meta in metas:
            category = meta.get('category')
            keyword = meta.get('keyword')
            url = f"{BASE_URL}search"
            response = requests.get(url, params={'search-term': keyword}, headers=HEADERS)
            if response.status_code == 200:
                self.parse_item(response, meta)
            else:
                logging.error(f"Failed to fetch URL: {url} with status code: {response.status_code}")
                self.failed_collection.insert_one({
                  'url': url,
                  'status_code': response.status_code,
                  'category': category,
                  'keyword': keyword
                })
            
    def parse_item(self, response, meta):
        """item part"""

        sel = Selector(response.text)

        # XPATH
        PRODUCT_XPATH = '//article[@data-testid="product-card-layout"]'
        URL_XPATH = './/a[contains(@href, "/p")]/@href'

        # EXTRACT
        products = sel.xpath(PRODUCT_XPATH)
        products = products[:10]  # Limit to first 10 products
        if products:
            for product in products:
                rank=products.index(product)+1
                url = product.xpath(URL_XPATH).extract_first()
                if not url:
                    continue
                # ITEM YEILD
                item = {}
                item['rank'] = rank
                item['product_url'] = url
                item['category'] = meta.get('category')
                item['keyword'] = meta.get('keyword')
                logging.info(item)
                try:
                     # db[collection].insert_one(item)
                    
                     # product_item = ProductUrlItem(**item)
                     # self.mongo.process(product_item,collection=MONGO_COL_URL)  # Mongo insert using items
                    if not self.collection.find_one({'product_url': url, 'keyword': meta.get('keyword')}):
                        self.collection.insert_one(item)

                except Exception as e:
                    logging.error(f"MongoDB insertion failed: {e}")

            return True
        return False

    def close(self):
        """Close function for all module object closing"""

        self.mongo.close()


if __name__ == "__main__":
    crawler = Crawler()
    crawler.start()
    crawler.close()
