from datetime import datetime
import calendar
import logging
import pytz
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# basic details
PROJECT = ""
CLIENT_NAME = ""
PROJECT_NAME = "john_lewis"
FREQUENCY = ""
BASE_URL = "https://www.johnlewis.com/"


datetime_obj = datetime.now(pytz.timezone("Asia/Kolkata"))

iteration = datetime_obj.strftime("%Y_%m_%d")
YEAR = datetime_obj.strftime("%Y")
MONTH = datetime_obj.strftime("%m")
DAY = datetime_obj.strftime("%d")
MONTH_VALUE = calendar.month_abbr[int(MONTH.lstrip("0"))]
WEEK = (int(DAY) - 1) // 7 + 1

FILE_NAME = f"johnlewis_{iteration}"

# Mongo db and collections
MONGO_HOST = os.environ["MONGO_HOST"]
MONGO_DB = "jhon_lewis"
MONGO_COLLECTION_RESPONSE = f"{PROJECT_NAME}_url"
MONGO_COLLECTION_CATEGORY = f"{PROJECT_NAME}_category_url"
MONGO_COLLECTION_URL_FAILED = f"{PROJECT_NAME}_url_failed"
MONGO_COLLECTION_DATA = f"{PROJECT_NAME}_data"

# Queue details
QUEUE_NAME_URL = f"{PROJECT_NAME}_urls"
QUEUE = ""

# Headers and useragents and other variables
SHARD_COLLECTION = [
    {'col': MONGO_COLLECTION_RESPONSE, 'unique': True, 'indexfield': "url"},
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Priority': 'u=0, i',
}
 
