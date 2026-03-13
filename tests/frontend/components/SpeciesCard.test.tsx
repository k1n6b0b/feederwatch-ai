/**
 * SpeciesCard — snapshot image error handling.
 * Shows feather placeholder when best_detection_id is null or snapshot 404s.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import SpeciesCard from '../../../addon/frontend/src/components/SpeciesCard'
import type { Species } from '../../../addon/frontend/src/types/api'

vi.mock('../../../addon/frontend/src/api/client', () => ({
  detections: {
    snapshotUrl: (id: number) => `/api/v1/detections/${id}/snapshot`,
  },
}))

function makeSpecies(overrides: Partial<Species> = {}): Species {
  return {
    scientific_name: 'Poecile atricapillus',
    common_name: 'Black-capped Chickadee',
    total_detections: 5,
    best_score: 0.95,
    first_seen: '2026-03-01T08:00:00',
    last_seen: '2026-03-13T09:00:00',
    best_detection_id: 42,
    best_snapshot_path: '/data/snapshots/42.jpg',
    ...overrides,
  }
}

describe('SpeciesCard', () => {
  it('renders the img when best_detection_id is set', () => {
    const { container } = render(
      <SpeciesCard species={makeSpecies()} isNewToday={false} onClick={vi.fn()} />
    )
    const img = container.querySelector('img')
    expect(img).not.toBeNull()
    expect(img!.src).toContain('/api/v1/detections/42/snapshot')
  })

  it('shows feather placeholder when best_detection_id is null', () => {
    render(
      <SpeciesCard
        species={makeSpecies({ best_detection_id: null, best_snapshot_path: null })}
        isNewToday={false}
        onClick={vi.fn()}
      />
    )
    expect(screen.getByText('🪶')).toBeInTheDocument()
  })

  it('shows feather placeholder when snapshot 404s', () => {
    const { container } = render(
      <SpeciesCard species={makeSpecies()} isNewToday={false} onClick={vi.fn()} />
    )
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('🪶')).toBeInTheDocument()
  })
})
