from .endee_client import EndeeClient
from .embeddings import EmbeddingService
import logging

logger = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self):
        self.endee_client = EndeeClient()
        self.embedding_service = EmbeddingService()

    def retrieve_relevant_rows(self, query, index_name="business_records", top_k=15):
        query_vector = self.embedding_service.generate_embedding(query).tolist()
        results = self.endee_client.search_vectors(query_vector, name=index_name, top_k=top_k)
        
        logger.info(f"Retrieved {len(results)} results for query: {query}")
        
        formatted_results = []
        for item in results:
            formatted_results.append({
                'score': item.get('similarity', 0),
                'metadata': item.get('meta', {}).get('original_row', {}),
                'text': item.get('meta', {}).get('text', '')
            })
        return formatted_results

    def generate_insight(self, query, retrieved_rows):
        if not retrieved_rows:
            return "No relevant data found to generate insights. Try a different query."

        # Analyze retrieved rows to extract dynamic patterns
        all_metadata = [row.get('metadata', {}) for row in retrieved_rows]
        
        # 1. Identify key entities (Products, Clients, etc.)
        entity_counts = {}
        for meta in all_metadata:
            for k, v in meta.items():
                if any(word in k.lower() for word in ['product', 'item', 'client', 'customer', 'industry', 'purpose']):
                    val = str(v).strip()
                    if val and val.lower() != 'nan':
                        entity_counts[f"{k}: {val}"] = entity_counts.get(f"{k}: {val}", 0) + 1
        
        # Sort entities by frequency
        sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)
        top_entities = [e[0] for e in sorted_entities[:5]]

        # 2. Build a truly dynamic response based on the actual data retrieved
        insight = f"### AI Business Intelligence Report\n\n"
        insight += f"Analysis of **{len(retrieved_rows)}** records retrieved from Endee for the query: *\"{query}\"*\n\n"
        
        if top_entities:
            insight += "#### 📊 Top Data Correlations\n"
            insight += "The following attributes appear most frequently in the context of your search:\n"
            for entity in top_entities:
                insight += f"- **{entity}**\n"
            insight += "\n"

        # 3. Dynamic reasoning based on the query type
        insight += "#### 🧠 AI Reasoning & Observations\n"
        
        # Check for numerical patterns if possible
        numeric_sums = {}
        for meta in all_metadata:
            for k, v in meta.items():
                if any(word in k.lower() for word in ['quantity', 'price', 'amount', 'total']):
                    try:
                        val = float(v)
                        numeric_sums[k] = numeric_sums.get(k, 0) + val
                    except:
                        continue
        
        if numeric_sums:
            insight += "Detected significant numerical volume in the following areas:\n"
            for k, v in numeric_sums.items():
                insight += f"- Total **{k}**: {v:,.2f}\n"
            insight += "\n"

        # 4. Contextual Summary
        insight += "#### 🔍 Contextual Summary\n"
        representative_text = retrieved_rows[0].get('text', '')
        insight += f"The most relevant record found describes: *{representative_text}*\n\n"
        
        insight += "#### 💡 Strategic Recommendation\n"
        if "product" in query.lower():
            insight += "Focus inventory and marketing efforts on the high-frequency products identified above, as they show the strongest semantic pull for this query."
        elif "client" in query.lower() or "customer" in query.lower():
            insight += "Prioritize relationship management for the key accounts appearing in this semantic cluster."
        else:
            insight += "The patterns identified suggest a concentrated market segment. Align your business strategy with the primary sectors and entities highlighted in this retrieval."
        
        return insight
