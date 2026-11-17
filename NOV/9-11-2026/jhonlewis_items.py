from mongoengine import DynamicDocument, StringField, BooleanField, DictField, ListField, IntField, FloatField
from jhonlewis_settings import MONGO_COLLECTION_DATA, MONGO_COLLECTION_RESPONSE


class ProductItem(DynamicDocument):
    """initializing URL fields and its Data-Types"""

    meta = {"db_alias": "default", "collection": MONGO_COLLECTION_DATA}
    url = StringField()
    product_name = StringField()
    brand = StringField()
    currency = StringField()
    review_dict_list = ListField()


class ProductUrlItem(DynamicDocument):
    """initializing URL fields and its Data-Types"""

    meta = {"db_alias": "default", "collection": MONGO_COLLECTION_RESPONSE}
    url = StringField(required=True)

