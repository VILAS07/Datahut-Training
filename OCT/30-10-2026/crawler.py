import logging
import json
from mongoengine import connect
from settings import HEADERS, LIST_API_URL, BASE_URL, MONGO_DB, MONGO_HOST
from items import ProductUrlItem
from curl_cffi import requests


class Crawler:
    """Crawling Urls"""

    def __init__(self):
        self.mongo = connect(db=MONGO_DB, host=MONGO_HOST, alias="default")  # connect mongodb


    def start(self):
        """Requesting Start url"""

        ##########used for fetching inputs from queue##########
        # while True:
        #     data = self.queue.get()
        #     if not data:
        #         logging.warning("No item in queue")
        #         break
        ##########used for fetching inputs from queue##########

        catalogs = [
            'dest_vertodo_she',
            'dest_vertodo_he'
        ]
        for catalog in catalogs:

            meta = {}
            meta['category'] = catalog
            page = meta.get("page", 1)  # initialising page for pagination

            api_url = LIST_API_URL.format(catalog=catalog, page=page)  # generate api Url

            while True:

                response = requests.get(api_url, headers=HEADERS, impersonate="chrome")
                if response.status_code == 200:
                    is_next = self.parse_item(response, meta)
                    if not is_next:
                        logging.info("Pagination completed")
                        break

                    # pagination crawling
                    page += 1
                    api_url = LIST_API_URL.format(catalog=catalog, page=page)
                    meta["page"] = page

                # else:
                #     self.queue.publish(data) ##########used for requeuing

    def parse_item(self, response, meta):
        """item part"""

        data = json.loads(response.text)

        # EXTRACT
        products = data.get('items')
        if products:
            for product in products:
                url = f"{BASE_URL}/us/en/p/x/x/{product.get('productId')}/{product.get('colorId')}/00"

                # ITEM YEILD
                item = {}
                item["url"] = url
                item["category"] = meta.get('category')
                try:
                     # db[collection].insert_one(item)

                     # product_item = ProductUrlItem(**item)
                     # self.mongo.process(product_item,collection=MONGO_COL_URL)  # Mongo insert using items

                    product_item = ProductUrlItem(**item)
                    product_item.save()

                except:
                    pass

            return meta.get("page", 1) < data.get('totalPages', 0)
        return False

    def close(self):
        """Close function for all module object closing"""

        self.mongo.close()


if __name__ == "__main__":
    crawler = Crawler()
    crawler.start()
    crawler.close()
