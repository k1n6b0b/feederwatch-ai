/**
 * StatusChip component tests.
 * Verifies all 3 visual states, tooltip content, link target, loading state.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { StatusResponse } from '../../../addon/frontend/src/types/api'

// vi.mock must be at module top level
vi.mock('../../../addon/frontend/src/hooks/useStatus', () => ({
  useStatus: vi.fn(),
  deriveChipInfo: vi.fn().mockImplementation((s: StatusResponse) => {
    if (!s.model.loaded || !s.database.ok) return { state: 'error', label: 'Error' }
    if (!s.mqtt.connected && !s.frigate.reachable) return { state: 'degraded', label: 'MQTT & Frigate Unreachable' }
    if (!s.mqtt.connected) return { state: 'degraded', label: 'MQTT Disconnected' }
    if (!s.frigate.reachable) return { state: 'degraded', label: 'Frigate Unreachable' }
    return { state: 'connected', label: 'Connected' }
  }),
}))

import { useStatus, deriveChipInfo } from '../../../addon/frontend/src/hooks/useStatus'
import StatusChip from '../../../addon/frontend/src/components/StatusChip'

function makeStatus(overrides: Partial<{
  mqttConnected: boolean
  frigateReachable: boolean
  modelLoaded: boolean
  dbOk: boolean
}> = {}): StatusResponse {
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
    database: { ok: dbOk, detections: 50, size_bytes: 512000 },
    uptime_seconds: 120,
    version: '0.1.0',
  }
}

function renderChip(statusData: StatusResponse | null, isLoading = false, isError = false) {
  vi.mocked(useStatus).mockReturnValue({ data: statusData ?? undefined, isLoading, isError } as any)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <StatusChip />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('StatusChip', () => {
  it('shows loading state', () => {
    renderChip(null, true)
    expect(screen.getByText('Connecting…')).toBeInTheDocument()
  })

  it('shows Connected in happy path', () => {
    renderChip(makeStatus())
    expect(screen.getByText('Connected')).toBeInTheDocument()
  })

  it('links to /connection-status', () => {
    renderChip(makeStatus())
    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', '/connection-status')
  })

  it('shows Error state when model not loaded', () => {
    renderChip(makeStatus({ modelLoaded: false }))
    expect(screen.getByText('Error')).toBeInTheDocument()
  })

  it('shows degraded state when MQTT disconnected', () => {
    renderChip(makeStatus({ mqttConnected: false }))
    expect(screen.getByText('MQTT Disconnected')).toBeInTheDocument()
  })

  it('includes aria-label mentioning MQTT issue', () => {
    renderChip(makeStatus({ mqttConnected: false }))
    const link = screen.getByRole('link')
    expect(link.getAttribute('aria-label') ?? '').toContain('MQTT')
  })

  it('password is NOT present in any rendered output', () => {
    renderChip(makeStatus())
    expect(document.body.innerHTML).not.toContain('password')
  })
})
