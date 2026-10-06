from pymongo import MongoClient


class MongoDBExporter:

    def __init__(
        self,
        uri="mongodb://localhost:27017/",
        database="haraj_db",
        collection="properties"
    ):
        self.client = MongoClient(uri)
        self.db = self.client[database]
        self.collection = self.db[collection]

        # Prevent duplicate advertisements
        self.collection.create_index(
            "ad_id",
            unique=True
        )

    def export_one(self, item):

        if not item:
            return False

        if hasattr(item, "to_dict"):
            data = item.to_dict()
        elif hasattr(item, "__dict__"):
            data = item.__dict__.copy()
        else:
            data = dict(item)

        ad_id = data.get("ad_id")

        if not ad_id:
            print("Skipping item: no ad_id")
            return False

        result = self.collection.update_one(
            {"ad_id": ad_id},
            {"$set": data},
            upsert=True
        )

        if result.upserted_id:
            print(f"MongoDB: NEW advertisement inserted - {ad_id}")
        else:
            print(f"MongoDB: advertisement updated - {ad_id}")

        return True

    def count(self):
        return self.collection.count_documents({})

    def close(self):
        self.client.close()