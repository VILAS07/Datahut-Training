from pymongo import MongoClient


class MongoDBExporter:

    def __init__(
        self,
        uri="mongodb://localhost:27017/",
        database="sephora_db",
        collection="makeup_products"
    ):

        self.client = MongoClient(uri)

        self.db = self.client[database]

        self.collection = self.db[collection]

        # Prevent duplicate product URLs
        self.collection.create_index(
            "url",
            unique=True
        )

    def export_one(self, product):

        if not product:
            return False

        url = product.get("url")

        if not url:
            return False

        result = self.collection.update_one(
            {"url": url},
            {"$set": product},
            upsert=True
        )

        if result.upserted_id:
            print("MongoDB: NEW product inserted")
        else:
            print("MongoDB: product updated")

        return True

    def count(self):

        return self.collection.count_documents({})

    def close(self):

        self.client.close()