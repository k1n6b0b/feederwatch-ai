/**
 * TypeScript types mirroring the Python API response models.
 * Keep in sync with api.py route handlers.
 */

export type CategoryName = 'ai_classified' | 'frigate_classified' | 'human_reclassified'

export interface Detection {
  id: number
  frigate_event_id: string
  scientific_name: string
  common_name: string
  score: number | null
  category_name: CategoryName
  camera_name: string
  snapshot_path: string | null
  detected_at: string // ISO 8601
  is_first_ever?: boolean
}

export interface Species {
  scientific_name: string
  common_name: string
  total_detections: number
  first_seen: string
  last_seen: string
  best_score: number | null
  best_snapshot_path: string | null
  best_detection_id: number | null
}

export interface WeeklyCell {
  day: number    // 0=Sun … 6=Sat
  hour: number   // 0–23
  count: number
}

export interface WeeklyPoint {
  week: string        // 'YYYY-WW'
  species: number
  detections: number
}

export interface SpeciesDetail extends Species {
  hourly_activity: HourlyBucket[]
}

export interface HourlyBucket {
  hour: number   // 0–23
  count: number
}

export interface PhenologyYear {
  year: string
  first_day_of_year: string
  last_day_of_year: string
  first_seen: string
  last_seen: string
  total: number
}

export interface DailySummary {
  date: string
  total_detections: number
  unique_species: number
  peak_hour: number | null
  hourly: HourlyBucket[]
  species: DailySpeciesRow[]
}

export interface DailySpeciesRow {
  scientific_name: string
  common_name: string
  count: number
  first_seen: string
  last_seen: string
  best_score: number | null
  is_first_ever: boolean
  category_name: CategoryName
}

export interface DiscoveredMqtt {
  host: string
  port: number
  username: string | null
  ssl: boolean
}

export interface StatusResponse {
  mqtt: {
    connected: boolean
    host: string
    port: number
    authenticated: boolean
    error: string | null
    error_type: 'auth' | 'connection' | null
  }
  frigate: {
    reachable: boolean
    url: string
  }
  model: {
    loaded: boolean
    labels_loaded: boolean
    path: string
    input_size: number
  }
  database: {
    ok: boolean
    detections: number
    size_bytes: number
  }
  uptime_seconds: number
  version: string
  discovery: {
    mqtt: DiscoveredMqtt | null
    frigate_url: string | null
  } | null
}

export type StatusChipState = 'connected' | 'degraded' | 'error'

export interface StatusChipInfo {
  state: StatusChipState
  label: string
}

export interface MqttRingEntry {
  timestamp: string
  camera: string
  frigate_event_id: string
  our_score: number | null
  threshold: number
  action: 'saved_ai' | 'saved_frigate' | 'below_threshold' | 'no_bird' | 'error'
  raw_payload: Record<string, unknown>
}
