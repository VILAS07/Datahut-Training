from mongoengine import DynamicDocument, StringField


class ProductUrlItem(DynamicDocument):
    url = StringField(required=True)