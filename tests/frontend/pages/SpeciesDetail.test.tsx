/**
 * SpeciesDetail — snapshot image error handling.
 * HeroImage must hide entirely on 404; GridPhoto must show feather placeholder.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { HeroImage, GridPhoto } from '../../../addon/frontend/src/pages/SpeciesDetail'
import type { Detection } from '../../../addon/frontend/src/types/api'

vi.mock('../../../addon/frontend/src/api/client', () => ({
  detections: {
    snapshotUrl: (id: number) => `/api/v1/detections/${id}/snapshot`,
  },
}))

function makeDetection(overrides: Partial<Detection> = {}): Detection {
  return {
    id: 1,
    frigate_event_id: 'evt-001',
    scientific_name: 'Corvus brachyrhynchos',
    common_name: 'American Crow',
    score: 0.81,
    category_name: 'ai_classified',
    camera_name: 'birdcam',
    snapshot_path: null,
    detected_at: '2026-03-11T15:00:00',
    is_first_ever: false,
    ...overrides,
  }
}

describe('HeroImage', () => {
  it('renders the img when no error', () => {
    const { container } = render(<HeroImage detectionId={42} altText="American Crow" />)
    const img = container.querySelector('img')
    expect(img).not.toBeNull()
    expect(img!.src).toContain('/api/v1/detections/42/snapshot')
  })

  it('hides entirely when the image 404s', () => {
    const { container } = render(<HeroImage detectionId={42} altText="American Crow" />)
    const img = container.querySelector('img')!
    fireEvent.error(img)
    // Container should be empty — no img, no fallback element
    expect(container.firstChild).toBeNull()
  })
})

describe('GridPhoto', () => {
  it('renders the img when no error', () => {
    const detection = makeDetection({ id: 7 })
    const { container } = render(
      <GridPhoto detection={detection} altText="American Crow photo" onClick={vi.fn()} />
    )
    const img = container.querySelector('img')
    expect(img).not.toBeNull()
    expect(img!.src).toContain('/api/v1/detections/7/snapshot')
  })

  it('shows feather placeholder when image 404s', () => {
    const detection = makeDetection({ id: 7 })
    const { container } = render(
      <GridPhoto detection={detection} altText="American Crow photo" onClick={vi.fn()} />
    )
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('🪶')).toBeTruthy()
  })

  it('button remains clickable after image 404', () => {
    const onClick = vi.fn()
    const detection = makeDetection({ id: 7 })
    const { container } = render(
      <GridPhoto detection={detection} altText="American Crow photo" onClick={onClick} />
    )
    fireEvent.error(container.querySelector('img')!)
    fireEvent.click(container.querySelector('button')!)
    expect(onClick).toHaveBeenCalledOnce()
  })
})
