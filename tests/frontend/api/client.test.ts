/**
 * Tests for the typed API client: helpers, URL builders, fetch wrappers.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { aabUrl, frigateEventUrl, detections } from '../../../addon/frontend/src/api/client'

// ---------------------------------------------------------------------------
// AllAboutBirds URL helper
// ---------------------------------------------------------------------------

describe('aabUrl', () => {
  it('replaces spaces with underscores', () => {
    expect(aabUrl('American Robin')).toBe(
      'https://www.allaboutbirds.org/guide/American_Robin/overview'
    )
  })

  it('removes apostrophes', () => {
    expect(aabUrl("Cooper's Hawk")).toBe(
      "https://www.allaboutbirds.org/guide/Coopers_Hawk/overview"
    )
  })

  it('preserves hyphens', () => {
    expect(aabUrl('Black-capped Chickadee')).toBe(
      'https://www.allaboutbirds.org/guide/Black-capped_Chickadee/overview'
    )
  })

  it('handles multi-word names with apostrophes', () => {
    expect(aabUrl("Steller's Jay")).toBe(
      "https://www.allaboutbirds.org/guide/Stellers_Jay/overview"
    )
  })

  it('handles single-word name', () => {
    expect(aabUrl('Mallard')).toBe(
      'https://www.allaboutbirds.org/guide/Mallard/overview'
    )
  })
})

// ---------------------------------------------------------------------------
// Frigate event URL helper
// ---------------------------------------------------------------------------

describe('frigateEventUrl', () => {
  it('builds correct URL', () => {
    expect(frigateEventUrl('http://192.168.1.10:5000', 'abc-123')).toBe(
      'http://192.168.1.10:5000/events/abc-123'
    )
  })

  it('does not produce double-slash in path', () => {
    const url = frigateEventUrl('http://frigate.local:5000', 'evt-456')
    // Should be .../events/... not ...//events/...
    expect(url).not.toMatch(/[^:]\/\//)
    expect(url).toContain('/events/evt-456')
  })

  it('strips trailing slash from base URL', () => {
    expect(frigateEventUrl('http://frigate.local:5000/', 'evt-789')).toBe(
      'http://frigate.local:5000/events/evt-789'
    )
  })

  it('encodes special characters in event ID', () => {
    const url = frigateEventUrl('http://frigate.local:5000', '1773407461.534049-3st0ju')
    expect(url).toBe('http://frigate.local:5000/events/1773407461.534049-3st0ju')
  })
})

// ---------------------------------------------------------------------------
// Snapshot URL builder
// ---------------------------------------------------------------------------

describe('detections.snapshotUrl', () => {
  it('uses internal detection ID', () => {
    expect(detections.snapshotUrl(42)).toBe('/api/v1/detections/42/snapshot')
  })
})

// ---------------------------------------------------------------------------
// Fetch wrapper: GET with error handling
// ---------------------------------------------------------------------------

describe('fetch wrapper', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    global.fetch = vi.fn()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('returns parsed JSON on 200', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => [{ id: 1, common_name: 'Robin' }],
    } as Response)

    const result = await detections.daily('2025-01-01')
    expect(result).toHaveLength(1)
    expect(result[0].common_name).toBe('Robin')
  })

  it('throws on non-OK response', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      status: 404,
      text: async () => 'Not Found',
    } as Response)

    await expect(detections.daily('2025-01-01')).rejects.toThrow('API error 404')
  })
})
