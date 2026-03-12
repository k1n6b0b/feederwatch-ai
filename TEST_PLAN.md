# FeederWatch AI — Test Plan (Living Document)

> Updated as development progresses. Check items off as tests are written and passing.

---

## Unit Tests — Python (`tests/addon/`)

### `test_db.py`
- [x] Upsert and batch display name lookup
- [x] Empty and missing name lookups return empty dict
- [x] Upsert updates existing common name
- [x] Insert and get detection by ID
- [x] `detection_exists` true/false
- [x] `is_first_ever_species` before and after first insert
- [x] Delete detection — success and not-found
- [x] Total detection count
- [x] Cursor-based pagination for recent detections
- [x] `limit` > 100 does not error (capped internally)
- [x] Offset pagination for daily detections — no overlap between pages
- [x] Daily summary empty day returns 24 hourly buckets
- [x] Daily summary with data returns correct species count
- [x] Species list sort by count
- [x] Species detail returns None for unknown species
- [x] DB size bytes — present and missing file

### `test_classifier.py`
- [x] Preprocess produces correct shape (1, 224, 224, 3)
- [x] Preprocess normalizes to [0, 1]
- [x] Preprocess resizes arbitrary input dimensions
- [x] Preprocess rejects corrupt bytes
- [x] Classify sync returns top-K sorted descending
- [x] Shape mismatch raises ValueError
- [x] Async classify raises RuntimeError when not loaded
- [x] Async classify returns results with mocked interpreter
- [x] LabelMapper loads and maps class indices
- [x] LabelMapper skips out-of-range indices
- [x] Fixture image smoke test (CC0 images — skipped if not present)

### `test_api.py`
- [x] `/api/v1/status` returns 200 with correct shape
- [x] `/api/v1/detections/recent` empty
- [x] `/api/v1/detections/recent` returns data
- [x] `limit=999` does not error (capped)
- [x] `/api/v1/detections/daily` invalid date → 400
- [x] `/api/v1/detections/daily` valid date → 200
- [x] `/api/v1/detections/daily/summary` returns 24 hourly buckets
- [x] `/api/v1/species` empty
- [x] `/api/v1/species` invalid sort → 400
- [x] `/api/v1/species/{name}` not found → 404
- [x] `DELETE /api/v1/detections/{id}` success
- [x] `DELETE /api/v1/detections/{id}` not found → 404
- [x] `DELETE /api/v1/detections/not-an-int` → 400
- [x] `POST /api/v1/config/threshold` valid
- [x] `POST /api/v1/config/threshold` out of range → 400
- [x] `POST /api/v1/config/threshold` missing field → 400
- [x] `/api/v1/events/recent` empty
- [x] `/api/v1/export/csv` empty dataset
- [x] `/api/v1/export/csv?date=` with date
- [x] All routes have `X-Content-Type-Options: nosniff`
- [x] All routes have `X-Frame-Options: SAMEORIGIN` (not DENY)

### `test_connection_status.py`
- [x] All healthy → all fields true/connected
- [x] MQTT disconnected → `mqtt.connected = false`, model/DB ok
- [x] Model not loaded → `model.loaded = false`
- [x] Anonymous MQTT → `authenticated = false`
- [x] Authenticated MQTT → `authenticated = true`, password absent from response
- [x] Response shape has all required fields for StatusChip logic
- [x] Security headers: `X-Frame-Options: SAMEORIGIN` (not DENY)
- [x] CSP: `frame-ancestors 'self'` (not 'none')

### `test_mqtt_handler.py`
- [x] Valid Frigate event payload parses
- [x] Invalid payload raises ValidationError
- [x] Missing `type` field raises ValidationError
- [x] Sublabel field parsed correctly
- [x] Malformed JSON does not crash handler — ring buffer entry added
- [x] Non-bird label ignored silently
- [x] Wrong camera ignored silently
- [x] Sublabel fallback used when score below threshold
- [x] Ring buffer respects max size (RING_BUFFER_SIZE)

---

## Unit Tests — Frontend (`tests/frontend/`)

### `StatusChip.test.tsx`
- [ ] `connected` state: emerald color, "Connected" label
- [ ] `degraded` state: amber color, service name in label
- [ ] `error` state: red color, "Error" label
- [ ] Chip is a link to `/connection-status`
- [ ] Chip is NOT present in nav links (regression)
- [ ] Hover tooltip shows degraded service name

### `ConnectionStatus.test.tsx`
- [ ] Route `/connection-status` renders page
- [ ] Page NOT in nav links (second regression check)
- [ ] Status table rows present for each service
- [ ] Ring buffer table renders entries
- [ ] Empty ring buffer shows empty state

### `DetectionCard.test.tsx`
- [ ] All fields render (common name, score bar, camera, timestamp)
- [ ] Low-confidence card has amber border class
- [ ] Frigate-classified card shows `[Frigate]` badge, no confidence bar
- [ ] Click opens DetectionModal

### `DetectionModal.test.tsx`
- [ ] AllAboutBirds URL: `"Black-capped Chickadee"` → `.../Black-capped_Chickadee/overview`
- [ ] AllAboutBirds URL: `"Cooper's Hawk"` → `.../Coopers_Hawk/overview`
- [ ] AllAboutBirds URL: `"American Goldfinch"` → `.../American_Goldfinch/overview`
- [ ] Frigate link present with correct URL
- [ ] Video player renders for recent detection
- [ ] "No longer available" message shown when snapshot 404s

### `Feed.test.tsx`
- [ ] SSE mock → new card appears at top of grid
- [ ] SSE disconnect → polling fallback activates
- [ ] TanStack Virtual renders only visible cards (not all 1000)
- [ ] Frigate-classified card renders badge

### `Gallery.test.tsx`
- [ ] Default sort = Most Seen, cards in count-descending order
- [ ] Sort by Alphabetical changes card order
- [ ] Search filters by common name
- [ ] Search filters by scientific name
- [ ] `★ NEW TODAY` badge present on today's first detection

### `Daily.test.tsx`
- [ ] `[ Hourly Activity ]` toggle shows HourlyActivityChart
- [ ] `[ Weekly Heatmap ]` toggle shows ActivityHeatmap
- [ ] Date prev/next navigation changes date param
- [ ] Export CSV button triggers download URL
- [ ] ⭐ first-ever flag shown in species table

### `HourlyActivityChart.test.tsx`
- [ ] Correct 24 hourly buckets passed to Recharts
- [ ] Empty day (all zeros) renders without error
- [ ] Peak hour highlighted

---

## HACS Integration Tests (`pytest-homeassistant-custom-component`)

- [ ] Config flow: valid Add-on URL → entry created
- [ ] Config flow: invalid URL (no /api/v1/status response) → user-readable error
- [ ] Options flow: notification settings saved and persist
- [ ] Options flow: push target dropdown populated from hass.services
- [ ] Coordinator: entities update when API returns new detection
- [ ] Coordinator: `feederwatch_ai_detection` event fires on new detection
- [ ] Coordinator: `feederwatch_ai_new_species` event fires on new species
- [ ] `notifications.py`: persistent notification created on new species
- [ ] `notifications.py`: push notification sent to configured target
- [ ] `notifications.py`: push failure is silent — coordinator continues
- [ ] `notifications.py`: duplicate new-species notification deduplicated by notification_id
- [ ] `binary_sensor.feederwatch_classified_bird_present`: True during active event
- [ ] `binary_sensor.feederwatch_classified_bird_present`: False after event end
- [ ] `binary_sensor.feederwatch_{species}_present`: auto-created on first detection
- [ ] `binary_sensor.feederwatch_{species}_present`: True/False with event lifecycle
- [ ] `image` entity URL updates on new detection
- [ ] All entities grouped under single Device

---

## Integration Tests (`docker-compose.test.yml`)

- [ ] Full pipeline: MQTT event → DB insert → SSE push → API response
- [ ] Sublabel fallback: below-threshold + Frigate sub_label → `frigate_classified` row
- [ ] `store_snapshots: true` → file written to `/data/snapshots/{event_id}.jpg`
- [ ] Frigate snapshot 404 → placeholder served from `/api/v1/detections/{id}/snapshot`
- [ ] WAMF backward-compat: `whosatmyfeeder/detections` topic published on each detection
- [ ] WAMF backward-compat: `whosatmyfeeder/new_species` retained on first-ever detection
- [ ] Migration tool: WAMF fixture DB → all rows transferred, schema valid

---

## Manual Verification Checklist

- [ ] HA Ingress: UI accessible via sidebar, HA handles auth — no login prompt in UI
- [ ] Add-on config tab: all options render as GUI form fields — no YAML editing required
- [ ] connection-status chip: transitions green → amber → red with real service failures
- [ ] connection-status chip click: navigates to `/connection-status`, not in nav
- [ ] Ring buffer: below-threshold events appear with correct score and threshold shown
- [ ] Ring buffer: Frigate sublabel events show `saved_frigate` action
- [ ] New species: persistent notification appears in HA bell icon
- [ ] New species: push notification delivered to configured target
- [ ] Per-species binary sensor: auto-appears in entity registry on first detection
- [ ] AllAboutBirds links: open correct species page in browser
- [ ] Frigate links: open correct event in Frigate UI
- [ ] Video clip: plays in modal; graceful message when expired
- [ ] Snapshot: served from local file (not Frigate) for old detections
