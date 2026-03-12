/**
 * HourlyActivityChart — renders bars for each hour, highlights peak.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { HourlyActivityChart } from '../../../../addon/frontend/src/components/charts/HourlyActivityChart'
import type { HourlyBucket } from '../../../../addon/frontend/src/types/api'

// Recharts uses SVG; jsdom renders it but we test accessible/text content.
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="chart">{children}</div>,
  BarChart: ({ children }: any) => <div>{children}</div>,
  Bar: ({ children }: any) => <div>{children}</div>,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Cell: () => null,
}))

function makeHourly(): HourlyBucket[] {
  return Array.from({ length: 24 }, (_, i) => ({
    hour: i,
    count: i === 9 ? 15 : i === 10 ? 8 : 0,
  }))
}

describe('HourlyActivityChart', () => {
  it('renders without crashing', () => {
    const { container } = render(
      <HourlyActivityChart data={makeHourly()} peakHour={9} />
    )
    expect(container).toBeTruthy()
  })

  it('shows chart container', () => {
    render(<HourlyActivityChart data={makeHourly()} peakHour={9} />)
    expect(screen.getByTestId('chart')).toBeInTheDocument()
  })

  it('renders with no data without crashing', () => {
    const emptyData: HourlyBucket[] = Array.from({ length: 24 }, (_, i) => ({ hour: i, count: 0 }))
    const { container } = render(
      <HourlyActivityChart data={emptyData} peakHour={null} />
    )
    expect(container).toBeTruthy()
  })
})
