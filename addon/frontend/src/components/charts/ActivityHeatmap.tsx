/**
 * Hour × day-of-week heatmap.
 * Shows weekly routine patterns — which hours on which days have highest activity.
 * Data is aggregated from multiple daily summaries passed as props.
 */

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const HOURS = Array.from({ length: 24 }, (_, i) => i)

function formatHour(h: number): string {
  if (h === 0)  return '12a'
  if (h < 12)  return `${h}a`
  if (h === 12) return '12p'
  return `${h - 12}p`
}

interface WeeklyCell {
  day: number   // 0–6
  hour: number  // 0–23
  count: number
}

interface Props {
  /** Cells pre-aggregated by the parent (Daily page fetches multiple days) */
  cells: WeeklyCell[]
}

export function ActivityHeatmap({ cells }: Props) {
  const maxCount = Math.max(...cells.map(c => c.count), 1)

  // Build lookup: day → hour → count
  const grid: number[][] = Array.from({ length: 7 }, () => Array(24).fill(0))
  for (const c of cells) {
    grid[c.day][c.hour] = c.count
  }

  function opacity(count: number): string {
    if (count === 0) return '0.08'
    return String(0.15 + (count / maxCount) * 0.85)
  }

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[600px]">
        {/* Hour axis labels */}
        <div className="flex ml-10 mb-1">
          {HOURS.filter(h => h % 3 === 0).map(h => (
            <div
              key={h}
              className="text-xs text-slate-600"
              style={{ width: `${(3 / 24) * 100}%`, textAlign: 'left' }}
            >
              {formatHour(h)}
            </div>
          ))}
        </div>

        {/* Grid */}
        {DAYS.map((day, dayIdx) => (
          <div key={day} className="flex items-center gap-1 mb-0.5">
            <span className="text-xs text-slate-500 w-9 flex-shrink-0 text-right pr-1">
              {day}
            </span>
            <div className="flex flex-1 gap-px">
              {HOURS.map(hour => {
                const count = grid[dayIdx][hour]
                return (
                  <div
                    key={hour}
                    className="flex-1 h-5 rounded-sm transition-opacity duration-150"
                    style={{
                      backgroundColor: '#10b981',
                      opacity: opacity(count),
                    }}
                    title={`${day} ${formatHour(hour)}: ${count} detection${count !== 1 ? 's' : ''}`}
                  />
                )
              })}
            </div>
          </div>
        ))}

        {/* Legend */}
        <div className="flex items-center gap-2 mt-3 justify-end">
          <span className="text-xs text-slate-600">Less</span>
          {[0.08, 0.3, 0.5, 0.7, 1.0].map(o => (
            <div
              key={o}
              className="w-3 h-3 rounded-sm"
              style={{ backgroundColor: '#10b981', opacity: o }}
            />
          ))}
          <span className="text-xs text-slate-600">More</span>
        </div>
      </div>
    </div>
  )
}
