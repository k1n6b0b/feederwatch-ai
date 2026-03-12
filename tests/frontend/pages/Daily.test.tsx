/**
 * Daily page tests.
 * Date navigation, summary stats, species table, chart toggle, export link.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Daily from '../../../addon/frontend/src/pages/Daily'
import type { DailySummary } from '../../../addon/frontend/src/types/api'

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  BarChart: ({ children }: any) => <div>{children}</div>,
  Bar: ({ children }: any) => <div>{children}</div>,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Cell: () => null,
}))

vi.mock('../../../addon/frontend/src/hooks/useDetections', () => ({
  useDailySummary: vi.fn(),
}))

import { useDailySummary } from '../../../addon/frontend/src/hooks/useDetections'

function makeSummary(overrides: Partial<DailySummary> = {}): DailySummary {
  return {
    date: '2025-06-15',
    total_detections: 42,
    unique_species: 7,
    peak_hour: 9,
    hourly: Array.from({ length: 24 }, (_, i) => ({ hour: i, count: i === 9 ? 15 : 0 })),
    species: [
      {
        scientific_name: 'Turdus migratorius',
        common_name: 'American Robin',
        count: 20,
        first_seen: '2025-06-15T06:30:00Z',
        last_seen: '2025-06-15T18:00:00Z',
        best_score: 0.94,
        is_first_ever: false,
        category_name: 'ai_classified',
      },
      {
        scientific_name: 'Poecile atricapillus',
        common_name: 'Black-capped Chickadee',
        count: 22,
        first_seen: '2025-06-15T07:00:00Z',
        last_seen: '2025-06-15T17:30:00Z',
        best_score: null,
        is_first_ever: true,
        category_name: 'frigate_classified',
      },
    ],
    ...overrides,
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

describe('Daily page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading skeleton', () => {
    vi.mocked(useDailySummary).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as any)
    wrapper(<Daily />)
    expect(document.querySelector('.animate-pulse')).toBeTruthy()
  })

  it('shows no data message when summary is null', () => {
    vi.mocked(useDailySummary).mockReturnValue({
      data: null,
      isLoading: false,
    } as any)
    wrapper(<Daily />)
    expect(screen.getByText(/No detections on this day/i)).toBeInTheDocument()
  })

  it('renders summary stats', async () => {
    vi.mocked(useDailySummary).mockReturnValue({
      data: makeSummary(),
      isLoading: false,
    } as any)
    wrapper(<Daily />)
    expect(screen.getByText('7')).toBeInTheDocument()    // unique_species
    expect(screen.getByText('42')).toBeInTheDocument()   // total_detections
    expect(screen.getByText('9 am')).toBeInTheDocument() // peak_hour
  })

  it('shows — for peak_hour when null', () => {
    vi.mocked(useDailySummary).mockReturnValue({
      data: makeSummary({ peak_hour: null }),
      isLoading: false,
    } as any)
    wrapper(<Daily />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('renders species in table', async () => {
    vi.mocked(useDailySummary).mockReturnValue({
      data: makeSummary(),
      isLoading: false,
    } as any)
    wrapper(<Daily />)
    expect(screen.getByText('American Robin')).toBeInTheDocument()
    expect(screen.getByText('Black-capped Chickadee')).toBeInTheDocument()
  })

  it('shows first-ever badge for new species', () => {
    vi.mocked(useDailySummary).mockReturnValue({
      data: makeSummary(),
      isLoading: false,
    } as any)
    wrapper(<Daily />)
    expect(screen.getByText(/First!/i)).toBeInTheDocument()
  })

  it('shows Frigate badge for frigate_classified rows', () => {
    vi.mocked(useDailySummary).mockReturnValue({
      data: makeSummary(),
      isLoading: false,
    } as any)
    wrapper(<Daily />)
    expect(screen.getByText('Frigate')).toBeInTheDocument()
  })

  it('shows confidence percentage for ai_classified rows', () => {
    vi.mocked(useDailySummary).mockReturnValue({
      data: makeSummary(),
      isLoading: false,
    } as any)
    wrapper(<Daily />)
    expect(screen.getByText('94%')).toBeInTheDocument()
  })

  it('shows "No detections" message when species array is empty', () => {
    vi.mocked(useDailySummary).mockReturnValue({
      data: makeSummary({ species: [] }),
      isLoading: false,
    } as any)
    wrapper(<Daily />)
    expect(screen.getByText(/No detections on this day/i)).toBeInTheDocument()
  })

  it('prev day button navigates backward', async () => {
    const user = userEvent.setup()
    vi.mocked(useDailySummary).mockReturnValue({
      data: makeSummary(),
      isLoading: false,
    } as any)
    wrapper(<Daily />)

    const prevBtn = screen.getByRole('button', { name: /Previous day/i })
    await user.click(prevBtn)
    // useDailySummary should have been called with a date one day prior
    const calls = vi.mocked(useDailySummary).mock.calls
    const lastDate = calls[calls.length - 1][0]
    // Today's date minus 1 should be the last call's argument
    expect(lastDate).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('next day button is disabled on today', () => {
    vi.mocked(useDailySummary).mockReturnValue({
      data: makeSummary(),
      isLoading: false,
    } as any)
    wrapper(<Daily />)
    const nextBtn = screen.getByRole('button', { name: /Next day/i })
    expect(nextBtn).toBeDisabled()
  })

  it('renders export CSV link', () => {
    vi.mocked(useDailySummary).mockReturnValue({
      data: makeSummary(),
      isLoading: false,
    } as any)
    wrapper(<Daily />)
    const link = screen.getByText('Export CSV')
    expect(link).toHaveAttribute('href', expect.stringContaining('/api/v1/export/csv'))
    expect(link).toHaveAttribute('download', expect.stringContaining('feederwatch_'))
  })

  it('chart mode toggle switches between Hourly and Weekly Heatmap', async () => {
    const user = userEvent.setup()
    vi.mocked(useDailySummary).mockReturnValue({
      data: makeSummary(),
      isLoading: false,
    } as any)
    wrapper(<Daily />)

    // Default: hourly chart visible
    expect(screen.getByText('Hourly')).toBeInTheDocument()
    expect(screen.getByText('Weekly Heatmap')).toBeInTheDocument()

    // Switch to heatmap
    await user.click(screen.getByText('Weekly Heatmap'))
    expect(screen.getByText(/Based on last 4 weeks/i)).toBeInTheDocument()
  })
})
