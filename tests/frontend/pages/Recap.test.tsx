/**
 * Recap page tests.
 * Scroll-snap monthly story: loading, empty, intro slide, stats, top visitor,
 * new arrivals, peak time, back navigation.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Recap from '../../../addon/frontend/src/pages/Recap'
import type { MonthlyRecap } from '../../../addon/frontend/src/types/api'

vi.mock('../../../addon/frontend/src/hooks/useRecap', () => ({
  useMonthlyRecap: vi.fn(),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

import { useMonthlyRecap } from '../../../addon/frontend/src/hooks/useRecap'

function makeRecap(overrides: Partial<MonthlyRecap> = {}): MonthlyRecap {
  return {
    period: { year: 2026, month: 3, total_days: 31, days_with_detections: 22 },
    total_visits: 1034,
    unique_species: 26,
    top_species: {
      scientific_name: 'Melospiza melodia',
      common_name: 'Song Sparrow',
      count: 87,
      best_detection_id: 42,
    },
    rarest_species: {
      scientific_name: 'Passer domesticus',
      common_name: 'House Sparrow',
      count: 1,
      best_detection_id: 99,
    },
    new_species: [
      {
        scientific_name: 'Turdus migratorius',
        common_name: 'American Robin',
        first_seen: '2026-03-15T08:00:00',
        best_detection_id: 77,
      },
    ],
    peak_hour: 9,
    busiest_day: { date: '2026-03-07', count: 58 },
    featured_detection_id: 1,
    ...overrides,
  }
}

function wrapper(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/recap/2026/3']}>
        <Routes>
          <Route path="/recap/:year/:month" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Recap page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockNavigate.mockReset()
  })

  it('shows loading skeleton when data is loading', () => {
    vi.mocked(useMonthlyRecap).mockReturnValue({ data: undefined, isLoading: true } as any)
    wrapper(<Recap />)
    expect(document.querySelector('.animate-pulse')).toBeTruthy()
  })

  it('shows empty state when total_visits is 0', () => {
    vi.mocked(useMonthlyRecap).mockReturnValue({
      data: makeRecap({ total_visits: 0 }),
      isLoading: false,
    } as any)
    wrapper(<Recap />)
    expect(screen.getByText(/No detections in March 2026/i)).toBeInTheDocument()
  })

  it('renders month name and year in intro slide', () => {
    vi.mocked(useMonthlyRecap).mockReturnValue({
      data: makeRecap(),
      isLoading: false,
    } as any)
    wrapper(<Recap />)
    expect(screen.getByText('March Recap')).toBeInTheDocument()
    expect(screen.getByText('2026')).toBeInTheDocument()
  })

  it('renders total visits and species count', () => {
    vi.mocked(useMonthlyRecap).mockReturnValue({
      data: makeRecap(),
      isLoading: false,
    } as any)
    wrapper(<Recap />)
    expect(screen.getByText('1,034')).toBeInTheDocument()
    expect(screen.getByText('26')).toBeInTheDocument()
  })

  it('renders top visitor common name', () => {
    vi.mocked(useMonthlyRecap).mockReturnValue({
      data: makeRecap(),
      isLoading: false,
    } as any)
    wrapper(<Recap />)
    expect(screen.getByText('Song Sparrow')).toBeInTheDocument()
  })

  it('renders new arrivals species name', () => {
    vi.mocked(useMonthlyRecap).mockReturnValue({
      data: makeRecap(),
      isLoading: false,
    } as any)
    wrapper(<Recap />)
    expect(screen.getByText('American Robin')).toBeInTheDocument()
  })

  it('renders "No new species" message when new_species is empty', () => {
    vi.mocked(useMonthlyRecap).mockReturnValue({
      data: makeRecap({ new_species: [] }),
      isLoading: false,
    } as any)
    wrapper(<Recap />)
    expect(screen.getByText(/No new species this month/i)).toBeInTheDocument()
  })

  it('renders peak time slide', () => {
    vi.mocked(useMonthlyRecap).mockReturnValue({
      data: makeRecap(),
      isLoading: false,
    } as any)
    wrapper(<Recap />)
    expect(screen.getByText('9 am')).toBeInTheDocument()
  })

  it('back button calls navigate(-1)', async () => {
    const user = userEvent.setup()
    vi.mocked(useMonthlyRecap).mockReturnValue({
      data: makeRecap(),
      isLoading: false,
    } as any)
    wrapper(<Recap />)
    await user.click(screen.getByRole('button', { name: /Go back/i }))
    expect(mockNavigate).toHaveBeenCalledWith(-1)
  })
})
