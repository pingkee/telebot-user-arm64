from sentence_transformers import SentenceTransformer
import shutil

model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
save_path = "./emb_model"
model.save(save_path)
print(f"Model saved to {save_path}")