from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")

db = client["opensooq_db"]

collection = db["properties"]

print("Mongo DB Connected Successfully")


def save_to_mongodb(data):

    result = collection.update_one(
        {"url": data["url"]},
        {"$set": data},
        upsert=True
    )

    if result.upserted_id:
        print("Inserted document ID:", result.upserted_id)
    else:
        print("Updated:", data["url"])