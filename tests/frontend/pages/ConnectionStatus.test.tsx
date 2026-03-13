/**
 * ConnectionStatus page tests.
 * Verifies: status section renders, ring buffer table, loading state, error state.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ConnectionStatus from '../../../addon/frontend/src/pages/ConnectionStatus'
import type { StatusResponse, MqttRingEntry } from '../../../addon/frontend/src/types/api'

// Mock API client
vi.mock('../../../addon/frontend/src/api/client', async () => {
  const actual = await vi.importActual<typeof import('../../../addon/frontend/src/api/client')>(
    '../../../addon/frontend/src/api/client'
  )
  return {
    ...actual,
    status: { get: vi.fn() },
    events: { recent: vi.fn() },
  }
})

import { status as statusApi, events as eventsApi } from '../../../addon/frontend/src/api/client'

function makeStatus(overrides: Partial<StatusResponse> = {}): StatusResponse {
  return {
    mqtt: { connected: true, host: 'mqtt.local', port: 1883, authenticated: true },
    frigate: { reachable: true, api_url: 'http://frigate.local:5000', clips_ui_url: 'http://frigate.local:5000' },
    model: { loaded: true, labels_loaded: true, path: '/data/model.tflite', input_size: 224 },
    database: { ok: true, detections: 1234, size_bytes: 2 * 1024 * 1024 },
    uptime_seconds: 7380,
    version: '0.1.0',
    discovery: null,
    ...overrides,
  }
}

function makeRingEntry(action: MqttRingEntry['action'] = 'saved_ai'): MqttRingEntry {
  return {
    timestamp: new Date(Date.now() - 5000).toISOString(),
    camera: 'front_yard',
    frigate_event_id: 'evt-test-001',
    our_score: 0.87,
    threshold: 0.7,
    action,
  }
}

function wrapper(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ConnectionStatus page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page heading', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus())
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    expect(screen.getByText('Connection Status')).toBeInTheDocument()
  })

  it('shows loading skeleton before data resolves', () => {
    vi.mocked(statusApi.get).mockReturnValue(new Promise(() => {}))
    vi.mocked(eventsApi.recent).mockReturnValue(new Promise(() => {}))
    wrapper(<ConnectionStatus />)
    expect(document.querySelector('.animate-pulse')).toBeTruthy()
  })

  it('shows all 4 service rows after data loads', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus())
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => {
      expect(screen.getByText('MQTT')).toBeInTheDocument()
      expect(screen.getByText('Frigate')).toBeInTheDocument()
      expect(screen.getByText('AI Model')).toBeInTheDocument()
      expect(screen.getByText('Database')).toBeInTheDocument()
    })
  })

  it('shows OK for all services in healthy state', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus())
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => {
      // MQTT + Frigate + Database = 3× "OK", AI Model = "Loaded"
      expect(screen.getAllByText('OK').length).toBe(3)
      expect(screen.getByText('Loaded')).toBeInTheDocument()
    })
  })

  it('shows DOWN for MQTT when disconnected', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus({
      mqtt: { connected: false, host: 'mqtt.local', port: 1883, authenticated: false },
    }))
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => {
      expect(screen.getByText('DOWN')).toBeInTheDocument()
    })
  })

  it('shows MQTT host:port in detail', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus())
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => {
      expect(screen.getByText(/mqtt\.local:1883/i)).toBeInTheDocument()
    })
  })

  it('shows uptime and version', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus({ uptime_seconds: 7380, version: '0.1.0' }))
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => {
      expect(screen.getByText(/0\.1\.0/)).toBeInTheDocument()
      // 7380s = 2h 3m
      expect(screen.getByText(/2h 3m/)).toBeInTheDocument()
    })
  })

  it('shows detection count and db size', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus())
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => {
      expect(screen.getByText(/1,234 detections/)).toBeInTheDocument()
      expect(screen.getByText(/2\.0 MB/)).toBeInTheDocument()
    })
  })

  it('shows empty ring buffer message', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus())
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => {
      expect(screen.getByText(/No MQTT events recorded yet/i)).toBeInTheDocument()
    })
  })

  it('shows ring buffer entries in table', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus())
    vi.mocked(eventsApi.recent).mockResolvedValue([makeRingEntry('saved_ai')])
    wrapper(<ConnectionStatus />)
    await waitFor(() => {
      expect(screen.getByText('front_yard')).toBeInTheDocument()
      expect(screen.getByText('AI saved')).toBeInTheDocument()
      expect(screen.getByText('87%')).toBeInTheDocument()
      expect(screen.getByText('70%')).toBeInTheDocument()
    })
  })

  it('shows all action types in ring buffer', async () => {
    const entries: MqttRingEntry[] = [
      makeRingEntry('saved_ai'),
      makeRingEntry('saved_frigate'),
      makeRingEntry('below_threshold'),
      makeRingEntry('no_bird'),
      makeRingEntry('error'),
    ]
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus())
    vi.mocked(eventsApi.recent).mockResolvedValue(entries)
    wrapper(<ConnectionStatus />)
    await waitFor(() => {
      expect(screen.getByText('AI saved')).toBeInTheDocument()
      expect(screen.getByText('Frigate saved')).toBeInTheDocument()
      expect(screen.getByText('Below threshold')).toBeInTheDocument()
      expect(screen.getByText('No bird')).toBeInTheDocument()
      expect(screen.getByText('Error')).toBeInTheDocument()
    })
  })

  it('shows — for null score in ring buffer', async () => {
    const entry = makeRingEntry('no_bird')
    entry.our_score = null
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus())
    vi.mocked(eventsApi.recent).mockResolvedValue([entry])
    wrapper(<ConnectionStatus />)
    await waitFor(() => {
      expect(screen.getByText('—')).toBeInTheDocument()
    })
  })

  it('password is absent from all rendered output', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus())
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => screen.getByText('Connection Status'))
    expect(document.body.innerHTML).not.toMatch(/password/i)
  })

  // Fix 1: duplicate chip label removed from card header
  it('does not render chip label text in the status card', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus({
      mqtt: { connected: false, host: 'mqtt.local', port: 1883, authenticated: false },
      frigate: { reachable: false, api_url: 'http://frigate.local:5000', clips_ui_url: 'http://frigate.local:5000' },
    }))
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => screen.getByText('MQTT'))
    // "MQTT & Frigate Unreachable" is the chip label — must NOT appear in page body
    expect(screen.queryByText('MQTT & Frigate Unreachable')).toBeNull()
  })

  it('does not render "Connected" chip label in the status card', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus())
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => screen.getByText('MQTT'))
    expect(screen.queryByText('Connected')).toBeNull()
  })

  // Fix 5: discovery hints
  it('shows discovery hint when MQTT down and Supervisor found broker elsewhere', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus({
      mqtt: { connected: false, host: 'wrong-host', port: 9999, authenticated: false },
      discovery: {
        mqtt: { host: 'core-mosquitto', port: 1883, username: null, ssl: false },
        frigate_url: null,
      },
    }))
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => {
      expect(screen.getByText(/Detected at core-mosquitto:1883/)).toBeInTheDocument()
    })
  })

  it('shows no discovery hint when MQTT is connected even if discovery data is present', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus({
      mqtt: { connected: true, host: 'core-mosquitto', port: 1883, authenticated: true },
      discovery: {
        mqtt: { host: 'core-mosquitto', port: 1883, username: null, ssl: false },
        frigate_url: null,
      },
    }))
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => screen.getByText('MQTT'))
    expect(screen.queryByText(/Detected at/)).toBeNull()
  })

  it('shows Frigate discovery hint when Frigate unreachable and Supervisor found it', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus({
      frigate: { reachable: false, api_url: 'http://wrong:5000', clips_ui_url: 'http://wrong:5000' },
      discovery: {
        mqtt: null,
        frigate_url: 'http://ccab4aaf-frigate:5000',
      },
    }))
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => {
      expect(screen.getByText(/Detected at http:\/\/ccab4aaf-frigate:5000/)).toBeInTheDocument()
    })
  })

  it('shows no hint when discovery is null', async () => {
    vi.mocked(statusApi.get).mockResolvedValue(makeStatus({
      mqtt: { connected: false, host: 'mqtt.local', port: 1883, authenticated: false },
      discovery: null,
    }))
    vi.mocked(eventsApi.recent).mockResolvedValue([])
    wrapper(<ConnectionStatus />)
    await waitFor(() => screen.getByText('MQTT'))
    expect(screen.queryByText(/Detected at/)).toBeNull()
  })
})
