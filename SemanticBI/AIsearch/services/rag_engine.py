from .endee_client import EndeeClient
from .embeddings import EmbeddingService
from .llm_client import GroqLLMClient
import logging


logger = logging.getLogger(__name__)

class RAGEngine:
    def __init__(self):
        self.endee_client = EndeeClient()
        self.embedding_service = EmbeddingService()
        self.llm_client = GroqLLMClient()

    def _parse_filters(self, query):
        """Parse simple filters from the query.

        Supported syntax:
        - key:value (no spaces)
        """
        if not query:
            return "", {}

        tokens = str(query).split()
        filters = {}
        cleaned_tokens = []

        for t in tokens:
            if ":" in t and not t.startswith("http"):
                k, v = t.split(":", 1)
                k = k.strip()
                v = v.strip()
                if k and v:
                    filters[k] = v
                    continue
            cleaned_tokens.append(t)

        return " ".join(cleaned_tokens).strip(), filters

    def retrieve_relevant_rows(self, query, index_name="business_records", top_k=25):
        cleaned_query, filters = self._parse_filters(query)
        embed_query = cleaned_query or query

        query_vector = self.embedding_service.generate_embedding(embed_query).tolist()
        metadata_filter = filters or None
        results = self.endee_client.search_vectors(
            query_vector,
            name=index_name,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )

        # If server-side filtering is unsupported (or too strict), fall back to
        # vector-only retrieval and apply filters locally.
        if metadata_filter and not results:
            results = self.endee_client.search_vectors(
                query_vector,
                name=index_name,
                top_k=top_k,
            )
        
        logger.info(f"Retrieved {len(results)} results for query: {query}")
        
        formatted_results = []
        for item in results:
            formatted_results.append({
                'score': item.get('similarity', 0),
                'metadata': item.get('meta', {}).get('original_row', {}),
                'text': item.get('meta', {}).get('text', '')
            })

        if not filters:
            return formatted_results

        def _meta_matches(meta, k, v):
            if not meta:
                return False
            target_key = str(k).strip().lower()
            target_val = str(v).strip().lower()

            for mk, mv in meta.items():
                if str(mk).strip().lower() != target_key:
                    continue
                mv_str = str(mv).strip().lower()
                if mv_str == target_val:
                    return True
                if target_val in mv_str:
                    return True
            return False

        filtered = []
        for r in formatted_results:
            meta = r.get("metadata", {}) or {}
            ok = True
            for k, v in filters.items():
                if not _meta_matches(meta, k, v):
                    ok = False
                    break
            if ok:
                filtered.append(r)

        return filtered

    def _detect_intent(self, query):
        q = (query or "").lower()
        if any(w in q for w in ["top ", "highest", "most", "best", "rank"]):
            return "ranking"
        if any(w in q for w in ["trend", "over time", "month", "weekly", "daily", "quarter", "q1", "q2", "q3", "q4", "year"]):
            return "trend"
        if any(w in q for w in ["compare", "vs", "versus", "difference", "between"]):
            return "comparison"
        if any(w in q for w in ["why", "root cause", "reason", "driver"]):
            return "explanation"
        return "general"

    def _pick_field(self, metadata_rows, candidate_substrings):
        for meta in metadata_rows:
            for k in meta.keys():
                lk = str(k).lower()
                if any(sub in lk for sub in candidate_substrings):
                    return k
        return None

    def _pick_field_from_query(self, query, metadata_rows):
        q = (query or "").lower()

        if any(w in q for w in ["customer", "client", "account"]):
            return self._pick_field(metadata_rows, ["customer", "client", "account"])
        if any(w in q for w in ["product", "item", "sku", "service"]):
            return self._pick_field(metadata_rows, ["product", "item", "sku", "service"])
        if any(w in q for w in ["industry", "sector", "category"]):
            return self._pick_field(metadata_rows, ["industry", "sector", "category"])
        if any(w in q for w in ["region", "country", "state", "city", "geo"]):
            return self._pick_field(metadata_rows, ["region", "country", "state", "city"])

        return None

    def _coerce_float(self, v):
        try:
            if v is None:
                return None
            if isinstance(v, bool):
                return None
            s = str(v).strip().replace(",", "")
            if not s or s.lower() == "nan":
                return None
            return float(s)
        except Exception:
            return None

    def _aggregate(self, query, retrieved_rows):
        metadata_rows = [r.get('metadata', {}) for r in retrieved_rows]

        entity_field = self._pick_field_from_query(query, metadata_rows) or self._pick_field(
            metadata_rows,
            ["product", "item", "sku", "service", "client", "customer", "industry", "sector", "category", "region", "country", "state", "city"],
        )
        amount_field = self._pick_field(metadata_rows, ["amount", "total", "revenue", "sales", "value", "price", "cost"]) 
        quantity_field = self._pick_field(metadata_rows, ["qty", "quantity", "units", "volume"]) 

        entity_counts = {}
        entity_amounts = {}
        entity_quantities = {}
        numeric_sums = {}

        for row in retrieved_rows:
            meta = row.get('metadata', {}) or {}

            if entity_field:
                ent_val = str(meta.get(entity_field, "")).strip()
                if ent_val and ent_val.lower() != "nan":
                    entity_counts[ent_val] = entity_counts.get(ent_val, 0) + 1

            for k, v in meta.items():
                lk = str(k).lower()
                if any(w in lk for w in ["quantity", "qty", "units", "amount", "total", "price", "revenue", "sales", "value"]):
                    fv = self._coerce_float(v)
                    if fv is None:
                        continue
                    numeric_sums[k] = numeric_sums.get(k, 0.0) + fv

            if entity_field and amount_field:
                ent_val = str(meta.get(entity_field, "")).strip()
                amt_val = self._coerce_float(meta.get(amount_field))
                if ent_val and ent_val.lower() != "nan" and amt_val is not None:
                    entity_amounts[ent_val] = entity_amounts.get(ent_val, 0.0) + amt_val

            if entity_field and quantity_field:
                ent_val = str(meta.get(entity_field, "")).strip()
                qty_val = self._coerce_float(meta.get(quantity_field))
                if ent_val and ent_val.lower() != "nan" and qty_val is not None:
                    entity_quantities[ent_val] = entity_quantities.get(ent_val, 0.0) + qty_val

        top_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:8]
        top_entity_amounts = sorted(entity_amounts.items(), key=lambda x: x[1], reverse=True)[:8]
        top_entity_quantities = sorted(entity_quantities.items(), key=lambda x: x[1], reverse=True)[:8]

        return {
            "entity_field": entity_field,
            "amount_field": amount_field,
            "quantity_field": quantity_field,
            "top_entities": top_entities,
            "top_entity_amounts": top_entity_amounts,
            "top_entity_quantities": top_entity_quantities,
            "numeric_sums": numeric_sums,
        }

    def _build_context(self, query, retrieved_rows, intent, aggregates):
        trimmed = retrieved_rows[:8]
        records = []
        for i, r in enumerate(trimmed, start=1):
            meta = r.get("metadata", {}) or {}
            # Keep the prompt compact: a few key-value pairs + short text excerpt.
            compact_meta = {}
            for mk, mv in list(meta.items())[:12]:
                compact_meta[str(mk)] = str(mv)[:160]

            text = (r.get("text", "") or "").strip()
            if len(text) > 400:
                text = text[:400] + "..."

            records.append({
                "rank": i,
                "score": r.get("score", 0),
                "text": text,
                "metadata": compact_meta,
            })

        return {
            "query": query,
            "intent": intent,
            "retrieval": {
                "k": len(retrieved_rows),
                "sample_k": len(trimmed),
                "score_max": max([r.get("score", 0) for r in retrieved_rows], default=0),
                "score_min": min([r.get("score", 0) for r in retrieved_rows], default=0),
            },
            "aggregates": aggregates,
            "records": records,
        }

    def generate_insight(self, query, retrieved_rows):
        if not retrieved_rows:
            return "No relevant data found to generate insights. Try a different query."

        intent = self._detect_intent(query)
        aggregates = self._aggregate(query, retrieved_rows)
        context = self._build_context(query, retrieved_rows, intent, aggregates)

        def _deterministic_summary():
            insight = f"### AI Business Intelligence Report\n\n"
            insight += f"Analysis of **{len(retrieved_rows)}** records retrieved from Endee for the query: *\"{query}\"*\n\n"

            if aggregates.get("top_entities"):
                insight += "#### Top Entities (by frequency)\n"
                for name, count in aggregates["top_entities"][:5]:
                    insight += f"- **{name}** ({count})\n"
                insight += "\n"

            if aggregates.get("top_entity_amounts"):
                insight += "#### Top Entities (by amount)\n"
                for name, total in aggregates["top_entity_amounts"][:5]:
                    insight += f"- **{name}** ({total:,.2f})\n"
                insight += "\n"

            if aggregates.get("top_entity_quantities"):
                insight += "#### Top Entities (by quantity)\n"
                for name, total in aggregates["top_entity_quantities"][:5]:
                    insight += f"- **{name}** ({total:,.2f})\n"
                insight += "\n"

            numeric_sums = aggregates.get("numeric_sums") or {}
            if numeric_sums:
                insight += "#### Numeric Totals\n"
                for k, v in list(numeric_sums.items())[:8]:
                    insight += f"- Total **{k}**: {v:,.2f}\n"
                insight += "\n"

            representative_text = retrieved_rows[0].get('text', '')
            insight += "#### Contextual Summary\n"
            insight += f"Most relevant record: *{representative_text}*\n"
            return insight

        if not self.llm_client.is_configured():
            return _deterministic_summary()

        system = (
            "You are a senior business intelligence analyst. "
            "Answer the user's question using ONLY the provided retrieved records and computed aggregates. "
            "If the data is insufficient, say exactly what's missing and propose the smallest next query or filter to get it. "
            "Be concrete: reference fields and values seen in the records."
        )

        user = (
            "User question:\n"
            f"{query}\n\n"
            "Retrieved context (JSON):\n"
            f"{context}"
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        try:
            return self.llm_client.chat_completion(messages)
        except RuntimeError as e:
            # If Groq rejects due to size / TPM, return a deterministic fallback.
            err = str(e)
            if "Request too large" in err or "413" in err:
                return _deterministic_summary()
            raise
