# Trove — Agentic Course Recommendation Platform

An online-learning platform whose backend watches how each user browses, understands their interests, and generates personalized, persuasive recommendations grounded in the real catalog via semantic retrieval.

Built for the **Trove Build Challenge 2026**.

---

## What's built

- **FastAPI** web app with server-rendered Jinja2 templates
- **Email/password auth** with signed session cookies; two roles (`user`, `admin`)
- **Product catalog** with full admin CRUD
- **Dual-write** — every product write goes to SQLite *and* Chroma (vector DB) atomically
- **Non-blocking behavioral tracking** — batched, throttled frontend queue that survives page unload via `sendBeacon`
- **Agentic recommendation engine** built as a **LangGraph** state machine (analyze → decide-retrieve → retrieve → evaluate → refine → generate)
- **Smart triggering** — the agent only fires when the user has enough new activity *and* enough time has passed, with a fingerprint-based cache to skip redundant runs
- **Scheduled daily digest** via APScheduler (mock delivery — logged to a `DigestLog` table and viewable in the admin panel)
- **LangSmith tracing** wired through the whole agent workflow
- **Retrieval polish** — metadata filtering (category, price band, level) and LLM-based re-ranking

---

## Architecture

```
┌────────────────────┐        ┌─────────────────────────────────────────┐
│  Browser (Jinja2)  │        │              FastAPI backend            │
│                    │        │                                         │
│  tracker.js queue  │──POST──▶  /events (batched ingest, non-blocking) │
│  sendBeacon on     │        │                                         │
│  unload            │        │  Trigger check ──▶ Agent (LangGraph):   │
│                    │◀───────│    analyze → retrieve (Chroma) →        │
│  /recommendations  │        │    evaluate → refine → generate          │
└────────────────────┘        │                                         │
                              │  APScheduler ──▶ daily digest job       │
                              └──────┬──────────────────┬───────────────┘
                                     │                  │
                                     ▼                  ▼
                              ┌─────────────┐    ┌──────────────┐
                              │   SQLite    │    │   Chroma     │
                              │ (via SQLA)  │    │ (embeddings) │
                              └─────────────┘    └──────────────┘
                                     ▲                  ▲
                                     └────── dual-write ┘
                                          (products only)

  All LLM + embedding calls flow through the Mesh API (OpenAI-compatible).
```

### Key tables

| Table              | Purpose                                                       |
|--------------------|---------------------------------------------------------------|
| `users`            | id, email, password_hash, role, created_at                    |
| `products`         | id, title, description, category, level, price, image_url…    |
| `events`           | id, user_id, session_id, event_type, product_id, payload_json |
| `recommendations`  | id, user_id, narrative, product_ids_json, fingerprint, source |
| `digest_logs`      | id, user_id, recommendation_id, subject, body, created_at     |

### Efficiency choices

- **Frontend tracker** flushes on: 10 events queued, 5 seconds elapsed, or page hide/unload (`visibilitychange` + `sendBeacon`). High-frequency events (scroll, dwell ticks) are throttled to at most 1/sec per type.
- **Backend event ingest** returns `202 Accepted` immediately after a bulk insert — no blocking work happens on the request path.
- **Agent triggering** requires *both* ≥ `RECO_MIN_NEW_EVENTS` new events *and* ≥ `RECO_MIN_INTERVAL_MINUTES` since the last run for that user. The agent also hashes the ordered recent activity into a **fingerprint**; if it matches the last stored recommendation's fingerprint, the LLM is skipped entirely.
- **Retrieval re-rank** happens on a *shortlist* (top-15 → LLM-ranked to top-5) so we send small prompts.

---

## Setup

```bash
# 1. Create and activate a virtualenv
python3.11 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure secrets
cp .env.example .env
# Edit .env — paste your MESH_API_KEY, set MESH_BASE_URL from your Mesh dashboard

# 4. Run
python run.py
# Or:  uvicorn app.main:app --reload
```

Then open <http://localhost:8000>.

### First-run bootstrap

On first boot the app creates the SQLite DB, seeds an admin account, and (if you set `SEED_CATALOG=true`) loads a small starter catalog. Default admin:

- **Email:** `admin@trove.local`
- **Password:** `admin123`  *(change it in .env or after first login)*

---

## Project layout

```
trove/
├── app/
│   ├── main.py               # FastAPI app factory + startup
│   ├── config.py             # pydantic-settings, reads .env
│   ├── database.py           # SQLAlchemy engine + session
│   ├── models.py             # ORM models
│   ├── auth.py               # password hashing + session helpers
│   ├── deps.py               # request-level dependencies
│   ├── mesh_client.py        # Mesh API (OpenAI-compatible) wrapper
│   ├── vector_store.py       # Chroma wrapper
│   ├── services/
│   │   └── dual_write.py     # SQLite + Chroma coordinated writes
│   ├── routers/              # auth, pages, products, catalog, events, recommendations
│   ├── agent/                # LangGraph state machine  (Day 4)
│   ├── scheduler/            # APScheduler jobs         (Day 5)
│   ├── templates/            # Jinja2
│   └── static/               # CSS + tracker.js
├── data/                     # SQLite lives here
├── chroma_db/                # vector store persistence
├── .github/workflows/        # CI (Trove checks)
├── .env.example
├── .gitignore
├── requirements.txt
└── run.py
```

---

## Roadmap (build days)

- [x] **Day 1** — scaffold, auth, DB schema, base templates, CI green
- [ ] **Day 2** — product CRUD + dual-write to Chroma + catalog pages
- [ ] **Day 3** — event tracking (batched, non-blocking) + activity storage
- [ ] **Day 4** — LangGraph agent + RAG retrieval + recommendation storage
- [ ] **Day 5** — APScheduler daily digest + LangSmith tracing
- [ ] **Day 6** — retrieval re-ranking, seed data, polish, final README

---

## License

MIT — hackathon submission.
