# SemanticBI — Endee-Powered Semantic Business Intelligence

SemanticBI is a Django web app that turns messy business spreadsheets into a **queryable semantic knowledge base** using **Endee** (vector database). You can upload Excel/CSV datasets, index each row as a vector, run semantic search, apply metadata filters, and generate analyst-style insights via a lightweight RAG pipeline.

---

## Problem Statement

Traditional BI tools assume:
- data is already modeled into clean tables
- analysts know which filters/columns to use
- questions can be answered with dashboards and fixed SQL

In real workflows (sales leads, procurement, orders, CRM exports, supplier catalogs), the data is:
- high-dimensional
- inconsistent column naming
- searched by “meaning” ("find buyers like X", "top products among these customers")

SemanticBI solves this by using **Endee vector search** as the retrieval layer and letting users ask questions in natural language.

---

## System Design (High Level)

### Data Flow

1. **Upload Dataset** (`/`)
2. **Parse + Clean** (pandas) and convert each row into a short semantic sentence
3. **Embed** text using `SentenceTransformer(all-MiniLM-L6-v2)` → 384-d vectors
4. **Store** vectors + metadata in Endee (one **unique index per dataset**)
5. **Query**
   - **Search page**: dense vector similarity retrieval
   - **Insights page**: retrieval + aggregations + optional Groq LLM generation
   - **Analytics page**: basic distributions computed from retrieved samples
6. **Multi-dataset management** via Dataset history and an “active dataset” stored in session

### Key Design Choices

- **One Endee index per upload**: avoids overwriting old data and enables dataset switching.
- **Metadata stored alongside each vector**: enables filter-aware retrieval and evidence display.
- **Compact RAG context**: prevents Groq “Request too large” errors.

---

## How Endee is Used (Core of the Project)

Endee is the authoritative retrieval and storage engine.

### What we store in Endee

Each dataset row becomes a vector document:

- **`id`**: `row_<row_index>`
- **`vector`**: 384-d embedding
- **`meta.text`**: the row converted into a natural-language sentence (used for human-readable evidence)
- **`meta.original_row`**: full row metadata as JSON-safe values (used for UI display and filtering)

### Index creation

On ingestion we ensure an index exists using:

- cosine similarity
- 384 dimensions
- `Precision.INT8`

### Querying + Filtering

Endee supports **payload (metadata) filtering** (MongoDB-style). This repo implements:

- **Endee-side filtering (best-effort)**: passes metadata filters into `index.query(...)` when supported by the installed SDK.
- **Local fallback filtering**: if SDK filter kwargs are not supported or the filter is too strict.

Filter syntax in the UI:

```text
top customers country:India city:Pune
```

This becomes a metadata filter object roughly like:

```python
{"country": "India", "city": "Pune"}
```

---

## Repository Walkthrough (Endee-Focused)

### `AIsearch/services/endee_client.py`

Endee SDK wrapper used everywhere else.

- **`ensure_index(name, dimension)`**
  - lists existing indexes
  - creates a new Endee index if missing

- **`upsert_vectors(vectors, name)`**
  - batches upserts (1000/vector batch)
  - calls `index.upsert([...])`

- **`search_vectors(query_vector, name, top_k, metadata_filter=None)`**
  - calls `index.query(vector=..., top_k=...)`
  - attempts to pass `metadata_filter` using common kwarg names (`filter`, `filters`, `payload_filter`, `where`)
  - falls back to vector-only query if filtering kwargs are unsupported

### `AIsearch/services/ingestion.py`

Responsible for turning files into Endee vectors.

- **`parse_file()`**
  - reads CSV or Excel
  - fills NaNs

- **`row_to_text(row)`**
  - converts a row into a sentence: `The <col> is <value>. ...`

- **`clean_metadata()`**
  - converts numpy types to JSON-safe Python primitives
  - prevents integer range errors

- **`process_dataset(file_path, original_filename)`**
  - generates a unique index name like `idx_<filename>_<timestamp>`
  - calls `EndeeClient.ensure_index(...)`
  - embeds all rows and upserts vectors into Endee

### `AIsearch/services/embeddings.py`

Embedding model used for both ingestion and querying:

- Loads `SentenceTransformer(all-MiniLM-L6-v2)` once (singleton)
- Produces 384-dimensional vectors

### `AIsearch/services/rag_engine.py`

RAG orchestration around Endee retrieval:

- **`retrieve_relevant_rows(query, index_name, top_k)`**
  - parses `key:value` filters
  - embeds the cleaned query
  - queries Endee with optional `metadata_filter`
  - falls back to vector-only + local filtering if needed
  - returns results as `{score, metadata, text}`

- **`generate_insight(query, retrieved_rows)`**
  - computes lightweight aggregations (top entities, totals)
  - builds a **compact** context window
  - calls Groq (optional) for natural-language analysis
  - gracefully falls back to a deterministic summary if Groq rejects the request (HTTP 413)

### `AIsearch/models.py`

`Dataset` model stores dataset history (name, file path, Endee index name, total rows). This is how the UI can switch which Endee index is “active”.

### `AIsearch/views.py`

The web endpoints:

- **Upload**: ingest file → create Endee index → upsert vectors
- **Search**: query active Endee index and display retrieved rows
- **Insights**: query Endee (top-k is intentionally smaller) → RAG generation
- **Analytics**: computes simple charts from sampled retrieval
- **History / Select**: switch active Endee dataset index in session

---

## Setup & Run (Local)

### 1) Start Endee

Endee must be running locally on port `8080`.

```bash
docker run -p 8080:8080 endeeai/endee:latest
```

### 2) Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3) Django migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4) Configure Groq for LLM Insights

SemanticBI works without Groq (deterministic insights) too. To enable LLM insights:

Linux / macOS:

```bash
export GROQ_API_KEY="YOUR_GROQ_KEY"
export GROQ_MODEL="meta-llama/llama-4-scout-17b-16e-instruct"
```

Windows (PowerShell):

```powershell
$env:GROQ_API_KEY="YOUR_GROQ_KEY"
$env:GROQ_MODEL="meta-llama/llama-4-scout-17b-16e-instruct"
```
<br>
PS: I know i shouldn't upload api keys on github but this one's usage is free so use this API KEY
<br>
GROQ_API_KEY="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"
<br>
otherwise just visit the groq website, login with an account and generate a new api key for free
<br>
Notes:
- The same Groq API key works across models, but rate/token limits vary by model.
- The Insights endpoint uses a compact context window (top-k + truncation) to avoid “Request too large” errors.

### 5) Run the server

```bash
python manage.py runserver 8001
```

Open:

- Upload: `http://127.0.0.1:8001/`
- Search: `http://127.0.0.1:8001/search/`
- Insights: `http://127.0.0.1:8001/insights/`
- Analytics: `http://127.0.0.1:8001/analytics/`
- Dataset history: `http://127.0.0.1:8001/history/`

---

## Demo Queries

Search:

- `indiamart buyers in pune`
- `suppliers for stainless fasteners`

Insights:

- `top 3 most bought products across all buyers`
- `top customers country:India`
- `high value orders city:Pune`

---

## Running on Another Laptop

1. Clone the repo.
2. Start Endee (Docker).
3. `pip install -r requirements.txt`
4. `python manage.py migrate`
5. Run Django and upload a dataset.

## Future Use Case — Personalized Advertising & Audience Targeting

One powerful extension of **SemanticBI** is using the retrieved insights to drive **data-driven marketing and personalized advertising campaigns**.

Since every dataset row is converted into a **semantic embedding** and stored with **rich metadata**, the system can identify customer segments with similar purchasing behavior, locations, and product interests. These insights can then be used to create **targeted marketing campaigns for different customer groups**.

---

### Customer Segmentation via Semantic Search

SemanticBI allows businesses to retrieve customers with similar behavior using natural language queries.

Example queries:

```
high value buyers country:India
repeat buyers city:Pune
customers buying stainless steel fasteners
```

This allows businesses to identify **micro-segments** such as:

- Industrial buyers in Pune
- High-volume procurement teams
- Customers frequently purchasing a specific product category
- Buyers from a particular region or city

Unlike traditional BI systems, segmentation does not require predefined SQL filters. Users can simply search by **meaning and intent**.

---

### Insight-Driven Audience Generation

The **Insights Engine** already extracts useful information such as:

- Top customers
- Most purchased products
- Geographic purchase patterns
- High-value transactions
- Product demand clusters

These insights can be used to automatically generate **marketing audience segments**.

Example segmentation table:

| Segment | Criteria | Marketing Use |
|--------|--------|--------|
| High Value Buyers | Large order values | Premium product campaigns |
| City-Based Customers | city:Pune | Location-based promotions |
| Product Interest | Buyers of stainless fasteners | Cross-selling related products |
| Frequent Buyers | Multiple orders | Loyalty offers |

These segments can be exported as **CSV audience lists** for marketing platforms.

---

### Bulk Ad Personalization

SemanticBI can also support **bulk ad generation** for different customer segments.

**Example**

**Segment:** Industrial Buyers in Pune

Example Ad Copy:

> High-quality stainless steel fasteners now available with fast delivery in Pune.  
> Trusted by local manufacturers and suppliers.

**Segment:** High Value Procurement Teams

Example Ad Copy:

> Exclusive bulk pricing on industrial hardware for high-volume buyers.  
> Optimized for large-scale procurement operations.

This allows companies to create **multiple personalized ad campaigns at scale** using insights generated from the dataset.

---

### Integration with Advertising Platforms

Future versions of SemanticBI could integrate with marketing platforms such as:

- Google Ads
- Meta Ads (Facebook / Instagram)
- LinkedIn Ads (for B2B datasets)

SemanticBI could generate **structured campaign data**, for example:

```
Campaign
 ├── Audience Segment
 ├── Recommended Product
 ├── Target Location
 └── Generated Ad Copy
```

This would allow businesses to quickly deploy **data-driven marketing campaigns** based on real purchase behavior.

---

### Why Semantic BI is Powerful for Marketing

Traditional marketing segmentation requires **manual SQL queries, dashboards, or rigid filters**.

SemanticBI enables users to ask questions like:

```
customers similar to top buyers in delhi
buyers interested in industrial fasteners
high value customers from maharashtra
```

The **vector similarity search** retrieves customers with **similar behavioral patterns**, enabling smarter targeting and more effective marketing campaigns.

---

### Potential Future Enhancements

Some possible future improvements include:

- Automated **customer clustering using embeddings**
- **Lookalike audience generation**
- LLM-generated **ad copy variations**
- Direct **campaign export to ad platforms**
- **Customer lifetime value prediction**
- AI-driven **product recommendation systems**

---

### Business Impact

By using semantic insights to drive marketing decisions, businesses could:

- Increase **conversion rates through personalized advertising**
- Reduce **wasted marketing spend**
- Discover **hidden customer segments**
- Identify **high-demand products**
- Build more effective **data-driven campaigns**

In the long term, **SemanticBI can evolve from a semantic analytics tool into a decision engine that powers intelligent marketing automation.**
