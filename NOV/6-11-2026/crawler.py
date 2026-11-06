import logging
from urllib.parse import quote_plus
from parsel import Selector
from mongoengine import connect
from settings import SEARCH_URL, TOP_N, MONGO_DB, MONGO_HOST
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

        keywords = [
            {'keyword': 'mini dress', 'category': 'Dress'},
            {'keyword': 'midi dress', 'category': 'Dress'},
            {'keyword': 'maxi dress', 'category': 'Dress'},
            {'keyword': 'summer dress', 'category': 'Dress'},
            {'keyword': 'knitted dress', 'category': 'Dress'},
            {'keyword': 'wide leg jeans', 'category': 'Jeans'},
            {'keyword': 'straight leg jeans', 'category': 'Jeans'},
            {'keyword': 'skinny jeans', 'category': 'Jeans'},
            {'keyword': 'flared jeans', 'category': 'Jeans'},
            {'keyword': 'high waist jeans', 'category': 'Jeans'},
            {'keyword': 'fine-knit jumper', 'category': 'Knitwear'},
            {'keyword': 'fine-knit cardigan', 'category': 'Knitwear'},
            {'keyword': 'turtleneck jumper', 'category': 'Knitwear'},
            {'keyword': 'oversized jumper', 'category': 'Knitwear'},
            {'keyword': 'knitted top', 'category': 'Knitwear'},
            {'keyword': 'crop top', 'category': 'Tops'},
            {'keyword': 'tank top', 'category': 'Tops'},
            {'keyword': 'vest top', 'category': 'Tops'},
            {'keyword': 'long sleeve top', 'category': 'Tops'},
        ]
        for data in keywords:

            meta = {}
            meta['keyword'] = data.get('keyword')
            meta['category'] = data.get('category')

            api_url = SEARCH_URL.format(keyword=quote_plus(data.get('keyword')))  # generate search Url

            response = requests.get(api_url, impersonate="chrome")
            if response.status_code == 200:
                self.parse_item(response, meta)

            # else:
            #     self.queue.publish(data) ##########used for requeuing

    def parse_item(self, response, meta):
        """item part"""

        sel = Selector(text=response.text)

        # XPATH
        PRODUCTS_XPATH = '//article//a[@data-card-type="media" and contains(@href,".html")]/@href'

        # EXTRACT
        products = sel.xpath(PRODUCTS_XPATH).extract()

        for rank, url in enumerate(products[:TOP_N], start=1):

            # ITEM YEILD
            item = {}
            item["url"] = url
            item["unique_id"] = f"{meta.get('keyword')}_{url}"
            item["keyword"] = meta.get('keyword')
            item["category"] = meta.get('category')
            item["retailer"] = "Zalando"
            item["gender"] = "Women"
            item["rank"] = rank
            try:
                # db[collection].insert_one(item)

                # product_item = ProductUrlItem(**item)
                # self.mongo.process(product_item,collection=MONGO_COL_URL)  # Mongo insert using items

                product_item = ProductUrlItem(**item)
                product_item.save()

            except:
                pass

    def close(self):
        """Close function for all module object closing"""

        self.mongo.close()


if __name__ == "__main__":
    crawler = Crawler()
    crawler.start()
    crawler.close()
