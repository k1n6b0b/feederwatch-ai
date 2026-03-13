/**
 * DetectionCard component tests.
 * Renders detection metadata, confidence bar, Frigate badge, first-ever badge.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import DetectionCard from '../../../addon/frontend/src/components/DetectionCard'
import type { Detection } from '../../../addon/frontend/src/types/api'

// Suppress the status fetch from DetectionCard
vi.mock('../../../addon/frontend/src/hooks/useStatus', () => ({
  useStatus: () => ({ data: null, isLoading: false, isError: false }),
  deriveChipInfo: vi.fn(),
}))

function makeDetection(overrides: Partial<Detection> = {}): Detection {
  return {
    id: 1,
    frigate_event_id: 'evt-abc',
    scientific_name: 'Turdus migratorius',
    common_name: 'American Robin',
    score: 0.92,
    category_name: 'ai_classified',
    camera_name: 'front_yard',
    snapshot_path: '/data/snapshots/1.jpg',
    detected_at: new Date(Date.now() - 30_000).toISOString(),
    is_first_ever: false,
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

describe('DetectionCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders common name and scientific name', () => {
    wrapper(<DetectionCard detection={makeDetection()} />)
    expect(screen.getByText('American Robin')).toBeInTheDocument()
    expect(screen.getByText('Turdus migratorius')).toBeInTheDocument()
  })

  it('renders camera badge', () => {
    wrapper(<DetectionCard detection={makeDetection()} />)
    expect(screen.getByText('front_yard')).toBeInTheDocument()
  })

  it('does not render ConfidenceBar (removed in B8)', () => {
    wrapper(<DetectionCard detection={makeDetection({ score: 0.92 })} />)
    // Score is shown in modal, not on the card itself
    expect(screen.queryByRole('progressbar')).toBeNull()
    // No percentage text on card face
    expect(screen.queryByText('92%')).toBeNull()
  })

  it('does not render Frigate badge on card (removed in B9)', () => {
    wrapper(<DetectionCard detection={makeDetection({
      category_name: 'frigate_classified',
      score: null,
    })} />)
    expect(screen.queryByText('Frigate')).toBeNull()
  })

  it('does not render amber dot for frigate_classified detections (removed in B11)', () => {
    const { container } = wrapper(<DetectionCard detection={makeDetection({
      category_name: 'frigate_classified',
      score: null,
    })} />)
    // Amber dot was: <span class="...bg-amber-400..." title="Frigate sublabel classification">
    expect(container.querySelector('[title="Frigate sublabel classification"]')).toBeNull()
  })

  it('accepts onRemove prop without error', () => {
    const onRemove = vi.fn()
    // Verifies the prop interface: component renders cleanly when onRemove is provided
    wrapper(<DetectionCard detection={makeDetection()} onRemove={onRemove} />)
    expect(screen.getByText('American Robin')).toBeInTheDocument()
  })

  it('renders first-ever badge when is_first_ever=true', () => {
    wrapper(<DetectionCard detection={makeDetection({ is_first_ever: true })} />)
    expect(screen.getByText(/First ever/i)).toBeInTheDocument()
  })

  it('does not render first-ever badge when is_first_ever=false', () => {
    wrapper(<DetectionCard detection={makeDetection({ is_first_ever: false })} />)
    expect(screen.queryByText(/First ever/i)).toBeNull()
  })

  it('opens modal on click', async () => {
    const user = userEvent.setup()
    wrapper(<DetectionCard detection={makeDetection()} />)
    const card = screen.getByRole('button', { name: /American Robin detection/i })
    await user.click(card)
    // Modal renders common name in it too
    expect(screen.getAllByText('American Robin').length).toBeGreaterThan(1)
  })

  it('renders relative timestamp', () => {
    wrapper(<DetectionCard detection={makeDetection()} />)
    // 30s ago detection should show seconds
    expect(screen.getByText(/s ago/)).toBeInTheDocument()
  })

  it('shows feather placeholder when snapshot 404s', () => {
    const { container } = wrapper(<DetectionCard detection={makeDetection()} />)
    const img = container.querySelector('img')!
    fireEvent.error(img)
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('🪶')).toBeInTheDocument()
  })
})
