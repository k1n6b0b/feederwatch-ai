/**
 * Tests for deriveChipInfo — the pure status→chip mapping function.
 */

import { describe, it, expect } from 'vitest'
import { deriveChipInfo } from '../../../addon/frontend/src/hooks/useStatus'
import type { StatusResponse } from '../../../addon/frontend/src/types/api'

function makeStatus(overrides: Partial<{
  mqttConnected: boolean
  frigateReachable: boolean
  modelLoaded: boolean
  dbOk: boolean
}>): StatusResponse {
  const {
    mqttConnected = true,
    frigateReachable = true,
    modelLoaded = true,
    dbOk = true,
  } = overrides

  return {
    mqtt: { connected: mqttConnected, host: 'localhost', port: 1883, authenticated: false },
    frigate: { reachable: frigateReachable, url: 'http://frigate.local:5000' },
    model: { loaded: modelLoaded, path: '/data/model.tflite', input_size: 224 },
    database: { ok: dbOk, detections: 100, size_bytes: 1024 * 1024 },
    uptime_seconds: 3600,
    version: '0.1.0',
  }
}

describe('deriveChipInfo', () => {
  it('returns connected when all services healthy', () => {
    const info = deriveChipInfo(makeStatus({}))
    expect(info.state).toBe('connected')
    expect(info.label).toBe('Connected')
  })

  it('returns error when model not loaded', () => {
    const info = deriveChipInfo(makeStatus({ modelLoaded: false }))
    expect(info.state).toBe('error')
    expect(info.label).toBe('Error')
  })

  it('returns error when database not ok', () => {
    const info = deriveChipInfo(makeStatus({ dbOk: false }))
    expect(info.state).toBe('error')
    expect(info.label).toBe('Error')
  })

  it('returns degraded when MQTT disconnected', () => {
    const info = deriveChipInfo(makeStatus({ mqttConnected: false }))
    expect(info.state).toBe('degraded')
    expect(info.label).toContain('MQTT')
  })

  it('returns degraded when Frigate unreachable', () => {
    const info = deriveChipInfo(makeStatus({ frigateReachable: false }))
    expect(info.state).toBe('degraded')
    expect(info.label).toContain('Frigate')
  })

  it('returns degraded label mentioning both when both down', () => {
    const info = deriveChipInfo(makeStatus({ mqttConnected: false, frigateReachable: false }))
    expect(info.state).toBe('degraded')
    expect(info.label).toContain('MQTT')
    expect(info.label).toContain('Frigate')
  })

  it('error takes priority over degraded (model + mqtt down)', () => {
    const info = deriveChipInfo(makeStatus({ modelLoaded: false, mqttConnected: false }))
    expect(info.state).toBe('error')
  })
})
