from mongoengine import DynamicDocument, StringField, BooleanField, DictField, ListField, IntField, FloatField
#from settings import (
#    MONGO_COL_URL, MONGO_COLLECTION_EMPTY,
#    MONGO_COLLECTION_URL_FAILED,
#    MONGO_COLLECTION_DATA, MONGO_COLLECTION_MISMATCH,
#    MONGO_COLLECTION_RESPONSE, MONGO_COLLECTION_IMAGES, MONGO_COLLECTION_CATEGORY,
#    MONGO_COLLECTION_STORE_CODE, MONGO_COLLECTION_COUNT, MONGO_COLLECTION_PAGINATION
#
#)
from settings import (
    MONGO_COLLECTION_DATA,
    MONGO_COL_URL,
    MONGO_COLLECTION_URL_FAILED
)


class ProductItem(DynamicDocument):
    """initializing URL fields and its Data-Types"""

    meta = {"db_alias": "default", "collection": MONGO_COLLECTION_DATA}
    unique_id = StringField(unique=True)
    url = StringField()
    rank = IntField()
    product_name = StringField()
    brand = StringField()
    original_price = StringField()
    price = StringField()
    currency = StringField()
    discount = StringField()
    description = StringField()
    sizes = ListField()
    product_type = StringField()
    image = StringField()
    color = StringField()
    gender = StringField()
    material_composition = StringField()
    fit = StringField()
    style = StringField()
    category = StringField()
    care = StringField()


class ProductUrlItem(DynamicDocument):
    """initializing URL fields and its Data-Types"""

    meta = {"db_alias": "default", "collection": MONGO_COL_URL}
    url = StringField(required=True)
    unique_id = StringField(required=True, unique=True)


class ProductMismatchItem(DynamicDocument):
    """initializing URL fields and its Data-Types"""

    #meta = {"db_alias": "default", "collection": MONGO_COLLECTION_MISMATCH}
    input_style = StringField(required=True)


class ProductEmptyItem(DynamicDocument):
    """initializing URL fields and its Data-Types"""

    #meta = {"db_alias": "default", "collection": MONGO_COLLECTION_EMPTY}
    input_style = StringField(required=True)


class ProductCountItem(DynamicDocument):
    """initializing URL fields and its Data-Types"""

    #meta = {"db_alias": "default", "collection": MONGO_COLLECTION_COUNT}
    zipcode = StringField(required=True)


class ProductResponseItem(DynamicDocument):
    """initializing URL fields and its Data-Types"""

    #meta = {"db_alias": "default", "collection": MONGO_COLLECTION_RESPONSE}
    url = StringField(required=True)


class ProductFailedItem(DynamicDocument):
    """initializing URL fields and its Data-Types"""

    meta = {"db_alias": "default", "collection": MONGO_COLLECTION_URL_FAILED}
    url = StringField(required=True)


class ProductCategoryUrlItem(DynamicDocument):
    """initializing URL fields and its Data-Types"""

    #meta = {"db_alias": "default", "collection": MONGO_COLLECTION_CATEGORY}

    url = StringField(required=True)


class ProductPageItem(DynamicDocument):
    """initializing URL fields and its Data-Types"""

    #meta = {"db_alias": "default", "collection": MONGO_COLLECTION_PAGINATION}
    url = StringField(required=True)
