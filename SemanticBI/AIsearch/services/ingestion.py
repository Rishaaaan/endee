import pandas as pd
import logging
import numpy as np
from .embeddings import EmbeddingService
from .endee_client import EndeeClient

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self):
        logger.info("Initializing IngestionService and loading EmbeddingService...")
        self.embedding_service = EmbeddingService()
        self.endee_client = EndeeClient()

    def parse_file(self, file_path):
        logger.info(f"Parsing file: {file_path}")
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

        # Replace NaN values
        df = df.fillna("")

        return df

    def row_to_text(self, row):
        # Filter out empty values and join with descriptive labels
        parts = []
        for col in row.index:
            val = str(row[col]).strip()
            if val and val.lower() != 'nan' and val != "":
                parts.append(f"The {col} is {val}.")
        return " ".join(parts)

    def clean_metadata(self, row_dict):
        """
        Converts row values into JSON safe types
        to prevent 'Integer exceeds 64-bit range' errors.
        """
        clean = {}

        for key, value in row_dict.items():

            if value is None:
                clean[key] = ""

            # numpy integers
            elif isinstance(value, np.integer):
                clean[key] = int(value)

            # numpy floats
            elif isinstance(value, np.floating):
                clean[key] = float(value)

            # very large integers → convert to string
            elif isinstance(value, int) and abs(value) > 9223372036854775807:
                clean[key] = str(value)

            # pandas NaN
            elif str(value) == "nan":
                clean[key] = ""

            # fallback (safe for JSON)
            else:
                clean[key] = value

        return clean

    def process_dataset(self, file_path, original_filename, index_name=None):

        logger.info(f"Processing dataset from {file_path}")

        df = self.parse_file(file_path)
        
        # Use provided index_name or generate one from original_filename
        if not index_name:
            import time
            import re
            clean_name = re.sub(r'[^a-zA-Z0-9]', '_', original_filename).lower()
            index_name = f"idx_{clean_name}_{int(time.time())}"
        
        logger.info(f"Ensuring index exists: {index_name}")
        self.endee_client.ensure_index(name=index_name, dimension=384)

        texts = [self.row_to_text(row) for _, row in df.iterrows()]

        logger.info(f"Generating embeddings for {len(texts)} rows...")

        embeddings = self.embedding_service.generate_embeddings_batch(texts)

        vectors = []

        for i, (row_idx, row) in enumerate(df.iterrows()):

            row_dict = row.to_dict()

            safe_row = self.clean_metadata(row_dict)

            vectors.append({
                "id": f"row_{row_idx}",
                "vector": embeddings[i].tolist(),
                "meta": {
                    "text": texts[i],
                    "original_row": safe_row
                }
            })

        logger.info(f"Upserting {len(vectors)} vectors to Endee...")

        self.endee_client.upsert_vectors(vectors, name=index_name)

        logger.info("Ingestion complete.")

        return {
            "total_rows": len(df),
            "index_name": index_name
        }