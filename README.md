# 🚀 Multi Agents Systems - Agentic RFQ Intelligence Platform

An advanced **Multi-Agent AI System** designed to automate RFQ (Request for Quotation) analysis, engineering document validation, conflict detection, and intelligent document querying.

The platform combines **Agentic AI**, **RAG (Retrieval-Augmented Generation)**, **Vector Search**, and **Document Intelligence** to process complex engineering and procurement documents with minimal human intervention.

---

# ✨ Key Features

## 🤖 Multi-Agent Architecture

Specialized AI agents collaborate to solve complex engineering and procurement tasks.

* Query Analysis Agent
* Retrieval Agent
* Conflict Detection Agent
* Optimization Agent
* Response Generation Agent

---

## 📄 Multi-Format Document Processing

Supports:

* PDF Documents
* Excel BOQ Files
* Technical Specifications
* Engineering Drawings
* RFQ Documents

Handled through:

```text
document_upload.py
document_service.py
```

---

## 🔍 Intelligent RAG Search

The system uses embeddings and vector search for semantic retrieval.

### Features

* Dense Vector Search
* Context Retrieval
* Semantic Similarity Matching
* Source Referencing

Powered by:

```text
embedding_service.py
vector_service.py
chunk_service.py
```

---

## 🧠 Agentic Reasoning Pipeline

Instead of traditional RAG:

```text
Question
   ↓
Retrieve
   ↓
Answer
```

The system follows:

```text
Reason
   ↓
Act
   ↓
Observe
   ↓
Answer
```

Agents autonomously decide:

* Which documents to search
* Which retrieval strategy to use
* How to combine evidence
* How to generate responses

---

## ⚠️ Engineering Conflict Detection

Automatically detects:

* Quantity mismatches
* Specification conflicts
* Missing items
* BOQ inconsistencies
* Cross-document discrepancies

Implemented in:

```text
conflict_engine.py
```

---

## 📊 RFQ Intelligence Pipeline

The dedicated RFQ pipeline performs:

* Requirement Extraction
* Risk Analysis
* Quantity Validation
* Vendor Requirement Analysis
* Document Summarization

Implemented in:

```text
rfq_pipeline.py
```

---

## 📌 Source Citations & Confidence Score

Every generated response includes:

* Retrieved document references
* Source chunks
* Confidence indicators
* Supporting evidence

---

# 📂 Project Structure

```text
Multi Agents Systems
│
├── app
│
├── brain
│   ├── agent_service.py
│   ├── chunk_service.py
│   ├── conflict_engine.py
│   ├── document_service.py
│   ├── document_upload.py
│   ├── embedding_service.py
│   ├── llm_service.py
│   └── vector_service.py
│
├── extraction
│
├── models
│
├── pipeline
│   ├── agent_pipeline.py
│   ├── intelligence_service.py
│   ├── optimization_service.py
│   ├── query_pipeline.py
│   └── rfq_pipeline.py
│
├── routers
│   ├── agent_router.py
│   └── document_router.py
│
└── main.py
```

---

# 🧠 System Architecture

```text
User Query
    │
    ▼
Agent Router
    │
    ▼
Agent Pipeline
    │
    ▼
Intent Analysis Agent
    │
    ├──────────────┐
    ▼              ▼
Vector Search   RFQ Analysis
Agent           Agent
    │              │
    ▼              ▼
Document Context
    │
    ▼
Conflict Detection Agent
    │
    ▼
Optimization Agent
    │
    ▼
LLM Response Agent
    │
    ▼
Final Answer + Citations
```

---

# ⚙️ Technology Stack

## Backend

* FastAPI
* Python

## AI & LLM

* OpenAI GPT-4o
* OpenAI Embeddings

## Vector Search

* FAISS

## Document Processing

* PyPDF
* Pandas
* OpenPyXL

## Agent Framework

* Custom Multi-Agent Architecture

## Deployment

* Uvicorn
* Docker (Future)

---

# 🛠 Installation

## Clone Repository

```bash
git clone <repository-url>
cd "Multi Agents Systems"
```

## Create Virtual Environment

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux / Mac

```bash
python3 -m venv venv
source venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Configure Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_api_key
```

---

# 🚀 Run Application

```bash
uvicorn app.main:app --reload --port 8000
```

---

# 📘 API Documentation

### Swagger UI

```text
http://127.0.0.1:8000/docs
```

### ReDoc

```text
http://127.0.0.1:8000/redoc
```

---

# 💡 Example Queries

### Document Search

```text
Find all fire safety requirements mentioned in the uploaded RFQ documents.
```

### BOQ Analysis

```text
List all equipment and quantities from the BOQ.
```

### Conflict Detection

```text
Compare quantities mentioned in BOQ and specifications.
```

### Risk Assessment

```text
Identify procurement risks in this RFQ package.
```

### Engineering Validation

```text
Check for inconsistencies across all uploaded engineering documents.
```

---

# 🎯 Use Cases

* RFQ Analysis Automation
* Procurement Intelligence
* Engineering Document Validation
* Construction BOQ Verification
* Tender Risk Assessment
* Knowledge Base Search
* Enterprise Document Intelligence

---

# 📈 Future Enhancements

* LangGraph Integration
* Multi-Agent Memory
* Hybrid Search (BM25 + Vector Search)
* CAD Drawing Intelligence
* AWS Deployment
* Docker Support
* Multi-Modal AI Support
* Autonomous Agent Planning

---

# 👩‍💻 Author

**Jaya Rajput**
Full Stack Developer | AI/ML Engineer | Agentic AI Enthusiast

---

⭐ If you found this project useful, consider giving it a star and contributing to future enhancements.
"# Multi-Agents-Systems" 
