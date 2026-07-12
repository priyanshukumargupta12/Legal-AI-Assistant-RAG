# Enterprise AI Legal Assistant — Hybrid RAG System

> **Interview-quality, production-ready AI system for US Tax & Legal document Q&A using Hybrid Retrieval-Augmented Generation (Hybrid RAG)**

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6?logo=typescript)](https://typescriptlang.org)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-red)](https://qdrant.tech)
[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-8.x-yellow?logo=elasticsearch)](https://elastic.co)
[![Gemini](https://img.shields.io/badge/Google_Gemini-1.5_Flash-blue?logo=google)](https://ai.google.dev)

---

## Project Overview

The **Enterprise AI Legal Assistant** allows legal professionals to:

- Upload and search **~100 US legal PDF documents** across 4 categories:
  - Acts & Statutes
  - Court Judgments
  - Tax Documents
  - Legal Opinions
- Ask **natural language legal questions** and receive **grounded answers** with page-level citations
- **Never hallucinates** — if information is unavailable, returns: *"Information not found in the provided legal documents."*
- Evaluate system quality using a **Golden Set** with 6 RAG metrics

---

## Architecture

```
Frontend (React + MUI)
        │
        │ HTTP REST
        ▼
FastAPI Backend (/api/v1)
        │
        ├── DocumentIngestionService
        │      PyMuPDF → Chunker → BGE Embedder
        │      → Qdrant (vectors) + Elasticsearch (BM25)
        │
        └── QueryService
               BGE Embedder (query)
               → Qdrant (top-10) ┐
               → Elasticsearch  ┘ → RRF Merger → Top-5
               → Google Gemini → Structured Answer + Citations
```

**Clean Architecture layers** (innermost → outermost):
```
Domain (entities + interfaces)
    → Application (services + use cases)
        → Infrastructure (Qdrant, ES, Gemini, PyMuPDF)
            → Presentation (FastAPI routers)
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend API | FastAPI 0.111 | Async REST API, OpenAPI docs |
| ASGI Server | Uvicorn | Production ASGI server |
| Embeddings | BAAI/bge-small-en-v1.5 | 384-dim dense vectors (CPU) |
| Vector DB | Qdrant | ANN cosine similarity search |
| Keyword Search | Elasticsearch 8 | BM25 keyword retrieval |
| LLM (default) | Google Gemini 1.5 Flash | Grounded answer generation |
| LLM (optional) | OpenAI GPT-4o-mini | Alternative LLM provider |
| PDF Parsing | PyMuPDF (fitz) | Fast page-attributed text extraction |
| Data Processing | Pandas + OpenPyXL | CSV/Excel generation |
| Logging | Loguru | Structured rotating file logs |
| Config | Pydantic Settings | Typed .env loading |
| Frontend | React 18 + TypeScript | Professional SPA dashboard |
| UI Components | Material UI 5 | Enterprise-grade UI components |
| HTTP Client | Axios | API calls with interceptors |
| State/Cache | React Query 5 | Server state management |
| Routing | React Router 6 | Client-side routing |

---

## Project Structure

```
Legal-AI-Assistant-RAG/
├── backend/                    # Python FastAPI backend (Clean Architecture)
│   ├── main.py                 # FastAPI app factory + lifespan
│   ├── requirements.txt        # All Python dependencies (pinned)
│   ├── .env.example            # Environment variable template
│   └── app/
│       ├── api/v1/             # FastAPI routers (thin layer)
│       ├── controllers/        # HTTP-to-service translation
│       ├── services/           # Business logic / use cases
│       ├── repositories/       # Abstract data access interfaces
│       ├── core/
│       │   ├── config/         # Pydantic BaseSettings
│       │   ├── database/       # DB client factories
│       │   ├── exceptions.py   # Domain exception hierarchy
│       │   └── constants.py    # All app-wide constants
│       ├── models/             # Domain entity dataclasses
│       ├── schemas/            # Pydantic API schemas
│       ├── middlewares/        # CORS, logging, rate limiting
│       ├── utils/              # File utils, prompts, security
│       ├── logging/            # Loguru configuration
│       ├── pdf_parser/         # PyMuPDF PDF text extractor
│       ├── chunking/           # Recursive text splitter
│       ├── embeddings/         # BGE embedding model wrapper
│       ├── vectorstore/        # Qdrant repository implementation
│       ├── elasticsearch/      # ES BM25 repository implementation
│       ├── retrieval/          # Hybrid retriever + RRF ranker
│       ├── llm/                # Gemini + OpenAI providers
│       ├── dataset/            # Dataset scanner
│       ├── evaluation/         # Golden set + metrics calculator
│       └── history/            # Search history persistence
│
├── frontend/                   # React + TypeScript + MUI
│   ├── src/
│   │   ├── pages/              # DashboardPage, QueryPage, etc.
│   │   ├── components/         # Reusable MUI components
│   │   ├── layouts/            # MainLayout with sidebar
│   │   ├── services/           # Axios API service functions
│   │   ├── types/              # TypeScript interfaces
│   │   ├── hooks/              # Custom React hooks
│   │   ├── store/              # React Context state
│   │   ├── theme/              # MUI custom dark theme
│   │   └── utils/              # Helper functions
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── dataset/                    # Place PDF files here
│   ├── Acts/
│   ├── CourtJudgement/
│   ├── Tax/
│   └── Legal_opinion/
│
├── metadata/                   # Auto-generated dataset reports
│   ├── documents.csv           # Generated by DatasetService
│   ├── documents.xlsx          # Generated by DatasetService
│   └── golden_set.csv          # Manually populated by user
│
├── logs/                       # Rotating log files
│   ├── app/, api/, dataset/
│   ├── embedding/, retrieval/, evaluation/
│
├── embeddings/cache/           # Cached HuggingFace model files
├── vectordb/qdrant/            # Qdrant persistent storage
├── scripts/                    # Windows batch setup/start scripts
└── docs/                       # Architecture documentation
```

---

## Installation & Setup

### Prerequisites

| Requirement | Version | Download |
|------------|---------|----------|
| Python | 3.12+ | [python.org](https://python.org) |
| Node.js | 20+ | [nodejs.org](https://nodejs.org) |
| Qdrant | Latest | [qdrant.tech/download](https://qdrant.tech/documentation/guides/installation/) |
| Elasticsearch | 8.x | [elastic.co](https://www.elastic.co/downloads/elasticsearch) |
| Gemini API Key | — | [makersuite.google.com](https://makersuite.google.com/app/apikey) |

---

### Step 1 — Clone Repository

```bash
git clone https://github.com/your-org/Legal-AI-Assistant-RAG.git
cd Legal-AI-Assistant-RAG
```

---

### Step 2 — Backend Setup

```bash
# Option A: Use the setup script (Windows)
scripts\setup_backend.bat

# Option B: Manual setup
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

---

### Step 3 — Configure Environment

```bash
# Copy template
cp backend/.env.example backend/.env

# Edit backend/.env — fill in required values:
# GEMINI_API_KEY=<your_key>
# QDRANT_URL=http://localhost:6333
# ELASTICSEARCH_URL=http://localhost:9200
```

---

### Step 4 — Frontend Setup

```bash
# Option A: Use the setup script (Windows)
scripts\setup_frontend.bat

# Option B: Manual setup
cd frontend
npm install
```

---

### Step 5 — Add Dataset

Place your PDF files in the correct category folders:
```
dataset/Acts/           ← US Acts and Statutes PDFs
dataset/CourtJudgement/ ← Court Judgment PDFs
dataset/Tax/            ← Tax Document PDFs
dataset/Legal_opinion/  ← Legal Opinion PDFs
```

---

### Step 6 — Start External Services

```bash
# Start Qdrant (local server mode)
qdrant\qdrant.exe

# Start Elasticsearch
elasticsearch-8.x\bin\elasticsearch.bat
```

---

## Running the Project

### Start Backend

```bash
# Option A: Script
scripts\start_backend.bat

# Option B: Manual
cd backend
venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Backend URLs:**
- API: `http://localhost:8000`
- Swagger Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

### Start Frontend

```bash
# Option A: Script
scripts\start_frontend.bat

# Option B: Manual
cd frontend
npm run dev
```

**Frontend URL:** `http://localhost:5173`

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health check |
| `POST` | `/api/v1/documents/ingest` | Upload and ingest a PDF |
| `POST` | `/api/v1/documents/ingest-all` | Bulk ingest all dataset PDFs |
| `GET` | `/api/v1/documents` | List all indexed documents |
| `POST` | `/api/v1/query` | Ask a legal question (Hybrid RAG) |
| `GET` | `/api/v1/query/history` | Search history |
| `GET` | `/api/v1/dataset/scan` | Scan dataset directory |
| `GET` | `/api/v1/dataset/export` | Download documents.csv / .xlsx |
| `POST` | `/api/v1/evaluation/import` | Upload golden set |
| `GET` | `/api/v1/evaluation/run` | Run evaluation + get metrics |

---

## Retrieval Pipeline

```
User Question
    │
    ├── Input Sanitization (prompt injection guard)
    │
    ├── BGE Query Embedding → 384-dim vector
    │
    ├── [Parallel]
    │   ├── Qdrant Search → Top-10 vector results (cosine)
    │   └── Elasticsearch → Top-10 BM25 keyword results
    │
    ├── RRF Merger → Top-5 unique chunks
    │        RRF(d) = Σ 1/(60 + rank_i)
    │
    ├── Prompt Assembly → System + Context[1-5] + Question
    │
    ├── Google Gemini API
    │
    └── Structured Response:
            answer, summary, citations[], confidence_score
```

---

## Evaluation Metrics

| Metric | What it Measures |
|--------|-----------------|
| **Precision@K** | Fraction of retrieved chunks that are relevant |
| **Recall@K** | Fraction of relevant chunks that were retrieved |
| **Faithfulness** | Answer contains only facts from retrieved context |
| **Context Precision** | Retrieved context relevance to the question |
| **Context Recall** | Expected answer coverage by retrieved context |
| **Answer Relevancy** | Semantic similarity of generated vs expected answer |

---

## Development Roadmap

| Milestone | Status | Description |
|-----------|--------|-------------|
| M1 | ✅ **Complete** | Project scaffold, config, logging, exceptions |
| M2 | ⏳ Pending | Domain entities + abstract interfaces |
| M3 | ⏳ Pending | PDF parser (PyMuPDF) + text chunker |
| M4 | ⏳ Pending | BGE embedding model |
| M5 | ⏳ Pending | Qdrant vector store |
| M6 | ⏳ Pending | Elasticsearch BM25 |
| M7 | ⏳ Pending | Gemini + OpenAI LLM providers |
| M8 | ⏳ Pending | Hybrid retrieval + RRF |
| M9 | ⏳ Pending | Application services |
| M10 | ⏳ Pending | FastAPI routers + middleware |
| M11 | ⏳ Pending | Frontend core (MUI theme + routing) |
| M12 | ⏳ Pending | All frontend pages |
| M13 | ⏳ Pending | Dataset scanner + CSV/Excel export |
| M14 | ⏳ Pending | Golden set evaluation |
| M15 | ⏳ Pending | Security hardening |
| M16 | ⏳ Pending | Final documentation + scripts |

---

## Coding Standards

**Backend (Python)**
- PEP 8 compliant with type hints throughout
- Pydantic v2 for all schemas and config
- Loguru for structured logging (6 named loggers)
- Domain exceptions for every error category
- No business logic in routers or controllers

**Frontend (TypeScript)**
- Strict TypeScript (`strict: true` in tsconfig)
- No `any` types
- Component-level JSDoc comments
- Axios interceptors for error handling
- React Query for server state

---

## Environment Variables Reference

See [`backend/.env.example`](backend/.env.example) for the complete reference with inline documentation.

Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | **Yes** | Google Gemini API key |
| `QDRANT_URL` | Yes | Qdrant server URL |
| `ELASTICSEARCH_URL` | Yes | Elasticsearch URL |
| `LLM_PROVIDER` | No | `gemini` (default) or `openai` |
| `LOG_LEVEL` | No | `INFO` (default) |

---

## License

This project is intended for demonstration and interview purposes.

---

*Built with ❤️ — Enterprise AI Legal Assistant | Hybrid RAG | Clean Architecture*
