/**
 * Typed API client — all fetch calls centralized here.
 * No raw fetch() calls in components or hooks.
 */

import type {
  DailySummary,
  Detection,
  MqttRingEntry,
  PhenologyYear,
  Species,
  SpeciesDetail,
  StatusResponse,
} from '../types/api'

// Resolve relative to document.baseURI so the path is correct under HA Ingress
// (served at /api/hassio_ingress/<token>/) as well as in local dev (/).
const BASE = new URL('api/v1/', document.baseURI).pathname.replace(/\/$/, '')

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`)
  if (!resp.ok) {
    throw new Error(`API error ${resp.status}: ${await resp.text()}`)
  }
  return resp.json() as Promise<T>
}

async function del<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!resp.ok) {
    throw new Error(`API error ${resp.status}: ${await resp.text()}`)
  }
  return resp.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!resp.ok) {
    throw new Error(`API error ${resp.status}: ${await resp.text()}`)
  }
  return resp.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Detections
// ---------------------------------------------------------------------------

export const detections = {
  recent: (limit = 20, afterId?: number) =>
    get<Detection[]>(
      `/detections/recent?limit=${limit}${afterId != null ? `&after_id=${afterId}` : ''}`
    ),

  daily: (date: string, limit = 50, offset = 0) =>
    get<Detection[]>(`/detections/daily?date=${date}&limit=${limit}&offset=${offset}`),

  dailySummary: (date: string) =>
    get<DailySummary>(`/detections/daily/summary?date=${date}`),

  snapshotUrl: (id: number) => `${BASE}/detections/${id}/snapshot`,

  delete: (id: number) => del<{ deleted: boolean; id: number }>(`/detections/${id}`),
}

// ---------------------------------------------------------------------------
// Species
// ---------------------------------------------------------------------------

export const species = {
  list: (sort = 'count', limit = 50, offset = 0) =>
    get<Species[]>(`/species?sort=${sort}&limit=${limit}&offset=${offset}`),

  get: (scientificName: string) =>
    get<SpeciesDetail>(`/species/${encodeURIComponent(scientificName)}`),

  phenology: (scientificName: string) =>
    get<PhenologyYear[]>(`/species/${encodeURIComponent(scientificName)}/phenology`),
}

// ---------------------------------------------------------------------------
// Status
// ---------------------------------------------------------------------------

export const status = {
  get: () => get<StatusResponse>('/status'),
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export const config = {
  setThreshold: (threshold: number) =>
    post<{ threshold: number }>('/config/threshold', { threshold }),
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

export const exportApi = {
  csvUrl: (date?: string) => `${BASE}/export/csv${date ? `?date=${date}` : ''}`,
}

// ---------------------------------------------------------------------------
// Events (ring buffer)
// ---------------------------------------------------------------------------

export const events = {
  recent: () => get<MqttRingEntry[]>('/events/recent'),
}

// ---------------------------------------------------------------------------
// Deep link helpers
// ---------------------------------------------------------------------------

/**
 * Generates AllAboutBirds.org species page URL.
 * Rules confirmed from Cornell Lab site JavaScript:
 *   spaces → underscores, apostrophes → removed, hyphens preserved
 *
 * Examples:
 *   "Black-capped Chickadee" → "Black-capped_Chickadee"
 *   "Cooper's Hawk"          → "Coopers_Hawk"
 *   "American Goldfinch"     → "American_Goldfinch"
 */
export function aabUrl(commonName: string): string {
  const slug = commonName.replace(/ /g, '_').replace(/'/g, '')
  return `https://www.allaboutbirds.org/guide/${slug}/overview`
}

/**
 * Generates Frigate event deep link.
 * frigateBaseUrl comes from /api/v1/status response.
 */
export function frigateEventUrl(frigateBaseUrl: string, eventId: string): string {
  return `${frigateBaseUrl}/events/${eventId}`
}
