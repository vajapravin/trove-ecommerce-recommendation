# Trove — Agentic E-Commerce Recommendation Platform

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white) ![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=chainlink&logoColor=white) ![LangGraph](https://img.shields.io/badge/LangGraph-333333?style=for-the-badge&logo=graphql&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white) ![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlite&logoColor=white) ![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6F61?style=for-the-badge&logo=databricks&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

**Live demo:** [trove-ecommerce-recommendation.vajapravin.me](https://trove-ecommerce-recommendation.vajapravin.me/)

</div>

A commerce-style platform whose backend watches how each shopper browses, understands their interests, and generates personalized, persuasive recommendations grounded in the real catalog via semantic retrieval. Built with Python, LangGraph, and FastAPI, this system uses a multi-node agent state machine to analyze behavioral signals, perform RAG-based retrieval against a Chroma vector store, and deliver LLM-ranked product picks — all without requiring a single explicit search from the user.

Built for the **SmartReco Build Challenge 2026**.

## 🏗 Architecture

The application uses a graph-based agent architecture (via LangGraph) to deliver deterministic, cost-aware recommendations:

1. **Behavioral Tracking (`tracker.js`)**: A non-blocking frontend queue that batches user events (views, clicks, scrolls, dwell time) and flushes on 10 events, 5-second timeout, or page unload via `sendBeacon` — zero dropped events.
2. **Trigger Policy (`policy.py`)**: Guards the agent graph behind a dual threshold: ≥ `RECO_MIN_NEW_EVENTS` new events *and* ≥ `RECO_MIN_INTERVAL_MINUTES` since the last run. SHA-256 activity fingerprinting skips LLM calls entirely on repeat visits.
3. **Activity Analyzer Node**: Summarizes raw behavioral events into structured signals (top categories, engagement depth, price affinities) and extracts a semantic search query.
4. **RAG Retrieval Node**: Queries the Chroma vector store with metadata filters (category, level) to produce a top-15 candidate shortlist from pre-computed product embeddings.
5. **Evaluation & Refinement Nodes**: Validates shortlist quality against relevance thresholds; if below threshold, broadens query parameters and re-retrieves.
6. **LLM Re-Rank Node**: Ranks the top-15 shortlist down to top-5 picks via the Mesh API, grounding selections in the user's behavioral context.
7. **Narrative Generation Node**: Produces a persuasive, personalized recommendation narrative with product picks anchored to real Chroma catalog IDs.

## ✨ Core Features

* **Dual-Write Consistency**: Every product write goes to SQLite *and* Chroma atomically, with rollback if Chroma fails — catalog and vector store are always in sync.
* **Semantic Search**: The `/catalog?q=...` route retrieves products through Chroma with metadata filtering by category and level, powered by OpenAI embeddings.
* **Zero-LLM "You Might Also Like"**: A semantic kNN strip on every product detail page that costs zero LLM tokens at runtime — Chroma does an in-memory vector search on pre-computed embeddings.
* **Fingerprint Caching**: The agent hashes ordered recent activity into a SHA-256 fingerprint; if it matches the last stored recommendation, the entire LLM pipeline is skipped for zero-cost repeat visits.
* **Scheduled Daily Digest**: APScheduler runs proactive background recommendations and logs to `digest_logs` with an admin view at `/admin/digests`.
* **Two-Stage Retrieval Re-Ranking**: Top-15 shortlist → LLM-ranked to top-5, keeping agent prompts small and token costs low.
* **LangSmith Observability**: Full span tree visibility across all agent graph nodes for debugging and performance monitoring.
* **Admin Health Dashboard**: `/admin/mesh-health` pings Mesh chat + embeddings and shows SQLite/Chroma sync status in real time.

## ⚔ Tech Stack

| Component | Technology |
|---|---|
| Framework | Python 3.12+, FastAPI |
| Templating | Jinja2 (server-rendered) |
| Agent Orchestration | LangGraph (StateGraph) |
| LLM Provider | Mesh API (OpenAI-compatible) — GPT-4o-mini |
| Embeddings | OpenAI `text-embedding-3-small` via Mesh |
| Database | SQLite (via SQLAlchemy) |
| Vector Store | ChromaDB |
| Auth | bcrypt + signed-cookie sessions |
| Scheduling | APScheduler |
| Observability | LangSmith tracing |
| Deployment | Docker Compose |

## 🛠 Quick Start

```bash
# Clone the repository
git clone https://github.com/vajapravin/trove-ecommerce-recommendation.git
cd trove-ecommerce-recommendation

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env — paste your MESH_API_KEY

# Run the application
python run.py
# Or:  uvicorn app.main:app --reload
```

The app will be available at `http://localhost:8000`.

### First-Run Bootstrap

On first boot the app creates the SQLite DB, seeds an admin account, and (if `SEED_CATALOG=true` and `MESH_API_KEY` is set) loads a starter catalog through the dual-write path — so both SQLite and Chroma are populated.

Default admin: **`admin@trove.local`** / **`admin123`** *(change in `.env`)*.

### Docker

```bash
docker compose up --build
```

## 📁 API Endpoints & Routes

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Landing page |
| `GET` | `/catalog` | Browsable product catalog with semantic search (`?q=...`) |
| `GET` | `/catalog/{id}` | Product detail + "You might also like" kNN strip |
| `GET` | `/recommendations` | Personalized AI recommendations for the logged-in user |
| `POST` | `/events` | Batched behavioral event ingest (non-blocking) |
| `POST` | `/auth/login` | Email/password authentication |
| `POST` | `/auth/register` | User registration |
| `GET` | `/admin/mesh-health` | Admin health dashboard (Mesh + sync status) |
| `GET` | `/admin/digests` | Admin view of scheduled digest logs |
| `GET` | `/admin/products` | Admin product CRUD management |
| `GET` | `/docs` | Interactive API documentation (Swagger) |

## 📂 Project Layout

```
trove/
├── app/
│   ├── main.py               # FastAPI app factory + startup
│   ├── config.py             # pydantic-settings, reads .env
│   ├── database.py           # SQLAlchemy engine + session
│   ├── models.py             # ORM models
│   ├── auth.py               # bcrypt + signed-cookie sessions
│   ├── deps.py               # Request-level dependencies
│   ├── mesh_client.py        # Mesh API (OpenAI-compatible) wrapper
│   ├── vector_store.py       # Chroma wrapper + kNN + ping helpers
│   ├── services/
│   │   ├── activity_summary.py # User event aggregation & fingerprinting
│   │   └── dual_write.py     # SQLite + Chroma coordinated writes
│   ├── routers/              # auth, pages, catalog, products (admin), events, recommendations
│   ├── agent/                # LangGraph state machine & trigger policy
│   │   ├── graph.py          # StateGraph compilation & LangSmith setup
│   │   ├── nodes.py          # analyze, decide, retrieve, evaluate, refine, rerank, generate
│   │   ├── policy.py         # Trigger threshold & fingerprint cache policy
│   │   ├── runner.py         # Recommendation agent execution & DB persistence
│   │   └── state.py          # AgentState schema
│   ├── scheduler/            # APScheduler background daily digest job
│   ├── templates/            # Jinja2 HTML templates
│   └── static/               # CSS + tracker.js
├── data/                     # SQLite persistence
├── chroma_db/                # Vector store persistence
├── .github/workflows/        # CI (SmartReco checks)
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── run.py
```

## Key Tables

| Table | Purpose |
|---|---|
| `users` | id, email, password_hash, role, created_at |
| `products` | id, title, description, category, level, price, image_url… |
| `events` | id, user_id, session_id, event_type, product_id, payload_json |
| `recommendations` | id, user_id, narrative, product_ids_json, fingerprint, source |
| `digest_logs` | id, user_id, recommendation_id, subject, body, created_at |

## 🗺 Roadmap

- [x] **Day 1** — Scaffold, auth, DB schema, tracking, dual-write, base templates (0.1.0)
- [x] **Day 2** — Full admin CRUD + edit page, catalog chips/filters, "you might also like", Mesh health dashboard, Trove rebrand (0.2.0)
- [x] **Day 3** — SCOPE.md documentation & activity summary service
- [x] **Day 4** — LangGraph agent + RAG retrieval + recommendation storage + trigger policy & fingerprint caching
- [x] **Day 5** — APScheduler daily digest + admin digest log view + LangSmith tracing
- [x] **Day 6** — Two-stage retrieval re-ranking, final verification & v1.0.0 release

## 📄 License

MIT — hackathon submission.
