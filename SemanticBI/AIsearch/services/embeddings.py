from sentence_transformers import SentenceTransformer
import numpy as np

# Singleton model to improve performance
model = SentenceTransformer("all-MiniLM-L6-v2")

class EmbeddingService:
    def __init__(self):
        self.dimension = 384

    def generate_embedding(self, text):
        embedding = model.encode(text)
        return embedding

    def generate_embeddings_batch(self, text_list):
        embeddings = model.encode(text_list)
        return embeddings
