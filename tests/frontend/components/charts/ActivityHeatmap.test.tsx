/**
 * ActivityHeatmap — 7-day × 24-hour grid, opacity encodes activity level.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ActivityHeatmap } from '../../../../addon/frontend/src/components/charts/ActivityHeatmap'

describe('ActivityHeatmap', () => {
  it('renders all day labels', () => {
    render(<ActivityHeatmap cells={[]} />)
    for (const day of ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']) {
      expect(screen.getByText(day)).toBeInTheDocument()
    }
  })

  it('renders legend labels', () => {
    render(<ActivityHeatmap cells={[]} />)
    expect(screen.getByText('Less')).toBeInTheDocument()
    expect(screen.getByText('More')).toBeInTheDocument()
  })

  it('renders 7 × 24 = 168 cells', () => {
    const { container } = render(<ActivityHeatmap cells={[]} />)
    // Each cell is a div.flex-1 with h-5 (the grid squares)
    const cells = container.querySelectorAll('[title]')
    expect(cells.length).toBe(168)
  })

  it('renders with data cells without crashing', () => {
    const cells = [
      { day: 0, hour: 8, count: 5 },
      { day: 3, hour: 12, count: 20 },
      { day: 6, hour: 17, count: 1 },
    ]
    const { container } = render(<ActivityHeatmap cells={cells} />)
    expect(container).toBeTruthy()
  })

  it('shows tooltip text for a Monday 9am cell', () => {
    render(<ActivityHeatmap cells={[{ day: 1, hour: 9, count: 7 }]} />)
    const cell = document.querySelector('[title="Mon 9a: 7 detections"]')
    expect(cell).toBeTruthy()
  })

  it('handles singular "detection" label', () => {
    render(<ActivityHeatmap cells={[{ day: 2, hour: 14, count: 1 }]} />)
    const cell = document.querySelector('[title="Tue 2p: 1 detection"]')
    expect(cell).toBeTruthy()
  })
})
