# FeederWatch AI — Build Instructions

## Before You Start

Read `CONTEXT.md` in full. It covers the legal basis, architecture decisions, and lessons learned
from the WAMF codebase that this project replaces. Do not deviate from the architecture without
updating CONTEXT.md first.

## Repo Layout

```
feederwatch-ai/
├── addon/                          # HA Add-on (Docker container)
│   ├── Dockerfile
│   ├── config.yaml                 # Add-on manifest + options schema
│   ├── run.sh                      # Add-on entrypoint
│   ├── src/
│   │   ├── main.py                 # asyncio entry point
│   │   ├── classifier.py           # ai-edge-litert wrapper
│   │   ├── mqtt_client.py          # aiomqtt consumer
│   │   ├── db.py                   # aiosqlite schema + queries
│   │   ├── api.py                  # aiohttp REST routes
│   │   └── config.py               # options loading
│   ├── data/                       # .gitignore — persistent Add-on storage
│   └── requirements.txt
├── custom_components/
│   └── feederwatch_ai/             # HACS Integration
│       ├── __init__.py
│       ├── manifest.json
│       ├── config_flow.py
│       ├── coordinator.py
│       ├── sensor.py
│       ├── binary_sensor.py
│       ├── camera.py
│       └── strings.json
├── tests/
│   ├── addon/
│   └── integration/
├── hacs.json
├── repository.yaml                 # HA Add-on repository manifest
├── CONTEXT.md
├── INSTRUCTIONS.md
└── README.md
```

## Development Environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install ai-edge-litert aiomqtt aiohttp aiosqlite pyyaml
pip install pytest pytest-asyncio pytest-aiohttp
```

## Core Principles

### Async-first
Every I/O operation must be async. No blocking calls on the event loop.
- DB: `async with aiosqlite.connect(DB_PATH) as db:`
- MQTT: `async with aiomqtt.Client(host) as client:`
- HTTP: `async with aiohttp.ClientSession() as session:`
- ML inference: `await loop.run_in_executor(None, classifier.classify, tensor_image)`

### Single process
No `multiprocessing`, no `threading` (except the executor for ML). One asyncio event loop.
The XNNPACK fork-safety issue from WAMF is impossible in this architecture.

### Structured logging
Use Python `logging` module, not bare `print()`. Log levels: DEBUG for per-event detail,
INFO for lifecycle events, WARNING for degraded operation, ERROR for failures.

### Configuration
Add-on reads options from `/data/options.json` (HA injects this). For local dev, load from
`config.yml` via env var `FEEDERWATCH_CONFIG`. No config hardcoded anywhere.

### Error handling
- All MQTT message handlers wrapped in `try/except` — log and continue, never crash the loop
- All Frigate HTTP calls have timeouts (2s for snapshot/thumbnail, 30s for clip)
- All DB operations use context managers — no connection leaks possible

## Add-on: Key Implementation Notes

### classifier.py
```python
# ai-edge-litert replacement for tflite_support
from ai_edge_litert.interpreter import Interpreter

class BirdClassifier:
    def __init__(self, model_path: str, num_threads: int = 4):
        self._interpreter = Interpreter(model_path=model_path)
        self._interpreter.allocate_tensors()
        # thread pool for executor calls
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def classify(self, image_array: np.ndarray) -> list[dict]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._classify_sync, image_array)

    def _classify_sync(self, image_array: np.ndarray) -> list[dict]:
        # set input tensor, invoke, read output tensor
        ...
```

### mqtt_client.py
```python
async def run_mqtt(config, classifier, db):
    async with aiomqtt.Client(
        hostname=config.mqtt_host,
        port=config.mqtt_port,
        username=config.mqtt_username,
        password=config.mqtt_password,
    ) as client:
        await client.subscribe(f"{config.frigate_topic}/events")
        async for message in client.messages:
            asyncio.create_task(handle_message(message, client, classifier, db, config))
```

### db.py
- Schema version tracked in `meta` table: `CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)`
- Migration: check `PRAGMA user_version`, apply numbered migrations in sequence
- All queries as `async def` functions returning typed dicts
- Batch `get_common_name` to avoid N+1: accept a list of scientific names, return a dict

### api.py (aiohttp)
Route prefix: `/api/v1/`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/detections/recent?limit=5` | Recent detections |
| GET | `/api/v1/detections/daily?date=YYYY-MM-DD` | Daily summary |
| GET | `/api/v1/status` | Add-on health/config |
| DELETE | `/api/v1/detections/{frigate_event}` | Delete a detection |

Web UI served from `addon/src/static/` — keep it minimal (vanilla JS, no build step).

## HACS Integration: Key Implementation Notes

### manifest.json
```json
{
  "domain": "feederwatch_ai",
  "name": "FeederWatch AI",
  "version": "0.1.0",
  "config_flow": true,
  "documentation": "https://github.com/k1n6b0b/feederwatch-ai",
  "requirements": [],
  "dependencies": [],
  "codeowners": ["@k1n6b0b"]
}
```

### config_flow.py
Step 1: User enters Add-on URL (default `http://localhost:8099`).
Step 2: Integration validates URL by hitting `/api/v1/status`.
Step 3: Config entry created. No MQTT config needed here — Add-on handles MQTT.

### coordinator.py
- `DataUpdateCoordinator` polling `/api/v1/detections/recent` every 30s
- On new detection: fire `EVENT_STATE_CHANGED` for relevant entities
- On new species: fire custom event `feederwatch_ai_new_species`

## MQTT Topic Schema (publish from Add-on)

Maintain backward compatibility with WAMF topic schema so existing HA automations keep working:

```
whosatmyfeeder/detections          — common name, on each detection (no retain)
whosatmyfeeder/new_species         — JSON payload, first-ever detection (retain)
whosatmyfeeder/new_species/common_name
whosatmyfeeder/new_species/scientific_name
whosatmyfeeder/new_species/score
whosatmyfeeder/new_species/camera
whosatmyfeeder/new_species/frigate_event
```

New topics (FeederWatch AI additions):
```
feederwatch_ai/detection           — full JSON payload, every detection
feederwatch_ai/status              — Add-on health heartbeat (every 60s)
```

## Testing Strategy

### Unit tests (no external deps)
- `classifier.py`: mock interpreter, test image preprocessing
- `db.py`: use in-memory SQLite (`:memory:`), test all query functions
- `api.py`: use `aiohttp.test_utils.TestClient`, mock db and classifier
- MQTT handler logic: extract pure functions, test without broker

### Integration tests (requires Frigate + MQTT broker)
- Send real MQTT event → assert DB row inserted, sublabel set on Frigate
- Test sub_label fallback path (WAMF below threshold, Frigate has sub_label)
- Test new_species publish (assert retained message on broker)
- These run manually or in a local docker-compose environment

### Local docker-compose for integration testing
Provide a `docker-compose.test.yml` with:
- MQTT broker (eclipse-mosquitto)
- Mock Frigate (simple aiohttp server returning test images)
- FeederWatch AI Add-on under test

## DB Migration from WAMF

Provide `tools/migrate_from_wamf.py`:
```bash
python tools/migrate_from_wamf.py \
  --source /path/to/wamf/data/speciesid.db \
  --dest /path/to/feederwatch-ai/data/feederwatch.db
```

Schema differences to handle:
- `category_name = 'frigate_classified'` rows (new in WAMF after our changes)
- `detection_index = -1` for Frigate-classified rows

## Distribution

### Add-on Repository
- `repository.yaml` in repo root lists the `addon/` folder as an Add-on
- Users add `https://github.com/k1n6b0b/feederwatch-ai` as an Add-on repository in HA

### HACS
- `hacs.json`: `{"name": "FeederWatch AI", "render_readme": true}`
- Submit to HACS default once stable: https://github.com/hacs/default

## Before Public Release Checklist

- [ ] Contact mmcc-xx on GitHub — inform of project, offer credit/collaboration
- [ ] Add attribution in README: "Inspired by WhosAtMyFeeder by mmcc-xx"
- [ ] Ensure zero lines copied from original source
- [ ] Semantic version tagged (`v0.1.0`)
- [ ] HACS `hacs.json` present and valid
- [ ] Add-on `config.yaml` options schema complete
- [ ] README with screenshots
- [ ] MIT LICENSE added to this repo
