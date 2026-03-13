# FeederWatch AI — Claude Guide

Clean-room rewrite of [WhosAtMyFeeder](https://github.com/mmcc-xx/WhosAtMyFeeder) as a
Home Assistant Add-on + HACS Integration. Frigate NVR is the reference architecture.
Solo project by a backend/infra engineer — full-stack via AI pair programming.

See `CONTEXT.md` for architecture decisions and legal basis. See `INSTRUCTIONS.md` for
design principles and HACS/MQTT specs. This file is the quick-start for a fresh session.

---

## Repo layout

```
addon/                        # HA Add-on (Docker image)
  src/                        # Python backend
    main.py                   # asyncio entrypoint
    api.py                    # aiohttp REST routes  (/api/v1/*)
    db.py                     # aiosqlite schema + all queries
    mqtt_client.py            # aiomqtt Frigate event consumer + classifier
    classifier.py             # ai-edge-litert TFLite wrapper
    bird_names.py             # static scientific→common name dict (965 species)
    config.py                 # options.json loader
    download_model.py         # model download on first boot
  frontend/                   # React + TypeScript SPA
    src/
      api/client.ts           # all API calls + URL helpers
      components/             # DetectionModal, DetectionCard, SpeciesCard, StatusChip…
      pages/                  # Feed, Gallery, Daily, SpeciesDetail, ConnectionStatus
      hooks/                  # useDetections, useSpecies, useStatus, useSSE
      types/api.ts            # shared TypeScript types
  Dockerfile                  # multi-stage: Node build → Python 3.12 runtime
  config.yaml                 # HA Add-on manifest + options schema (version field here)
  requirements.txt            # pinned Python deps
custom_components/feederwatch_ai/   # HACS Integration (Phase 3 — not yet built)
tests/
  addon/                      # pytest tests (107/107 passing)
  frontend/                   # vitest tests (91/91 passing)
```

---

## Commands

### Backend
```bash
# Test (run from repo root)
.venv/bin/pytest tests/addon/ -q

# Lint
.venv/bin/ruff check addon/src/ tests/addon/

# SAST
.venv/bin/bandit -r addon/src/ -ll -ii --skip B101

# CVE scan
trivy fs addon/requirements.txt --severity CRITICAL,HIGH --ignore-unfixed --exit-code 1
```

### Frontend
```bash
cd addon/frontend
npm run build          # production build (must be 0 errors before deploy)
npm test -- --run      # vitest (one-shot, no watch)
npx tsc --noEmit       # type-check only
```

### Deploy to HA (Mountain Duck must be mounted)
```bash
# 1. Build frontend first
cd addon/frontend && npm run build && cd ../..

# 2. Rsync to HA (Mountain Duck mount path is machine-local — see deploy workflow memory)
rsync -av --exclude='__pycache__' --exclude='*.pyc' --exclude='node_modules' --exclude='dist' \
  addon/ \
  "<mountain-duck-mount>/addons/feederwatch_ai/"

# 3. Rebuild (NOT restart — restart reuses old image, changes don't apply)
ssh hass "ha apps rebuild local_feederwatch_ai"

# Tail logs
ssh hass "ha apps logs local_feederwatch_ai 2>&1 | tail -30"
```

### Release
Before tagging: run all five checks above, deploy + smoke-test, update `version:` in
`addon/config.yaml`, then:
```bash
git tag vX.Y.Z && git push origin main --tags
```
See `project_versioning.md` memory for the full checklist.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 (Docker), aiohttp, aiomqtt, aiosqlite, pydantic v2 |
| ML | ai-edge-litert (TFLite), AiY Birds V1 model (965 species) |
| Frontend | React 18, TypeScript strict, Vite, Tailwind CSS, TanStack Query/Virtual, Recharts |
| Tests | pytest-asyncio (auto mode), pytest-aiohttp, vitest |
| CI | GitHub Actions: gitleaks, trivy, bandit, npm audit, ruff, tsc, pytest, vitest, Docker build |

---

## Key decisions (don't relitigate without good reason)

- **All timestamps stored as local time** via `datetime.now().isoformat()` in Python — NOT
  SQLite's `datetime('now')` which is UTC. Daily page queries use `date.today()` (local).
- **No config in the web UI** — HA Add-on config tab handles it via `config.yaml` schema.
- **SSE for live feed** (`/api/v1/detections/stream`), TanStack Query for everything else.
- **Snapshot = local `/data/snapshots/`** (permanent). Video = Frigate link only (no local copy).
- **Frigate event URL**: `{frigate_url}/events/{event_id}` (not `/review`).
- **AllAboutBirds URL**: spaces→underscores, apostrophes→removed.
- **ConnectionStatus page** accessible only via StatusChip click — not in nav.
- **Detection category_name**: `ai_classified` | `frigate_classified` | `human_reclassified`.
- **Frigate sublabel fallback**: score ≥ threshold → `ai_classified`; score < threshold +
  Frigate sub_label set → `frigate_classified`; otherwise discard (log to ring buffer).
- **MQTT ring buffer**: 50 entries in-memory, never persisted, served at `/api/v1/events/recent`.
- **bird_names.py**: baked-in static dict, no download. `get_common_name()` falls back to
  scientific name for unknowns.

---

## What NOT to do

- Don't use `datetime('now')` in SQLite for new timestamps — use Python `datetime.now()`.
- Don't use `ha addons` CLI — it's deprecated, use `ha apps`.
- Don't use `ha apps restart` — use `ha apps rebuild` or source changes won't apply.
- Don't push to GitHub as a test step — test locally, then push.
- Don't add config UI — HA handles it.
- Don't skip the full local check suite before pushing (ruff → bandit → trivy → pytest →
  build+vitest). Each one caught a separate CI failure last time.
- Don't use `frigateReviewUrl` — it was replaced with `frigateEventUrl(base, eventId)`.

---

## Phase status

- [x] Phase 1 — Add-on backend (complete)
- [x] Phase 2 — React + TypeScript frontend (complete)
- [ ] Phase 3 — HACS Integration (`custom_components/feederwatch_ai/`)
- [ ] Phase 4 — Polish + distribution

## Known pre-existing issues

None — 107/107 backend tests and 91/91 frontend tests pass as of v0.1.0.
