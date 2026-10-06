"""MongoDB exporter for John Lewis products."""

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from settings import (
    MONGO_URI,
    MONGO_DATABASE,
    MONGO_COLLECTION,
)


class MongoExporter:

    def __init__(self):
        print("Connecting to MongoDB...")

        self.client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000
        )

        # Test connection
        self.client.admin.command("ping")

        self.db = self.client[MONGO_DATABASE]
        self.collection = self.db[MONGO_COLLECTION]

        print(
            f"MongoDB connected: "
            f"{MONGO_DATABASE}.{MONGO_COLLECTION}"
        )

        self._setup_indexes()

    def _setup_indexes(self):

        # Check existing indexes first
        indexes = list(self.collection.list_indexes())

        existing_product_index = None

        for index in indexes:
            if index.get("name") == "product_id_1":
                existing_product_index = index
                break

        if existing_product_index:
            print("Existing product_id index found.")
            return

        # Create only if it does not already exist
        try:
            self.collection.create_index(
                [("product_id", 1)],
                unique=True,
                sparse=True,
                name="product_id_1",
            )

            print("Created product_id index.")

        except PyMongoError as e:
            print(f"Index creation warning: {e}")

    def save(self, product):

        if not product:
            return False

        try:

            product_id = product.get("product_id")

            if not product_id:
                print("WARNING: Product has no product_id")
                return False

            result = self.collection.update_one(
                {"product_id": product_id},
                {"$set": product},
                upsert=True,
            )

            if result.upserted_id:
                print(f"MongoDB INSERT: {product_id}")
            else:
                print(f"MongoDB UPDATE: {product_id}")

            return True

        except PyMongoError as e:
            print(f"MongoDB ERROR: {e}")
            return False

    def close(self):
        self.client.close()
        print("MongoDB connection closed.")