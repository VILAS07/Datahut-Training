from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")

db = client["sephora_db"]
collection = db["makeup_products"]

result = collection.insert_one({
    "test": "python_connection"
})

print("Inserted ID:", result.inserted_id)
print("Total documents:", collection.count_documents({}))

client.close()