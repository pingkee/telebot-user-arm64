from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer
import numpy as np
import json

# Load embedding model
model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

# Connect to Qdrant
client = QdrantClient(host="140.245.110.221", port=6333)

# Recreate collection with cosine similarity
client.recreate_collection(
    collection_name="outreach",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
)

# Normalize function
def normalize(vec):
    norm = np.linalg.norm(vec)
    return vec if norm == 0 else vec / norm

# Load your data
with open("solutions.json", "r") as f:
    documents = json.load(f)

# Prepare and normalize vectors for insertion
points = []
for idx, doc in enumerate(documents):
    embedding = model.encode(doc["text"])
    normalized_vector = normalize(embedding).tolist()
    points.append(PointStruct(id=idx, vector=normalized_vector, payload=doc))

# Insert data into Qdrant
client.upsert(collection_name="outreach", points=points)

print("✅ Cleared old data and inserted fresh, normalized context into Qdrant.")
