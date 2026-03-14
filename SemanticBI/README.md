# SemanticBI — AI Business Intelligence Engine

SemanticBI is a professional-grade AI intelligence dashboard powered by **Endee**. It allows you to upload Excel/CSV datasets and perform semantic discovery, dynamic AI insights, and market analytics using vector search technology.

---

## 🚀 Quick Start (Local Setup)

### 1. Initialize Endee Vector Database
Endee must be running locally to handle vector operations.

```bash
# Pull and run Endee using Docker
docker run -p 8080:8080 endeeai/endee:latest
```

### 2. Django Project Setup
Ensure you have Python 3.8+ installed.

```bash
# Install dependencies
pip install django pandas openpyxl sentence-transformers requests scikit-learn numpy torch endee

# Navigate to the project directory
cd SemanticBI

# Initialize database
python manage.py makemigrations
python manage.py migrate

# Start the development server
python manage.py runserver 8001
```

Access the dashboard at: `http://127.0.0.1:8001`

---

## 🛠️ Core Features

### 1. Data Ingestion
- Upload **Excel (.xlsx, .xls)** or **CSV** files.
- The system automatically cleans data, handles missing values (NaN), and generates 384-dimensional semantic embeddings.
- Each dataset is stored in a **unique index** on Endee, allowing for multi-dataset history management.

### 2. Semantic Discovery
- Search your data using **Natural Language**.
- Unlike traditional keyword search, SemanticBI finds records based on *meaning* and *context*.
- Matches are ranked by similarity confidence.

### 3. AI Business Analyst (RAG)
- Ask complex business questions about your data.
- The engine uses **Retrieval-Augmented Generation (RAG)** to pull relevant context from Endee and generate dynamic, data-driven insights.

### 4. Market Intelligence Analytics
- Visualize your data patterns through interactive charts.
- View sector distributions and semantic cluster densities calculated directly from your live vector database.

---

## 📁 Project Structure
- `AIsearch/services/`: Core logic for Endee client, embeddings, and RAG engine.
- `AIsearch/templates/`: Modern, responsive UI built with TailwindCSS and Framer Motion.
- `media/`: Temporary storage for uploaded datasets.

---

## 💻 Running on another laptop
1. Copy the entire project folder.
2. Install Docker and run the Endee container (Step 1).
3. Install Python requirements (Step 2).
4. Run `python manage.py migrate` to set up the local SQLite database.
5. Run the server and start uploading!
