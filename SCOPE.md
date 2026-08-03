# Trove — Project Scope

> *Every catalog has treasure. We find yours.*

This document defines what Trove is, what it delivers, and — just as importantly — what it deliberately does **not** cover. It is the acceptance frame for the submission: everything in scope is expected to work; everything out of scope is a conscious deferral.

- **Version:** 1.0 (MVP for the SmartReco Build Challenge 2026)
- **Deadline:** 9 Aug 2026, 07:30 BST
- **Target completion:** 8 Aug 2026

---

## 1. Problem

E-commerce shoppers face catalog overload. Static "related products" widgets and popularity-sorted lists ignore what each shopper actually cares about *right now*. The gap between browsing and buying is wider than it needs to be because the platform doesn't understand the shopper's evolving intent — it just serves the same top-N to everyone.

**Trove closes that gap.** The backend watches how each shopper behaves, understands their interests, retrieves the most relevant products from the real catalog, and generates a persuasive, personalized recommendation — a short narrative plus specific product picks — that refreshes as behavior shifts.

## 2. Vision

A commerce backend that treats each shopper's session as evidence to reason over, not a stream to append to. The system observes continuously, decides *when* recommendations are worth generating, retrieves grounded picks via semantic search, and writes short convincing copy that reads like it was written for one person. Delivery is both **pull** (visible on the site) and **push** (a scheduled daily digest).

## 3. Success Criteria

Trove is "done" when all of the following hold:

1. Every **Required** feature in the SmartReco Build Challenge brief is implemented and demonstrably works end-to-end.
2. All four **Highlighted Bonus** items ship: LangGraph agent, scheduled proactive delivery, LangSmith observability, retrieval polish (re-ranking + metadata filtering).
3. The critical CI checks pass on `main`: Python compiles; `requirements.txt` lists a web framework and an LLM client.
4. A reviewer can clone the repo, set `MESH_API_KEY` in `.env`, run `python run.py`, and complete the full loop (register → browse → get recommendations) in under 5 minutes.
5. The recommendation flow uses **real** Mesh API calls end-to-end — no mocked LLM responses in the demo path.

---

## 4. Users

### Shopper (role: `user`)

- Registers with email/password (or logs in)
- Browses the catalog and searches with natural language
- Views product detail pages
- Sees personalized recommendations at `/recommendations`
- Receives a daily digest recap (via mock delivery to the admin-viewable `digest_logs` table)

### Admin (role: `admin`)

- Manages the product catalog: create, edit, delete
- Verifies Mesh API health at `/admin/mesh-health` (chat + embed pings, SQLite/Chroma sync count)
- Inspects sent digests

Both roles share the same email/password login; the role flag decides which routes are reachable.

---

## 5. In Scope (MVP v1.0)

### 5.1 Platform foundation

- FastAPI web application, server-rendered Jinja2 templates
- Email/password authentication (bcrypt hashing, signed-cookie sessions)
- Two roles with route-level guards: `user`, `admin`
- SQLite persistence via SQLAlchemy 2.0
- Chroma vector store (persistent, local)
- All LLM + embedding calls routed through **Mesh API** (OpenAI-compatible)

### 5.2 Product management with dual-write

- Admin CRUD for products (title, description, category, level, price, tags, image URL)
- **Dual-write**: every product write goes to SQLite *and* Chroma atomically. If Chroma fails, the SQL transaction is rolled back — the two stores never drift.
- Admin health dashboard at `/admin/mesh-health` reports both counts side-by-side.

### 5.3 Behavioral event tracking

- Frontend tracker captures: `view_page`, `view_product`, `search`, `click`, `dwell`, `add_to_cart`, `recommendation_impression`, `recommendation_click`
- Batched, throttled, and non-blocking:
  - Flush trigger: 10 events queued, 5 seconds elapsed, or page hide/unload
  - Throttled types (`dwell`, `scroll`): max 1 event/sec per type
  - Unload flush uses `navigator.sendBeacon` so events survive tab close
- Backend endpoint `/events/ingest` does a bulk insert and returns `202 Accepted` without any downstream work on the request path

### 5.4 Agentic recommendation engine

- Built as a **LangGraph** state machine with explicit nodes:
  - `analyze_activity` — summarize recent events into structured interests
  - `decide_retrieve` — should we retrieve, or is the current recommendation still valid?
  - `retrieve` — semantic search over Chroma with metadata filters
  - `evaluate` — is the retrieved shortlist good enough?
  - `refine` — if not, broaden or narrow the query
  - `generate` — write the persuasive narrative + pick final products
- Retrieval is **grounded**: recommendations only reference product IDs returned by Chroma
- **Trigger policy**: agent runs only when *both* ≥ `RECO_MIN_NEW_EVENTS` new events AND ≥ `RECO_MIN_INTERVAL_MINUTES` since last run for that user
- **Fingerprint cache**: activity is hashed; if the hash matches the last stored recommendation, the LLM is skipped entirely (zero-cost repeat visits)
- Recommendations persist to the `recommendations` table and display at `/recommendations`

### 5.5 Retrieval polish

- **Metadata filtering** on category and level (Chroma `where` clauses)
- **Re-ranking**: retrieve top-15 shortlist, then a small LLM pass re-ranks to top-5
- **"You might also like"** on every product page: pure Chroma kNN (zero LLM cost) using the source product's stored embedding

### 5.6 Proactive delivery (scheduled digest)

- **APScheduler** in-process job that runs once daily at a configurable time (`DIGEST_HOUR`, `DIGEST_MINUTE`)
- For each active user with recent activity: runs the agent, generates a persuasive digest, writes to `digest_logs`
- **Mock delivery**: no SMTP required. Sent digests are visible in an admin view.

### 5.7 Observability

- **LangSmith tracing** wired through the agent workflow. Every node call — including retrieval hits, evaluate scores, and the final generation — is a span visible in a LangSmith run tree.
- Traces enabled by setting `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` in `.env`

### 5.8 Developer workflow

- Trunk-based git flow: feature branches → PR → squash-merge to `main`
- Conventional Commits
- CHANGELOG on every PR
- CI on every push/PR (`.github/workflows/smartreco-checks.yml`)
- Branch protection on `main` (see CONTRIBUTING.md)

---

## 6. Out of Scope

Deliberate exclusions. Each has a one-line reason so it doesn't look like an oversight.

| Not building                          | Why                                                           |
|---------------------------------------|---------------------------------------------------------------|
| Payments / checkout                   | Not in the challenge brief; recommendations end at "Enroll" button |
| Real SMTP email delivery              | Mock delivery to `digest_logs` is cleaner for reviewers       |
| Multi-tenancy / organizations         | Single-tenant sufficient for the demo                         |
| OAuth / social login                  | Brief says "keep auth simple"; email/password only            |
| Product image upload                  | Image URLs only — no file-storage layer needed                |
| User profile editing                  | Not required for the recommendation loop                      |
| Recommendation A/B testing            | Out of hackathon scope; would need traffic + statistics stack |
| Historical analytics dashboards       | Beyond required; admin dashboards limited to health + digest  |
| Fine-tuned / custom-trained models    | Mesh gateway is mandatory; only inference-time work           |
| Multilingual UI                       | English only                                                  |
| Native mobile / desktop app           | Web only                                                      |
| Rate limiting on user endpoints       | Sane defaults only; production hardening deferred             |
| Postgres / Supabase in production     | SQLite makes the reviewer flow frictionless (see README)      |
| Row-level security / column encryption| Sensitive data (passwords) hashed; catalog data is public     |

---

## 7. Feature Scope — Acceptance Criteria

Each capability lists the concrete "done" tests. If a bullet doesn't hold when the reviewer tries it, the capability is not done.

### 7.1 Authentication & authorization

- Registering with a valid email + password creates a `user`-role account and sets a session cookie
- Duplicate email registration returns 400 with a visible error
- Login with correct credentials sets a session cookie; wrong password returns 400 with error
- Logout clears the session cookie
- `/admin/*` routes return 403 for a `user`-role account
- `/admin/*` routes return 200 for an `admin`-role account
- Bootstrap admin (`admin@trove.local` / `admin123`) exists after first startup

### 7.2 Catalog + search

- `/catalog` lists all active products with newest first
- `/catalog?q=agentic AI` returns products ranked by semantic similarity via Chroma
- Category chip filter narrows results while preserving the current query
- Level filter narrows results while preserving other filters
- Empty states differentiate "no matches for X", "nothing matches filters", and "catalog empty"

### 7.3 Product detail + related

- `/products/{id}` renders the product's full description, tags, and metadata
- "You might also like" strip shows 3–4 semantically similar products (excluding self)
- Related-products render costs zero LLM tokens at runtime (verified in LangSmith trace: no LLM span on product page load)

### 7.4 Dual-write

- Creating a product in `/admin/products` inserts a row in SQLite *and* a vector in Chroma before returning
- Editing a product updates both stores
- Deleting a product removes from both stores
- `/admin/mesh-health` shows equal SQLite and Chroma counts after any CRUD operation
- If Chroma is unavailable during a create/update, the SQL commit is rolled back (no orphan rows in SQLite)

### 7.5 Behavioral tracking

- Navigating any page emits a `view_page` or `view_product` event
- Searching emits a `search` event with the query in the payload
- Clicking a product card emits a `click` event with the product ID
- Dwelling on a page emits `dwell` events at most once per 10 seconds
- Closing the tab flushes queued events via `sendBeacon` (verify: events created ≤ 5s before close are persisted)
- The event ingest endpoint returns within 50ms even for a 10-event batch

### 7.6 Agent

- With < `RECO_MIN_NEW_EVENTS` new events, no LLM call is triggered
- With ≥ `RECO_MIN_NEW_EVENTS` new events but < `RECO_MIN_INTERVAL_MINUTES` since last run, no LLM call is triggered
- With both conditions met, the agent runs and produces a recommendation whose `product_ids_json` references only real product IDs from Chroma retrieval
- If the activity fingerprint matches the last stored recommendation, the LLM is skipped and the existing recommendation is returned
- A LangSmith trace exists for every agent run, showing all nodes and the final output

### 7.7 Scheduled digest

- APScheduler starts on app boot and schedules the digest at `DIGEST_HOUR:DIGEST_MINUTE`
- Manually triggering the job creates one `digest_logs` row per active user with recent activity
- The digest body includes the persuasive narrative + a bulleted list of the recommended products

### 7.8 Observability

- With `LANGSMITH_TRACING=true`, every agent run appears in the LangSmith project
- Each run's tree shows the graph nodes as spans (analyze, retrieve, evaluate, refine, generate)

---

## 8. Architecture

See [README.md](./README.md#architecture) for the diagram and per-layer breakdown. No architectural changes are planned during MVP delivery — Day 3 onwards fills in code inside the already-defined seams (`app/agent/`, `app/scheduler/`).

---

## 9. Constraints & Assumptions

**Constraints**

- **Mesh API is mandatory** for all LLM + embedding calls
- **CI must pass** the two critical checks on every merged commit
- **~6 developer-days** available (Aug 3–8), solo build
- **~$5 of Mesh credit** budgeted for the whole build; iteration on agent prompts is the main burn source

**Assumptions**

- Mesh API endpoint `https://api.meshapi.ai/v1` remains reachable throughout the build
- Chroma runs embedded (no separate service needed)
- SQLite is sufficient for judging traffic (single user or single reviewer at a time)
- The reviewer environment has Python 3.11+ and network access to Mesh
- Mesh's model catalog includes at least one OpenAI-compatible chat model and one embedding model

---

## 10. Delivery Milestones

Ordered by dependency, not calendar day — some can slip a day without cascading. Each row corresponds to one merged PR.

| # | Milestone                                           | Ship condition                                                     | Status  |
|---|-----------------------------------------------------|--------------------------------------------------------------------|---------|
| 1 | Scaffold + auth + DB + tracker + dual-write         | 0.1.0 released; CI green                                           | ✅ done |
| 2 | Trove rebrand + admin edit + catalog polish + health| 0.2.0 released                                                     | ✅ done |
| 3 | Workflow setup (CHANGELOG, CONTRIBUTING, PR template)| Docs merged; every subsequent PR follows the template             | 🟡 in review |
| 4 | Activity summary service                            | `services/activity_summary.py` returns structured interest signals | ⚪ next  |
| 5 | LangGraph agent — happy path                        | 0.3.0; end-to-end recommendation generated + persisted             | ⚪       |
| 6 | Trigger policy + fingerprint cache                  | Skips are observable in logs / LangSmith                           | ⚪       |
| 7 | APScheduler daily digest                            | 0.4.0; digest rows appear at scheduled time                        | ⚪       |
| 8 | LangSmith tracing wired end-to-end                  | All agent runs visible in LangSmith project                        | ⚪       |
| 9 | Retrieval re-ranking                                | Top-15 shortlist → LLM re-ranks to top-5                           | ⚪       |
| 10| README architecture diagram + demo video            | v1.0 released                                                      | ⚪       |

---

## 11. Risks & Mitigations

| Risk                                                  | Likelihood | Impact | Mitigation                                                                 |
|-------------------------------------------------------|------------|--------|----------------------------------------------------------------------------|
| Mesh credit exhaustion during agent iteration         | Medium     | High   | Fingerprint cache; use `gpt-4o-mini` for agent, keep prompts small; log every call in dev |
| LangGraph learning curve slows Day 4                  | Medium     | Medium | Start with the simplest linear graph, add branching only after happy path works |
| Chroma / SQLite drift under errors                    | Low        | High   | Dual-write already rolls back SQL on Chroma failure; nightly reconcile helper `dual_write.reindex_all()` |
| CI OIDC token expiry mid-run                          | Low        | Low    | Workflow already re-requests token per job                                 |
| Chat vs. embed model mismatch (dim change post-seed)  | Low        | High   | Pin embed model in `.env`; if changed, run `dual_write.reindex_all()`      |
| Time overrun — Days 4–6 slip                          | Medium     | High   | Trigger policy + fingerprint are optional-if-tight; ship agent happy path first, add caching last |
| Reviewer's environment lacks Mesh key                 | Low        | Medium | CI checks don't need Mesh; app boots without a key (seed step logs and skips) |

---

## 12. Definition of Done (v1.0 release)

Trove ships v1.0 when **all** of the following hold:

- [ ] All acceptance criteria in §7 pass on a fresh clone
- [ ] All four highlighted bonuses shipped (LangGraph, scheduled digest, LangSmith, retrieval polish)
- [ ] `CHANGELOG.md` has a dated `[1.0.0]` section describing the release
- [ ] `README.md` has an architecture diagram and quickstart
- [ ] CI on `main` is green
- [ ] Branch protection is active on `main`
- [ ] A 2–3 minute demo video/GIF is embedded in the README
- [ ] The starter admin credentials (`admin@trove.local` / `admin123`) work out of the box

---

## Change control

Changes to this document require a PR labeled `scope`. Once v1.0 ships, further scope changes go into a v1.1 planning document instead of editing v1.0's scope retroactively.
