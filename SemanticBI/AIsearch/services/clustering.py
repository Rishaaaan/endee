from sklearn.cluster import KMeans
import numpy as np

class ClusteringService:
    def __init__(self, n_clusters=5):
        self.n_clusters = n_clusters

    def run_kmeans(self, embeddings):
        kmeans = KMeans(n_clusters=self.n_clusters, random_state=42)
        clusters = kmeans.fit_predict(embeddings)
        return clusters

    def generate_cluster_summary(self, clusters, metadata_list):
        summaries = {}
        for cluster_id in range(self.n_clusters):
            cluster_items = [metadata_list[i] for i, cid in enumerate(clusters) if cid == cluster_id]
            summaries[f"Cluster {cluster_id + 1}"] = {
                "count": len(cluster_items),
                "examples": cluster_items[:3]
            }
        return summaries
