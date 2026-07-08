# Procurement & Vendor Query Analyzer (The Smart Tender Bot)

An advanced, locally hosted comparative Retrieval-Augmented Generation (RAG) framework engineered to automate technical compliance auditing for public sector procurement pipelines (specifically optimized for ONGC Tender specifications and Vendor Proposals).

---

## 🚀 Core Features & Architectural Depth

### 1. Ingestion Layer & Metadata Isolation
* **Cross-Contamination Prevention:** Employs explicit `doc_type` metadata tags ("tender" vs. "proposal") during ingestion to enforce a strict logical partition within a unified ChromaDB collection, completely eliminating background data leakage.
* **Parent-Child Chunking Strategy:** Text is shredded into granular **250-character Child Chunks** to optimize semantic database search precision, while dynamically mapping each child back to a **1,200-character Parent Chunk** (the enclosing paragraph). This ensures the local LLM always receives full legal and technical context (preserving critical negative qualifiers like *"we do NOT hold this certification"*).

### 2. Hybrid Search Engine & Rank Fusion (RRF)
* **The Alphanumeric Blur Problem:** Standard vector embeddings frequently blur closely related alphanumeric engineering grades (e.g., treating `API 5L X65` and `API 5L X70` as identical semantic concepts).
* **The Solution:** Runs a dense vector retrieval track (ChromaDB using `nomic-embed-text`) in parallel with a sparse lexical retrieval track (BM25Okapi). 
* **Mathematical Fusion:** Merges both independent ranked arrays using the **Reciprocal Rank Fusion (RRF)** algorithm:
  $$RRF\_Score(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
  *(Configured with a standard constant penalty factor of $k = 60$)*.

### 3. Automated Comparative Auditing
* Automatically extracts technical mandates from chunks tagged as `doc_type: "tender"`.
* Programmatically executes targeted hybrid queries against the `doc_type: "proposal"` pool to isolate matching clauses.
* Instructs a local LLM to run a side-by-side gap analysis, classifying compliance into four rigid, standardized tags: `COMPLIANT`, `DEVIATION`, `PARTIAL`, or `MISSING`.

### 4. Asynchronous Observability Loop (LLM-as-a-Judge)
* Features a real-time production monitoring layer. When a user flags a bad response (Thumbs Down 👎), an **asynchronous background daemon thread** catches the payload without blocking primary user interactions.
* Routes the query, context, and failed response to a secondary local LLM instance acting as a "Judge" to classify errors (e.g., *Retrieval Failure* or *Faithfulness Hallucination*) and updates a local SQLite diagnostics log.

---

## 💻 Tech Stack
* **Backend Framework:** Python, FastAPI
* **Vector Database:** ChromaDB (Embedding Model: `nomic-embed-text`)
* **Lexical Search:** BM25Okapi
* **Local LLM Runtime:** Ollama (`qwen2.5:7b`, `llama3.2`)
* **Database Logs:** SQLite
* **Frontend Dashboard:** React, Vite, Custom CSS (Glassmorphism UI)

---

## 🏃‍♂️ Getting Started (Local Deployment)

### Prerequisites
Ensure you have **Ollama** installed locally and the required models pulled:
```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text