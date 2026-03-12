# FeederWatch AI

AI-powered bird species identification for Home Assistant, using your Frigate NVR camera.

[![CI](https://github.com/k1n6b0b/feederwatch-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/k1n6b0b/feederwatch-ai/actions/workflows/ci.yml)

---

## How it works

Frigate detects motion → FeederWatch AI classifies the bird → species appears in your HA dashboard with snapshot, confidence score, and AllAboutBirds link.

```
Frigate NVR ──MQTT──► FeederWatch AI Add-on ──► SQLite DB + Web UI
                                │
                                └──MQTT──► HA HACS Integration (sensors, notifications)
```

**Model:** [Google AIY Vision Classifier Birds V1](https://tfhub.dev/google/lite-model/aiy/vision/classifier/birds_V1/3) — 964 North American bird species, downloaded automatically on first startup.

---

## Requirements

- Home Assistant with Supervisor (any install type)
- [Frigate NVR](https://frigate.video) add-on
- A camera pointed at your feeder

---

## Installation

### 1. Add this repository to HA Add-on Store

In HA: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**

```
https://github.com/k1n6b0b/feederwatch-ai
```

### 2. Install the add-on

Search for **FeederWatch AI** and install.

### 3. Configure

| Option | Description | Default |
|--------|-------------|---------|
| `frigate_url` | URL of your Frigate instance | `http://frigate:5000` |
| `mqtt_host` | MQTT broker hostname | `homeassistant.local` |
| `mqtt_port` | MQTT broker port | `1883` |
| `mqtt_username` | MQTT username (optional) | — |
| `mqtt_password` | MQTT password (optional) | — |
| `camera_names` | List of Frigate camera names to monitor | `["birdcam"]` |
| `classification_threshold` | Minimum confidence to save a detection (0.1–1.0) | `0.7` |
| `store_snapshots` | Save bird snapshots locally | `true` |

### 4. Start

The add-on downloads the AI model on first startup (~3.5 MB). Check logs for progress.

---

## Features

- **Live feed** — real-time detections via SSE
- **Daily summary** — detections by hour, species table, CSV export
- **Species gallery** — phenology charts, AllAboutBirds links
- **Connection status** — MQTT/Frigate/model health, MQTT event log
- **WAMF migration** — import your existing `speciesid.db` from WhosAtMyFeeder

---

## HACS Integration

> **Status: Phase 3 — in development**

The HACS integration will surface HA entities:
- `binary_sensor.classified_bird_present` + per-species sensors
- `sensor.bird_species_count`, `sensor.total_detections`
- HA notifications for new detections and first-ever species

---

## Development

```bash
# Python tests
pip install -r addon/requirements.txt -r requirements-test.txt
pytest

# Frontend tests
cd addon/frontend && npm ci && npm test

# Local dev stack (Docker Compose)
docker compose -f docker-compose.dev.yml up
```

---

## Security

See [SECURITY.md](SECURITY.md) for the vulnerability disclosure policy.

Dependencies are audited with [Trivy](https://trivy.dev) on every commit. No CRITICAL/HIGH CVEs at time of release.

---

## Credits

Concept and original implementation: **[mmcc-xx/WhosAtMyFeeder](https://github.com/mmcc-xx/WhosAtMyFeeder)**

Bird classification model: **[Google AIY Vision Classifier Birds V1](https://tfhub.dev/google/lite-model/aiy/vision/classifier/birds_V1/3)**

---

## License

MIT — see [LICENSE](LICENSE)
