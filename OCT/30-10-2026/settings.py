from datetime import datetime
import os
import calendar
import logging
import configparser
import pytz
from dateutil.relativedelta import relativedelta, MO
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# basic details
PROJECT = "mango"
CLIENT_NAME = ""
PROJECT_NAME = "mango"
FREQUENCY = ""
BASE_URL = "https://shop.mango.com"


datetime_obj = datetime.now(pytz.timezone("Asia/Kolkata"))

iteration = datetime_obj.strftime("%Y_%m_%d")
# YEAR = datetime_obj.strftime("%Y")
# MONTH = datetime_obj.strftime("%m")
# DAY = datetime_obj.strftime("%d")
# MONTH_VALUE = calendar.month_abbr[int(MONTH.lstrip("0"))]
# WEEK = (int(DAY) - 1) // 7 + 1

REQUEST_DELAY = 2  # seconds between page requests
MAX_RETRY = 5  # retries when blocked (429 etc.)
RETRY_WAIT = 10  # seconds, multiplied by retry count

FILE_NAME = f"MANGO_{iteration}"

# Mongo db and collections
MONGO_DB = f"MANGO_{iteration}"
MONGO_COLLECTION_RESPONSE = f"{PROJECT_NAME}_url"
MONGO_COLLECTION_CATEGORY = f"{PROJECT_NAME}_category_url"
MONGO_COLLECTION_URL_FAILED = f"{PROJECT_NAME}_url_failed"
MONGO_COLLECTION_DATA = f"{PROJECT_NAME}_data"
MONGO_HOST = "localhost"
MONGO_PORT = 27017
MONGO_COL_URL = f"{PROJECT_NAME}_url"


# proxy
# PROXY = ''

# Queue details
QUEUE_NAME_URL = f"{PROJECT_NAME}_urls"
QUEUE = ""

# Headers and useragents and other variables
# SHARD_COLLECTION = [
#     {'col': MONGO_COL_URL, 'unique': True, 'indexfield': "url"}, ]


HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'origin': 'https://shop.mango.com',
    'referer': 'https://shop.mango.com/',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
}



LIST_API_URL = "https://api.shop.mango.com/cs/product-lists-drive-thru/v2/channels/shop/countries/us/catalogs/{catalog}?languageIso=en&page={page}"
DETAIL_API_URL = "https://online-orchestrator.mango.com/v4/products?channelId=shop&countryIso=US&languageIso=en&productId={product_id}"
PRICE_API_URL = "https://online-orchestrator.mango.com/v4/prices/products?channelId=shop&countryIso=US&productId={product_id}"
