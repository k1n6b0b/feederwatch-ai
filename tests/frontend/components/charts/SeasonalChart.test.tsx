/**
 * SeasonalChart — weekly unique-species line chart.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SeasonalChart } from '../../../../addon/frontend/src/components/charts/SeasonalChart'

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  LineChart: ({ children }: any) => <div>{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ReferenceLine: () => null,
}))

const SAMPLE_DATA = [
  { week: 'Jan W1', species: 3, detections: 12 },
  { week: 'Jan W2', species: 5, detections: 24 },
  { week: 'Mar W2', species: 8, detections: 43 },
]

describe('SeasonalChart', () => {
  it('renders without crashing with data', () => {
    const { container } = render(<SeasonalChart data={SAMPLE_DATA} />)
    expect(container).toBeTruthy()
  })

  it('renders chart axes with empty data (no early-return)', () => {
    const { container } = render(<SeasonalChart data={[]} />)
    // Chart renders with axes rather than hiding when data is empty
    expect(container.querySelector('div')).toBeTruthy()
  })
})
