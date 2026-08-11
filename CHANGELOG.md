# Changelog

All notable changes to Trove are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/) · Versioning: [SemVer](https://semver.org/)

## [Unreleased]

### Added

- `app/services/activity_summary.py`: user activity aggregation service (`summarize_user_activity`) returning structured `UserActivitySummary` with search queries, product interaction vectors, dwell metrics, and SHA256 event activity fingerprint.
- `app/agent/`: LangGraph recommendation engine workflow (`analyze_activity` → `decide_retrieve` → `retrieve` → `evaluate` → `refine` → `generate`) with grounded product picks and persistence to `recommendations` table.
- `POST /recommendations/refresh`: manual recommendation trigger route and UI button.



## [0.3.0] - 2026-08-03

### Added

- `SCOPE.md`: formal project scope document (problem, acceptance criteria, out-of-scope, risks, Definition of Done)

## [0.2.0] - 2026-08-03

### Added

- Admin edit page for products with live image URL preview (`/admin/products/{id}/edit`)
- Category chips + level filter on the catalog page; filters preserve the active query
- "You might also like" semantic strip on every product detail page (Chroma kNN, zero LLM cost at runtime)
- `/admin/mesh-health` dashboard: pings Mesh chat + embed round-trip, shows base URL, reports SQLite vs Chroma product counts, flags sync drift
- Smarter catalog empty states — distinct copy for "no matches for X" vs "nothing matches filters" vs "catalog empty"
- Related-products helper in `vector_store` (`related_products(product_id)`) using the source doc's pre-computed embedding

### Changed

- Rebranded SmartReco → Trove throughout: page titles, brand link, FastAPI app title, logger name (`trove`), session cookie (`trove_session`), DB filename (`trove.db`), admin email (`admin@trove.local`), tracker sessionStorage key, JS namespace (`window.Trove`), itsdangerous serializer salt
- Bumped app version to 0.2.0
- Default `MESH_BASE_URL` corrected to `https://api.meshapi.ai/v1` in both `.env.example` and the code-level fallback in `config.py`
- Admin products router mounted at `/admin` (was `/admin/products`) to host multiple admin views (products, mesh-health) under one prefix

## [0.1.0] - 2026-08-03

### Added

- FastAPI backend with server-rendered Jinja2 templates and app factory (`create_app`) + lifespan-managed startup bootstrap
- SQLAlchemy 2.0 ORM models: `User`, `Product`, `Event`, `Recommendation`, `DigestLog` — with `(user_id, created_at DESC)` composite indexes on events and recommendations for agent read paths
- Email/password authentication using **bcrypt directly** (passlib deliberately avoided to sidestep the passlib + bcrypt 4.1+ incompatibility) with signed-cookie sessions via `itsdangerous`
- Role-based route guards: `current_user` / `require_user` / `require_admin` FastAPI dependencies
- Admin CRUD for products (create/delete on Day 1; edit UI arrives in 0.2.0)
- **Dual-write** service: every product mutation goes to SQLite *and* Chroma atomically, with SQL rollback if the Chroma projection fails
- Mesh API client (`app/mesh_client.py`) wrapping the OpenAI SDK against `api.meshapi.ai/v1` — helpers `chat_complete`, `embed`, `embed_one`
- Chroma persistent vector store with a `MeshEmbeddingFunction` so index and query embeddings always use the same model
- Non-blocking behavioral tracker (`app/static/js/tracker.js`) — batches events, throttles high-frequency types (dwell, scroll) to 1/sec, flushes on `visibilitychange` / `pagehide` via `navigator.sendBeacon`
- `/events/ingest` endpoint accepting JSON *or* `text/plain` (for `sendBeacon`), bulk-inserting with `Session.bulk_save_objects`, returning `202 Accepted`
- Starter catalog seed (8 courses across AI/backend/data/devops/interview prep) written through the dual-write path so both stores are populated
- Base templates: login, register, home, catalog, product detail, recommendations, admin products
- CI workflow at `.github/workflows/smartreco-checks.yml` — GitHub OIDC + submission token, checks that code compiles and dependencies include a web framework and LLM client

### Security

- `.env` gitignored; `.env.example` ships only placeholders
- Bcrypt password hashes with per-user salts; session tokens are timestamped and expire after 7 days
- Route-level admin guard on all `/admin/*` endpoints
