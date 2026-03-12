/**
 * PhenologyCalendar — dot plot of first/last detection per year.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PhenologyCalendar } from '../../../../addon/frontend/src/components/charts/PhenologyCalendar'
import type { PhenologyYear } from '../../../../addon/frontend/src/types/api'

function makeYears(): PhenologyYear[] {
  return [
    {
      year: '2023',
      first_day_of_year: '45',
      last_day_of_year: '320',
      first_seen: '2023-02-14',
      last_seen: '2023-11-16',
      total: 88,
    },
    {
      year: '2024',
      first_day_of_year: '50',
      last_day_of_year: '310',
      first_seen: '2024-02-19',
      last_seen: '2024-11-05',
      total: 102,
    },
  ]
}

describe('PhenologyCalendar', () => {
  it('renders nothing when data is empty', () => {
    const { container } = render(<PhenologyCalendar data={[]} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders month axis labels', () => {
    render(<PhenologyCalendar data={makeYears()} />)
    expect(screen.getByText('Jan')).toBeInTheDocument()
    expect(screen.getByText('Jun')).toBeInTheDocument()
    expect(screen.getByText('Dec')).toBeInTheDocument()
  })

  it('renders a row for each year', () => {
    render(<PhenologyCalendar data={makeYears()} />)
    expect(screen.getByText('2023')).toBeInTheDocument()
    expect(screen.getByText('2024')).toBeInTheDocument()
  })

  it('renders detection totals', () => {
    render(<PhenologyCalendar data={makeYears()} />)
    expect(screen.getByText('88')).toBeInTheDocument()
    expect(screen.getByText('102')).toBeInTheDocument()
  })

  it('renders legend', () => {
    render(<PhenologyCalendar data={makeYears()} />)
    expect(screen.getByText('First seen')).toBeInTheDocument()
    expect(screen.getByText('Last seen')).toBeInTheDocument()
  })

  it('renders most recent year first (reversed)', () => {
    render(<PhenologyCalendar data={makeYears()} />)
    const yearEls = screen.getAllByText(/^202[0-9]$/)
    // Reversed: 2024 first, 2023 second
    expect(yearEls[0]).toHaveTextContent('2024')
    expect(yearEls[1]).toHaveTextContent('2023')
  })
})
