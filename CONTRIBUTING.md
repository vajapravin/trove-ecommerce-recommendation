# Contributing to Trove

This document describes how changes land in Trove. The workflow is deliberately
small — one feature per branch, one PR per branch, CI green before merge.

---

## Local development

```bash
# One-time setup
python3.11 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Paste your MESH_API_KEY into .env

# Run
python run.py
# Or:  uvicorn app.main:app --reload
```

Then open <http://localhost:8000> and log in as `admin@trove.local` / `admin123`.

### Quick sanity checks before committing

```bash
# Syntax check on all Python files (mirrors the CI critical check)
python -m compileall -q app run.py

# Manually hit health + mesh checks
curl -s http://localhost:8000/health
# Then log in as admin and visit /admin/mesh-health
```

---

## Branch naming

Every change happens on a short-lived feature branch off `main`. Naming
convention:

```
<type>/<short-kebab-case-summary>
```

Examples:

- `feat/agent-langgraph-workflow`
- `feat/scheduler-daily-digest`
- `fix/tracker-dwell-throttle`
- `chore/bump-fastapi`
- `docs/architecture-diagram`
- `ci/pin-python-version`

Types match the commit-message types below.

---

## Commit messages

Trove uses **Conventional Commits**. Every commit message follows:

```
<type>(<scope>): <short summary in imperative mood>

<optional body — what and why, not how>

<optional footer — refs, breaking changes>
```

### Types

| Type       | When to use it                                                        |
|------------|-----------------------------------------------------------------------|
| `feat`     | A user-visible new feature or capability                              |
| `fix`      | A bug fix                                                             |
| `docs`     | README, CHANGELOG, comments, architecture notes                       |
| `chore`    | Deps, tooling, refactors with no behavior change                      |
| `refactor` | Code restructuring without behavior change                            |
| `test`     | Adding or updating tests                                              |
| `ci`       | GitHub Actions changes                                                |
| `perf`     | Performance improvement                                               |
| `security` | Auth, secrets handling, dependency CVE fixes                          |

### Scope

The subsystem touched. Pick one:

`agent`, `catalog`, `admin`, `auth`, `tracker`, `events`, `db`, `vector`,
`mesh`, `scheduler`, `readme`, `ci`, `repo`.

### Good examples

```
feat(agent): add LangGraph state and node skeletons
feat(catalog): add category chips and level filter
fix(auth): drop passlib in favor of bcrypt to avoid version mismatch
chore(brand): rename SmartReco → Trove throughout
docs(readme): document dual-write architecture
```

### Bad examples (and why)

- `updated code` — no type, no scope, no verb
- `fix bug` — no scope, doesn't say what bug
- `WIP` — do not commit WIP messages to `main`; squash them out on merge

---

## Pull requests

### One PR = one logical change

Aim for 100–400 lines of diff per PR. If a PR grows past that, split it —
smaller PRs are faster to review, easier to revert, and produce a cleaner
git history.

### Opening the PR

1. Push your branch: `git push -u origin <branch-name>`
2. Open the PR against `main`. The template auto-populates from
   `.github/pull_request_template.md` — fill in every section.
3. Add labels — at minimum one type label (`feature`, `fix`, `docs`, `chore`)
   and any scope labels that apply (`agent`, `frontend`, `db`, etc.).
4. Assign yourself.

### Merging

- Wait for CI to go green. Fix anything red before merging.
- Use **Squash and merge** to keep `main` history linear and readable.
- The squash commit message must follow the same Conventional Commits format
  as regular commits — GitHub pre-fills it with the PR title, so making the PR
  title conformant makes this automatic.
- Delete the branch after merge.

### After merging

```bash
git checkout main
git pull
git branch -d <branch-name>
```

---

## Changelog

Every PR that changes user-visible behavior updates `CHANGELOG.md` under the
`[Unreleased]` section. Add a line under `### Added`, `### Changed`, `### Fixed`,
or `### Security` as appropriate.

When it's time to cut a release, promote `[Unreleased]` to a versioned section
(e.g. `[0.3.0] - YYYY-MM-DD`) and open a fresh `[Unreleased]` above it.

Version bump rules (SemVer, adapted for pre-1.0):

- **Patch** (`0.2.0 → 0.2.1`) — bug fixes, docs, chores, no new capability
- **Minor** (`0.2.0 → 0.3.0`) — new user-visible feature
- **Major** (`0.x → 1.0.0`) — reserved for the first stable/production release

Pure-docs and CI-only PRs do not bump the version.

---

## CI expectations

Every push and pull request runs the SmartReco Checks workflow at
`.github/workflows/smartreco-checks.yml`. The critical checks must pass
before merge:

- Python code compiles (no syntax errors)
- `requirements.txt` lists a web framework and an LLM client

Advisory checks (feedback only, do not block):

- `README.md` present
- `.gitignore` excludes `.env`
- No committed `.env` file

If a PR is blocked because CI is red, fix it in the same branch and push
again — do not open a new PR.

---

## What not to commit

- `.env` (only `.env.example` is tracked)
- `data/` contents (SQLite DB files)
- `chroma_db/` contents (vector store persistence)
- `logs/` contents
- `__pycache__/` and any `*.pyc`
- IDE workspace files (`.vscode/`, `.idea/`)
- OS metadata (`.DS_Store`, `Thumbs.db`)

All the above are already in `.gitignore` — if you notice something you added
sneaking in, add it to `.gitignore` in the same PR.
