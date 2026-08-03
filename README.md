# Trove — Agentic Recommendation Platform

*Every catalog has treasure. We find yours.*

A commerce-style platform whose backend watches how each shopper browses, understands their interests, and generates personalized, persuasive recommendations grounded in the real catalog via semantic retrieval.

Built for the **SmartReco Build Challenge 2026**.

---

## What's built

- **FastAPI** web app with server-rendered Jinja2 templates
- **Email/password auth** with signed session cookies; two roles (`user`, `admin`)
- **Product catalog** with full admin CRUD (create, edit, delete)
- **Dual-write** — every product write goes to SQLite *and* Chroma (vector DB) atomically, with rollback if Chroma fails
- **Semantic search** — the `/catalog?q=...` route retrieves through Chroma with metadata filtering by category and level
- **"You might also like"** — a zero-LLM semantic kNN strip on every product detail page
- **Non-blocking behavioral tracking** — batched, throttled frontend queue that survives page unload via `sendBeacon`
- **Admin health dashboard** at `/admin/mesh-health` — pings Mesh chat + embeddings and shows SQLite/Chroma sync status
- **Agentic recommendation engine** (Day 4) built as a **LangGraph** state machine
- **Scheduled daily digest** (Day 5) via APScheduler with mock delivery to a `DigestLog` table
- **LangSmith tracing** wired through the whole agent workflow (Day 5)
- **Retrieval polish** — metadata filtering by category / level (Day 6 adds LLM re-ranking)

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
│  /recommendations  │        │    evaluate → refine → generate         │
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
- **Backend event ingest** does a bulk insert and returns immediately — no blocking work happens on the request path.
- **Agent triggering** requires *both* ≥ `RECO_MIN_NEW_EVENTS` new events *and* ≥ `RECO_MIN_INTERVAL_MINUTES` since the last run for that user. The agent also hashes the ordered recent activity into a **fingerprint**; if it matches the last stored recommendation's fingerprint, the LLM is skipped entirely.
- **"You might also like"** costs zero LLM tokens at runtime — Chroma retrieves the pre-computed embedding for the source product and does an in-memory vector search.
- **Retrieval re-rank** happens on a *shortlist* (top-15 → LLM-ranked to top-5) so agent prompts stay small.

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
# Edit .env — paste your MESH_API_KEY

# 4. Run
python run.py
# Or:  uvicorn app.main:app --reload
```

Then open <http://localhost:8000>.

### First-run bootstrap

On first boot the app creates the SQLite DB, seeds an admin account, and (if `SEED_CATALOG=true` and `MESH_API_KEY` is set) loads a small starter catalog through the dual-write path — so both SQLite and Chroma are populated.

Default admin: **`admin@trove.local`** / **`admin123`** *(change in `.env`)*.

### Verify things are wired

Log in as admin and visit **`/admin/mesh-health`** — you'll see:
- Chat and embed pings (green = Mesh is reachable and your key/models are valid)
- SQLite product count vs. Chroma vector count (equal = dual-write is in sync)

If chat/embed show red, the model IDs in `.env` don't match Mesh's catalog. Get the correct IDs from your Mesh dashboard.

---

## Project layout

```
trove/
├── app/
│   ├── main.py               # FastAPI app factory + startup
│   ├── config.py             # pydantic-settings, reads .env
│   ├── database.py           # SQLAlchemy engine + session
│   ├── models.py             # ORM models
│   ├── auth.py               # bcrypt + signed-cookie sessions
│   ├── deps.py               # request-level dependencies
│   ├── mesh_client.py        # Mesh API (OpenAI-compatible) wrapper
│   ├── vector_store.py       # Chroma wrapper + kNN + ping helpers
│   ├── services/
│   │   └── dual_write.py     # SQLite + Chroma coordinated writes
│   ├── routers/              # auth, pages, catalog, products (admin), events, recommendations
│   ├── agent/                # LangGraph state machine  (Day 4)
│   ├── scheduler/            # APScheduler jobs         (Day 5)
│   ├── templates/            # Jinja2
│   └── static/               # CSS + tracker.js
├── data/                     # SQLite lives here
├── chroma_db/                # vector store persistence
├── .github/workflows/        # CI (SmartReco checks)
├── .env.example
├── .gitignore
├── requirements.txt
└── run.py
```

---

## Roadmap (build days)

- [x] **Day 1** — scaffold, auth, DB schema, tracking, dual-write, base templates
- [x] **Day 2** — full admin CRUD + edit page, catalog chips/filters, "you might also like", Mesh health dashboard, Trove rebrand
- [ ] **Day 3** — beyond-baseline tracking: dwell heatmap, referrer capture, activity dashboard
- [ ] **Day 4** — LangGraph agent + RAG retrieval + recommendation storage + trigger logic
- [ ] **Day 5** — APScheduler daily digest + LangSmith tracing
- [ ] **Day 6** — retrieval re-ranking, polish, final README, demo video

---

## License

MIT — hackathon submission.
