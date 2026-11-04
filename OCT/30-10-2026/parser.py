import re
import logging
from parsel import Selector
from mongoengine import connect
from settings import MONGO_COLLECTION_DATA, MONGO_DB, MONGO_HOST
from items import ProductItem, ProductUrlItem
from curl_cffi import requests


class Parser:
    """parser"""

    def __init__(self):
        self.queue = ''   # queue connect
        self.mongo = connect(db=MONGO_DB, host=MONGO_HOST,alias="default")  # mongo connect

    def start(self):
        """start code"""

        ##########used for fetching inputs from queue##########
        # while True:
        #     url = self.queue.get()
        #     if not url:
        #         break
        ##########used for fetching inputs from queue##########

        metas = [{'url':doc.url} for doc in ProductUrlItem.objects]
        for meta in metas:
            url = meta.get('url')
            response = requests.get(url, impersonate="chrome")
            if response.status_code==200:
                self.parse_item(url, response)
            # else:
            #     self.queue.publish(url)##########used for requeuing


    def parse_item(self, url, response):
        """item part"""

        sel = Selector(text=response.text)

                # XPATH
        CANONICAL_XPATH = '//link[@rel="canonical"]/@href'
        PRODUCT_NAME_XPATH = '//h1/text()'
        PRICE_XPATH = '//meta[@itemprop="price"]/@content'
        CURRENCY_XPATH = '//meta[@itemprop="priceCurrency"]/@content'
        PROMOTION_XPATH = '//h1/preceding-sibling::ul//span/text()'
        COLOR_XPATH = '//p[span[starts-with(text(),"Color")]]/span[2]/text()'
        SIZES_XPATH = '//ol[@aria-labelledby="product.sizeSelector"]/li//button//span[contains(@class,"withEllipsis")]/text()'
        DESCRIPTION_XPATH = '//meta[@property="og:description"]/@content'
        IMAGES_XPATH = '//img[contains(@src,"media.mango.com/is/image/punto/") and contains(@src,"wid=2048")]/@src'
        BREADCRUMBS_XPATH = '//nav[@aria-label="Breadcrumb"]//li'
        DETAILS_XPATH = '//script[contains(text(),"washingRules")]/text()'

        # EXTRACT
        canonical = sel.xpath(CANONICAL_XPATH).extract_first()
        product_name = sel.xpath(PRODUCT_NAME_XPATH).extract_first()
        price = sel.xpath(PRICE_XPATH).extract_first()
        currency = sel.xpath(CURRENCY_XPATH).extract_first()
        promotion = sel.xpath(PROMOTION_XPATH).extract()
        color = sel.xpath(COLOR_XPATH).extract_first()
        sizes = sel.xpath(SIZES_XPATH).extract()
        description = sel.xpath(DESCRIPTION_XPATH).extract_first()
        images = sel.xpath(IMAGES_XPATH).extract()
        breadcrumbs_list = sel.xpath(BREADCRUMBS_XPATH)
        details = sel.xpath(DETAILS_XPATH).extract_first()

        # CLEAN
        url = canonical if canonical else url
        product_name = product_name.strip() if product_name else ""
        price = price.strip() if price else ""
        currency = currency.strip() if currency else ""
        promotion = ", ".join(x.strip() for x in promotion) if promotion else ""
        color = color.strip() if color else ""
        sizes = list(x.strip() for x in sizes) if sizes else []
        description = description.strip() if description else ""
        images = list(dict.fromkeys(x.split("?")[0].strip() for x in images)) if images else []
        breadcrumbs = []
        for breadcrumb in breadcrumbs_list:
            value = breadcrumb.xpath(".//text()").extract()
            if value:
                value = " ".join(x.strip() for x in value)
                breadcrumbs.append(value)
        breadcrumbs = (">".join(breadcrumbs)).strip() if breadcrumbs else ""

        # url pattern - /us/en/p/<gender>/<category>/<sub category>/<slug>/<product id>/<color id>/00
        path = url.split("/p/")[1].split("?")[0].strip("/").split("/")
        gender = path[0]
        categories = path[1:-4]
        product_id = path[-3]
        color_id = path[-2]

        # composition, care and origin are inside a script tag
        details = details.replace('\\"', '"') if details else ""
        composition = re.search(r'"compositions":\[(.*?)\]', details)
        composition = ", ".join(re.findall(r'"(.*?)"', composition.group(1))) if composition else ""

        # ITEM YEILD
        item = {}
        item["url"] = url
        item["unique_id"] = f"{product_id}_{color_id}"
        item["product_name"] = product_name
        item["brand"] = "Mango"
        item["price"] = price
        item["currency"] = currency
        item["promotion"] = promotion
        item["description"] = description
        item["composition"] = composition
        item["color"] = color
        item["sizes"] = sizes
        item["images"] = images
        item["breadcrumbs"] = breadcrumbs
        item["gender"] = gender
        item["categories"] = categories

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
