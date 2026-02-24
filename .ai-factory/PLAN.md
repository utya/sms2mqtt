# Implementation Plan: Migrate to uv (no requirements.txt, no pip)

Branch: none (fast mode)
Created: 2025-02-24

## Settings
- Testing: yes (existing tests must pass via uv)
- Logging: standard (no new logging for this chore)
- Docs: yes (README and DESCRIPTION.md)

## Goal
- Replace all use of pip and `requirements*.txt` with **uv** (pyproject.toml + uv.lock).
- Two Python “projects”: root (sms2mqtt) and `sms2mqtt-persistence/`, each with own `pyproject.toml` and `uv.lock`.

## Commit Plan
- **Commit 1** (after tasks 1–2): `chore: migrate root project to uv`
- **Commit 2** (after tasks 3–4): `chore: migrate sms2mqtt-persistence to uv and update CI`
- **Commit 3** (after task 5): `docs: update README and DESCRIPTION for uv`

---

## Tasks

### Phase 1: Root project (sms2mqtt)

- [x] **Task 1: Add runtime and dev dependencies to root `pyproject.toml`, generate `uv.lock`**
  - **File:** `pyproject.toml`
  - In `[project]` add:
    - `dependencies = ["python-gammu>=3.2,<4", "paho-mqtt>=2.0", "certifi>=2023.7.22"]`
    - Optional: `[project.optional-dependencies]` with `dev = ["pytest>=7.0", "ruff>=0.8"]` (or put dev deps in main dependencies for simplicity; then CI uses `uv sync` and gets everything).
  - Run in repo root: `uv lock`.
  - **Deliverable:** `pyproject.toml` with deps, `uv.lock` at repo root. No new logging.
  - **Done:** `python-gammu` moved to optional `[run]` so CI can use `uv sync --extra dev` without system gammu; Docker uses `uv sync --frozen --no-dev --extra run`.

- [x] **Task 2: Update root `Dockerfile` to use uv only (no pip, no requirements.txt)**
  - **File:** `Dockerfile`
  - Install uv: e.g. `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/` (or official recommended way for Alpine).
  - Copy `pyproject.toml` and `uv.lock` (and any needed source) then run `uv sync --frozen --no-dev` (production image: no dev deps).
  - Remove any `pip install`, `COPY requirements.txt`, and use of `requirements.txt`.
  - Keep base `python:3.11-alpine` and `apk add gammu-dev` (and build-deps only if needed for compiling wheels; uv can fetch manylinux wheels so this may simplify).
  - **Deliverable:** Dockerfile builds with uv only; image runs `python /app/sms2mqtt.py` as today.
  - **Note:** On `python:3.11-alpine`, uv can be installed via `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/` (ensure binary is in `PATH`). If the official image is glibc-only, use the installer script from https://astral.sh/uv/install.sh or an Alpine-compatible uv image.

### Phase 2: sms2mqtt-persistence

- [x] **Task 3: Add `pyproject.toml` and `uv.lock` for sms2mqtt-persistence**
  - **Files:** `sms2mqtt-persistence/pyproject.toml`, `sms2mqtt-persistence/uv.lock`
  - Create `pyproject.toml` with `[project]`: name e.g. `sms2mqtt-persistence`, `requires-python = ">=3.11"`, dependencies from current `sms2mqtt-persistence/requirements.txt`: `paho-mqtt>=2.0,<3`, `psycopg2-binary>=2.9,<3`, `certifi>=2023.7.22`; dev/test: `pytest>=7.0`.
  - Run `uv lock` inside `sms2mqtt-persistence/` to generate `uv.lock`.
  - **Deliverable:** Dependencies defined only in pyproject.toml; uv.lock present. No logging changes.

- [x] **Task 4: Update sms2mqtt-persistence `Dockerfile` and CI to use uv**
  - **Files:** `sms2mqtt-persistence/Dockerfile`, `.github/workflows/ci.yml`, `.gitlab-ci.yml`
  - **Persistence Dockerfile:** Install uv (same pattern as root), copy `pyproject.toml` and `uv.lock`, run `uv sync --frozen --no-dev`. Remove `COPY requirements.txt` and `pip install -r requirements.txt`.
  - **GitHub Actions (ci.yml):** Use `astral-sh/setup-uv` (or equivalent); run `uv sync` in repo root (for main app + dev deps) and `uv run ruff` / `uv run pytest tests/`; for persistence run e.g. `cd sms2mqtt-persistence && uv sync && uv run pytest tests/ -v --tb=short` (or from root with `uv run` and correct PYTHONPATH if using workspace; simpler is two separate uv contexts).
  - **GitLab CI:** Replace `pip install -r requirements-dev.txt` and `PIP_CACHE_DIR` with uv: install uv, then `uv sync` (cache uv’s cache dir if desired). Run `uv run ruff` and `uv run pytest` for root; same for sms2mqtt-persistence as above.
  - **Deliverable:** No pip or requirements*.txt in CI or persistence Dockerfile.

### Phase 3: Cleanup and docs

- [x] **Task 5: Remove all requirements files and update README + DESCRIPTION**
  - **Delete:** `requirements.txt`, `requirements-dev.txt`, `sms2mqtt-persistence/requirements.txt`.
  - **README.md:** In “Development” replace pip install with uv: e.g. `uv sync` (and if dev deps are optional: `uv sync --all-extras` or the chosen convention). Update commands to `uv run pytest ...`, `uv run ruff ...`.
  - **.ai-factory/DESCRIPTION.md:** Change “requirements.txt for pinned deps” to “uv (pyproject.toml + uv.lock)”.
  - **AGENTS.md:** In project structure, replace references to `requirements.txt` / `requirements-dev.txt` with pyproject.toml and uv.lock for root and sms2mqtt-persistence.
  - **Deliverable:** No requirements*.txt in repo; docs and AGENTS.md describe uv workflow only.

---

## Verification
- `uv sync` in root and in `sms2mqtt-persistence/` succeed.
- Root: `uv run pytest tests/ -v`, `uv run ruff check .` and `uv run ruff format --check .` pass.
- Persistence: `cd sms2mqtt-persistence && uv sync && uv run pytest tests/ -v` pass.
- Docker build for main image and for sms2mqtt-persistence image succeed and containers run.
- CI (GitHub Actions and GitLab CI) pass with no pip or requirements files.
