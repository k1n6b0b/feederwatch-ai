/**
 * SpeciesTimeOfDay — per-species hourly bar chart with peak annotation.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SpeciesTimeOfDay } from '../../../../addon/frontend/src/components/charts/SpeciesTimeOfDay'
import type { HourlyBucket } from '../../../../addon/frontend/src/types/api'

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  BarChart: ({ children }: any) => <div>{children}</div>,
  Bar: ({ children }: any) => <div>{children}</div>,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Cell: () => null,
}))

function makeData(peakHour = 7): HourlyBucket[] {
  return Array.from({ length: 24 }, (_, i) => ({
    hour: i,
    count: i === peakHour ? 12 : 0,
  }))
}

describe('SpeciesTimeOfDay', () => {
  it('renders without crashing', () => {
    const { container } = render(<SpeciesTimeOfDay data={makeData()} />)
    expect(container).toBeTruthy()
  })

  it('shows peak activity annotation when there are detections', () => {
    render(<SpeciesTimeOfDay data={makeData(7)} />)
    expect(screen.getByText(/Peak activity at/i)).toBeInTheDocument()
    // Peak at 7am should show "7a"
    expect(screen.getByText('7a')).toBeInTheDocument()
  })

  it('hides peak annotation when all counts are 0', () => {
    const noActivity: HourlyBucket[] = Array.from({ length: 24 }, (_, i) => ({ hour: i, count: 0 }))
    render(<SpeciesTimeOfDay data={noActivity} />)
    expect(screen.queryByText(/Peak activity at/i)).toBeNull()
  })
})
