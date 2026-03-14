from endee import Endee, Precision


class EndeeClient:

    def __init__(self):
        self.client = Endee()

    def health_check(self):
        try:
            self.client.list_indexes()
            return True
        except Exception as e:
            print(f"Endee health check failed: {e}")
            return False

    def ensure_index(self, name="business_records", dimension=384):
        """
        Ensures index exists. If it already exists, skip creation.
        """
        try:
            indexes = self.client.list_indexes()

            # extract index names
            existing_names = [idx["name"] if isinstance(idx, dict) else idx for idx in indexes]

            if name in existing_names:
                print(f"Index '{name}' already exists.")
                return

            print(f"Creating index: {name}")

            self.client.create_index(
                name=name,
                dimension=dimension,
                space_type="cosine",
                precision=Precision.INT8
            )

            print(f"Index '{name}' created successfully.")

        except Exception as e:
            # Ignore conflict error if index already exists
            if "already exists" in str(e):
                print(f"Index '{name}' already exists (conflict ignored).")
            else:
                print(f"Error ensuring index: {e}")
                raise

    def get_index(self, name="business_records"):
        try:
            return self.client.get_index(name)
        except Exception as e:
            print(f"Error retrieving index '{name}': {e}")
            raise

    def upsert_vectors(self, vectors, name="business_records", batch_size=1000):
        """
        Insert vectors in batches (Endee limit = 1000 per batch)
        """
        try:
            index = self.get_index(name)

            total_vectors = len(vectors)
            print(f"Upserting {total_vectors} vectors into '{name}'")

            for i in range(0, total_vectors, batch_size):

                batch = vectors[i:i + batch_size]

                print(f"Uploading batch {i} → {i + len(batch)}")

                index.upsert(batch)

            print("All vectors inserted successfully.")

        except Exception as e:
            print(f"Vector upsert failed: {e}")
            raise

    def search_vectors(self, query_vector, name="business_records", top_k=5, metadata_filter=None):
        try:
            index = self.get_index(name)

            # Endee supports payload filtering (MongoDB-style) according to official docs.
            # SDK parameter naming can vary by version, so we try a few common names and
            # gracefully fall back to vector-only search if unsupported.
            base_kwargs = {
                "vector": query_vector,
                "top_k": top_k,
            }

            if metadata_filter:
                for filter_kw in ("filter", "filters", "payload_filter", "where"):
                    try:
                        results = index.query(**{**base_kwargs, filter_kw: metadata_filter})
                        return results
                    except TypeError:
                        continue

            results = index.query(**base_kwargs)

            return results

        except Exception as e:
            print(f"Vector search failed: {e}")
            return []