/**
 * Phenology dot plot: each year on y-axis, day-of-year on x-axis.
 * Shows arrival and departure date drift year over year.
 * Scientifically meaningful — Project FeederWatch core data product.
 */

import type { PhenologyYear } from '../../types/api'

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MONTH_START_DAYS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]

interface Props {
  data: PhenologyYear[]
}

export function PhenologyCalendar({ data }: Props) {
  if (!data.length) return null

  const maxDay = 365

  function pct(day: string | number): number {
    return (Number(day) / maxDay) * 100
  }

  return (
    <div className="space-y-1">
      {/* Month axis */}
      <div className="relative h-5 ml-12">
        {MONTH_LABELS.map((label, i) => (
          <span
            key={label}
            className="absolute text-xs text-slate-600 transform -translate-x-1/2"
            style={{ left: `${pct(MONTH_START_DAYS[i])}%` }}
          >
            {label}
          </span>
        ))}
      </div>

      {/* Year rows */}
      {[...data].reverse().map(row => (
        <div key={row.year} className="flex items-center gap-2">
          <span className="text-xs text-slate-500 w-10 flex-shrink-0 text-right">
            {row.year}
          </span>
          <div className="relative flex-1 h-4 bg-surface-elevated rounded-full overflow-hidden">
            {/* Presence bar */}
            <div
              className="absolute h-full bg-accent/30 rounded-full"
              style={{
                left:  `${pct(row.first_day_of_year)}%`,
                width: `${pct(Number(row.last_day_of_year) - Number(row.first_day_of_year))}%`,
              }}
            />
            {/* First seen dot */}
            <div
              className="absolute w-2.5 h-2.5 bg-accent rounded-full top-0.5"
              style={{ left: `${pct(row.first_day_of_year)}%` }}
              title={`First: ${row.first_seen}`}
            />
            {/* Last seen dot */}
            <div
              className="absolute w-2.5 h-2.5 bg-emerald-300 rounded-full top-0.5"
              style={{ left: `${pct(row.last_day_of_year)}%` }}
              title={`Last: ${row.last_seen}`}
            />
          </div>
          <span className="text-xs text-slate-600 w-8 text-right tabular-nums">
            {row.total}
          </span>
        </div>
      ))}

      {/* Legend */}
      <div className="flex items-center gap-4 mt-2 ml-12 text-xs text-slate-600">
        <span className="flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-full bg-accent inline-block" />
          First seen
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-300 inline-block" />
          Last seen
        </span>
      </div>
    </div>
  )
}
