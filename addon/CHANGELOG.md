# Changelog

## 0.1.3-alpha.1

_In development_

## 0.1.2

### Bug fixes

**Common names**
- Common names now shown everywhere (cards, modals, gallery) — existing rows backfilled at startup
- Backfill migration now queries the DB directly for wrong rows; was iterating a 590-entry dict and missing species outside it
- `backfill_reversed_sublabels` and WAMF import now use UPSERT — previously used `INSERT OR IGNORE`, silently leaving existing species rows with wrong common names
- WAMF import resolves common names from `BIRD_NAMES` at import time instead of falling back to scientific name on fresh installs

**Config**
- Frigate URL split into two fields: `frigate_api_url` (internal Docker URL for snapshot fetching) and `frigate_clips_ui_url` (browser-accessible URL for "View in Frigate" links); both default to the same value; backward-compatible with old `frigate_url` / `frigate_ui_url` key names
- `model_path` removed from user-visible config (always `/data/model.tflite`, not user-configurable)

**Images**
- Consistent 🪶 feather placeholder across all snapshot 404s: Feed cards, Gallery cards, and SpeciesDetail photo grid
- SpeciesDetail hero image hides entirely when no snapshot is available (was showing tiny feather in a large empty container)
- SpeciesDetail photo grid buttons remain clickable on missing snapshot (opens modal + Frigate clip link)

**Feed & gallery**
- Delete from Feed removes the card immediately without a page refresh
- "View in Frigate" link fixed — trailing slash stripped, event ID URL-encoded
- Gallery Alphabetical sort: previous data shown during sort change (no flash to empty)
- Daily page opens on local date (was showing tomorrow after ~8pm ET due to UTC mismatch)
- MQTT duplicate events eliminated — in-memory dedup prevents re-classifying the same Frigate event on every update message
- Frigate sub_label common names (e.g. "House Finch") now correctly reverse-mapped to scientific name before storage
- Gallery photo grid: clicking a photo opens the full DetectionModal (with delete + reclassify)
- Escape key navigates back on SpeciesDetail and ConnectionStatus pages
- Confidence bar and Frigate source badge removed from feed cards (score still visible in modal)

## 0.1.1

### Bug fixes
- MQTT pipeline: fixed sub_label extraction from Frigate list format `[label, score]`
- Classifier: fixed uint8 dtype handling for quantized AiY Birds V1 model output
- Camera normalization: camera names compared case-insensitively to configured list
- Security hardening: snapshot filenames validated against safe pattern before write

## 0.1.0

Initial release — Home Assistant Add-on with:
- Real-time bird detection via Frigate NVR MQTT events
- AiY Birds V1 TFLite classifier (965 species)
- Live feed with SSE streaming
- Gallery with species-level drill-down
- Daily activity heatmap
- MQTT re-publish (WAMF-compatible topics + new `feederwatch_ai/` namespace)
- Local snapshot storage
