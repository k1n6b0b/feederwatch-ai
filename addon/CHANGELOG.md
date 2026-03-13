# Changelog

## 0.1.2-alpha.1

### Bug fixes
- Common names now shown everywhere (cards, modals, gallery) — existing rows backfilled at startup
- Delete from Feed now removes the card immediately without a page refresh
- "View in Frigate" link fixed — trailing slash stripped, event ID URL-encoded
- Gallery Alphabetical sort: previous data shown during sort change (no flash to 0 species)
- Daily page opens on local date (not UTC date — was showing tomorrow after ~8pm ET)
- Gallery species detail: best image shown even when no local snapshot exists
- MQTT duplicate log entries eliminated — in-memory dedup prevents re-classifying the same event on every Frigate update
- Frigate sub_label common names (e.g. "House Finch") now correctly reverse-mapped to scientific name before storage
- Confidence bar removed from feed cards (score still visible in modal)
- Frigate source badge removed from feed cards
- Frigate-classified amber dot removed from feed card images
- Escape key navigates back on SpeciesDetail and ConnectionStatus pages
- Gallery photo grid: clicking a photo opens the full DetectionModal (with delete + reclassify)

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
