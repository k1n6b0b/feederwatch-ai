/**
 * Feed page tests — stream badge visibility.
 * Fix 3: badge is hidden when MQTT is disconnected.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Feed from '../../../addon/frontend/src/pages/Feed'
import type { StatusResponse } from '../../../addon/frontend/src/types/api'

vi.mock('../../../addon/frontend/src/hooks/useDetectionStream', () => ({
  useDetectionStream: vi.fn(),
}))

vi.mock('../../../addon/frontend/src/hooks/useStatus', () => ({
  useStatus: vi.fn(),
}))

import { useDetectionStream } from '../../../addon/frontend/src/hooks/useDetectionStream'
import { useStatus } from '../../../addon/frontend/src/hooks/useStatus'

type StreamState = 'connecting' | 'open' | 'polling' | 'error'

function mockStream(state: StreamState = 'open') {
  vi.mocked(useDetectionStream).mockReturnValue({ detections: [], streamState: state } as any)
}

function mockStatus(mqttConnected: boolean) {
  const data: StatusResponse = {
    mqtt: { connected: mqttConnected, host: 'mqtt.local', port: 1883, authenticated: false },
    frigate: { reachable: true, url: 'http://frigate.local' },
    model: { loaded: true, labels_loaded: true, path: '/data/model.tflite', input_size: 224 },
    database: { ok: true, detections: 0, size_bytes: 0 },
    uptime_seconds: 0,
    version: '0.1.0',
    discovery: null,
  }
  vi.mocked(useStatus).mockReturnValue({ data, isLoading: false, isError: false } as any)
}

function wrapper(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Feed page — stream badge', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows ● Live badge when SSE open and MQTT connected', () => {
    mockStream('open')
    mockStatus(true)
    wrapper(<Feed />)
    expect(screen.getByText(/● Live/)).toBeInTheDocument()
  })

  it('hides ● Live badge when MQTT disconnected even if SSE is open', () => {
    mockStream('open')
    mockStatus(false)
    wrapper(<Feed />)
    expect(screen.queryByText(/● Live/)).toBeNull()
  })

  it('shows ● Polling badge when SSE polling and MQTT connected', () => {
    mockStream('polling')
    mockStatus(true)
    wrapper(<Feed />)
    expect(screen.getByText(/● Polling/)).toBeInTheDocument()
  })

  it('hides ● Polling badge when MQTT disconnected', () => {
    mockStream('polling')
    mockStatus(false)
    wrapper(<Feed />)
    expect(screen.queryByText(/● Polling/)).toBeNull()
  })

  it('shows ● Stream error badge when MQTT connected', () => {
    mockStream('error')
    mockStatus(true)
    wrapper(<Feed />)
    expect(screen.getByText(/● Stream error/)).toBeInTheDocument()
  })

  it('hides ● Stream error badge when MQTT disconnected', () => {
    mockStream('error')
    mockStatus(false)
    wrapper(<Feed />)
    expect(screen.queryByText(/● Stream error/)).toBeNull()
  })

  it('shows badge when status data is not yet loaded (optimistic default)', () => {
    mockStream('open')
    vi.mocked(useStatus).mockReturnValue({ data: undefined, isLoading: true } as any)
    wrapper(<Feed />)
    // statusData undefined → mqttConnected defaults to true → badge visible
    expect(screen.getByText(/● Live/)).toBeInTheDocument()
  })
})
