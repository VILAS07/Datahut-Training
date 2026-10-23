from mongoengine import (
    DynamicDocument, StringField, ListField, IntField, FloatField, DictField,
)
from mongoengine import connect, disconnect
from settings import (
    MONGO_URI, MONGO_DB, MONGO_MOCK,
    MONGO_COL_URL, MONGO_COL_URL_FAILED, MONGO_COLLECTION_DATA,
)


def connect_db():
    """connect mongoengine (alias default)"""
    if MONGO_MOCK:
        import mongomock
        return connect(MONGO_DB, alias="default", mongo_client_class=mongomock.MongoClient)
    return connect(MONGO_DB, host=MONGO_URI, alias="default")


def close_db():
    disconnect("default")


class ProductItem(DynamicDocument):
    """Product data. One document per perfume page."""

    meta = {"db_alias": "default", "collection": MONGO_COLLECTION_DATA}
    website = StringField()
    extraction_date = StringField()
    product_id = StringField(required=True)
    pdp_url = StringField(required=True)
    product_name = StringField()
    brand = StringField()
    brand_url = StringField()
    brand_logo = StringField()
    gender = StringField()
    launch_year = StringField()
    fragrance_family = StringField()
    perfumer = StringField()
    description = StringField()
    main_image = StringField()
    main_accords = ListField(DictField())     # [{"accord": "sweet", "strength": 100}, ...]
    top_notes = ListField(StringField())
    middle_notes = ListField(StringField())
    base_notes = ListField(StringField())
    rating_value = StringField()
    rating_count = StringField()
    review_count = StringField()
    reviews_scraped = IntField()
    also_like = ListField(DictField())        # [{"name":..., "brand":..., "url":...}]
    amazon_title = StringField()
    amazon_price = StringField()
    amazon_currency = StringField()
    amazon_url = StringField()
    reviews = ListField(DictField())          # one dict per review


class ProductUrlItem(DynamicDocument):
    """Product urls (id, pdp_url)."""

    meta = {"db_alias": "default", "collection": MONGO_COL_URL}
    pdp_url = StringField(required=True)


class ProductFailedItem(DynamicDocument):
    """Urls that could not be fetched or parsed."""

    meta = {"db_alias": "default", "collection": MONGO_COL_URL_FAILED}
    pdp_url = StringField(required=True)
