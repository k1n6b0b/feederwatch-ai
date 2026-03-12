# FeederWatch AI — Project Context

## What This Is

FeederWatch AI is a clean-room rewrite of the bird feeder species identification concept pioneered
by WhosAtMyFeeder (github.com/mmcc-xx/WhosAtMyFeeder). It is designed as a first-class Home
Assistant Add-on + HACS Integration, with full configurability, modern async architecture, and
no dependency on the original codebase.

## Legal Groundwork

- The original repo (mmcc-xx/WhosAtMyFeeder) has **no LICENSE file**. Under copyright law this
  means all rights reserved — the code cannot legally be forked and redistributed.
- This project is a **clean-room rewrite**: no copying of original source, algorithms rewritten
  from scratch, architecture diverges substantially.
- Before public release, make one good-faith attempt to contact the original author (mmcc-xx on
  GitHub) to inform them of this project and offer to collaborate or credit them.
- Credit the original concept in README and HACS description regardless.

## Architecture Decision: Add-on + HACS Integration (Frigate Model)

Frigate NVR is the reference architecture: a Docker container Add-on that does the heavy lifting,
paired with a HACS custom_component Integration that surfaces entities in HA.

```
┌─────────────────────────────────────────────────────┐
│  Home Assistant Host                                │
│                                                     │
│  ┌─────────────────────┐   MQTT   ┌──────────────┐ │
│  │  FeederWatch AI     │ ◄──────► │  Frigate NVR │ │
│  │  (HA Add-on)        │          └──────────────┘ │
│  │                     │                            │
│  │  - aiomqtt listener │   REST   ┌──────────────┐ │
│  │  - ai-edge-litert   │ ◄──────► │  Frigate API │ │
│  │  - aiohttp web UI   │          └──────────────┘ │
│  │  - SQLite store     │                            │
│  └──────────┬──────────┘                            │
│             │ MQTT / REST API                       │
│  ┌──────────▼──────────┐                            │
│  │  FeederWatch AI     │                            │
│  │  (HACS Integration) │                            │
│  │                     │                            │
│  │  - sensor entities  │                            │
│  │  - binary_sensor    │                            │
│  │  - camera entity    │                            │
│  │  - event entity     │                            │
│  │  - config flow UI   │                            │
│  └─────────────────────┘                            │
└─────────────────────────────────────────────────────┘
```

### Why Two Components?

- **Add-on**: Runs the ML classifier and Frigate MQTT consumer. Needs Python 3.12+, heavy deps
  (ai-edge-litert, aiohttp), persistent SQLite. Cannot run inside HA Core process.
- **HACS Integration**: Surfaces HA entities, automations, Lovelace cards. Lives in
  `custom_components/feederwatch_ai/`. Communicates with the Add-on over local REST or MQTT.
- Users who don't use Supervisor (HA Container / Core) can still use just the HACS Integration
  pointed at a manually-run Docker container.

## Technical Stack

### ML / Classification
- **ai-edge-litert** (Google's successor to tflite_support) — unblocks Python 3.12+
- Same iNaturalist bird classifier model (`.tflite`) as WhosAtMyFeeder
- Model file bundled in Add-on image or downloaded on first run

### Async Core (eliminates all fork-safety issues from WAMF)
- **aiomqtt** — async MQTT client, replaces paho-mqtt + multiprocessing
- **aiohttp** — async web framework, replaces Flask + multiprocessing
- **asyncio** — single process, single event loop, no forking
- No XNNPACK thread-pool / fork-safety issue (classify runs in executor)

### Storage
- **SQLite** via `aiosqlite` — async-compatible, same schema as WAMF (migration path)
- Schema versioned with simple integer migrations (no Alembic)

### Add-on
- Python 3.12 base image
- HA Add-on options schema (`config.yaml`) — no hand-editing YAML
- Ingress support for web UI (accessible via HA sidebar)
- Watchdog / healthcheck built into Add-on manifest

### HACS Integration
- `config_entries` config flow — UI setup, no YAML
- `coordinator` pattern (DataUpdateCoordinator) — polling Add-on REST API
- Full entity registry integration

## HA Entity Model

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.feederwatch_last_species` | sensor | Common name of most recent detection |
| `sensor.feederwatch_today_count` | sensor | Unique species seen today |
| `sensor.feederwatch_total_detections` | sensor | All-time detection count |
| `binary_sensor.feederwatch_bird_present` | binary_sensor | True when a bird was detected in the last N minutes |
| `camera.feederwatch_last_snapshot` | camera | Latest classified bird snapshot |
| `event.feederwatch_new_species` | event | Fires when a species is seen for the first time |
| `event.feederwatch_detection` | event | Fires on every detection above threshold |

## Add-on Configuration Schema (options)

```yaml
frigate_url: "http://frigate:5000"
mqtt_host: "homeassistant.local"
mqtt_port: 1883
mqtt_username: ""
mqtt_password: ""
mqtt_use_tls: false
camera_names:
  - "birdcam"
classification_threshold: 0.7
model_path: "/data/model.tflite"
```

## HACS Distribution Requirements

- `hacs.json` in repo root with `name`, `render_readme: true`
- `custom_components/feederwatch_ai/manifest.json` with `domain`, `version`, `requirements`
- Semantic versioning (`v1.0.0`), GitHub Releases for each version
- Brand assets: `icon.png` (256x256), `logo.png` submitted to `home-assistant/brands` later

## Development Sequencing

### Phase 1 — Add-on skeleton (1 week)
- Repo structure: `addon/`, `custom_components/feederwatch_ai/`, `hacs.json`
- Add-on: asyncio entry point, aiomqtt consumer, classify in thread executor
- SQLite store with schema v1 (compatible with WAMF schema for migration)
- aiohttp: `/api/detections/recent`, `/api/status`, static web UI placeholder
- Docker build + local test

### Phase 2 — HACS Integration (1 week)
- Config flow: Frigate URL + Add-on URL entry
- DataUpdateCoordinator polling Add-on REST
- All entities wired up
- Test against real HA instance

### Phase 3 — Feature parity + UI (1–2 weeks)
- Web UI (aiohttp): daily summary, detection history, species gallery
- MQTT new_species publish (same topic schema as WAMF for HA automation compatibility)
- Sublabel write-back to Frigate
- Migration tool: import existing WAMF SQLite DB

### Phase 4 — Polish + Distribution (1 week)
- HA Add-on repo setup (`repository.yaml`)
- HACS submission
- README, screenshots, documentation
- Contact original author

## Key Lessons from WAMF (What to Avoid)

- No `multiprocessing.Process` for ML — use `asyncio.get_event_loop().run_in_executor()`
- No silent exception swallowing in MQTT callbacks — structured error handling + logging
- No `conn.close()` leaks — use context managers (`async with aiosqlite.connect(...)`)
- No temp files written to CWD — use `/data/` (Add-on persistent storage) or in-memory
- No hardcoded DB paths in multiple files — single config object
- No `firstmessage` global flag hack — handle MQTT reconnect properly with aiomqtt
- No sentinel strings returned from lookup functions — always `None` on miss
- N+1 DB queries — batch `WHERE display_name IN (...)` lookups

## Reference Projects

- **Frigate NVR** — Add-on + HACS Integration architecture reference
- **Double Take** — Frigate companion app pattern
- **HACS** — `hacs.json` format and submission requirements
- **ai-edge-litert** — https://github.com/google-ai-edge/LiteRT
- **aiomqtt** — https://github.com/sbtinstruments/aiomqtt
