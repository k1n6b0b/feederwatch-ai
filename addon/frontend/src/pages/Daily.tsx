import { useState, useRef } from 'react'
import { useDailySummary } from '../hooks/useDetections'
import { HourlyActivityChart } from '../components/charts/HourlyActivityChart'
import { ActivityHeatmap } from '../components/charts/ActivityHeatmap'
import { exportApi } from '../api/client'

type ChartMode = 'hourly' | 'heatmap'

function todayString(): string {
  return new Date().toISOString().slice(0, 10)
}

function offsetDate(dateStr: string, days: number): string {
  const d = new Date(dateStr)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

function formatDisplayDate(dateStr: string): string {
  return new Date(dateStr + 'T12:00:00').toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  })
}

export default function Daily() {
  const [date, setDate] = useState(todayString())
  const [chartMode, setChartMode] = useState<ChartMode>('hourly')
  const { data: summary, isLoading } = useDailySummary(date)
  const dateInputRef = useRef<HTMLInputElement>(null)

  const isToday = date === todayString()
  const canGoForward = !isToday
  const hasDetections = summary != null && summary.total_detections > 0

  return (
    <div className="space-y-4">
      {/* Date navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setDate(d => offsetDate(d, -1))}
            className="btn-ghost px-2"
            aria-label="Previous day"
          >
            ◀
          </button>
          <button
            onClick={() => dateInputRef.current?.showPicker()}
            className="text-base font-medium text-slate-200 hover:text-emerald-400 transition-colors"
            aria-label="Pick a date"
          >
            {formatDisplayDate(date)}
          </button>
          <input
            ref={dateInputRef}
            type="date"
            className="sr-only"
            value={date}
            max={todayString()}
            onChange={e => e.target.value && setDate(e.target.value)}
          />
          <button
            onClick={() => setDate(d => offsetDate(d, 1))}
            disabled={!canGoForward}
            className="btn-ghost px-2 disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="Next day"
          >
            ▶
          </button>
        </div>
        {hasDetections ? (
          <a
            href={exportApi.csvUrl(date)}
            download={`feederwatch_${date}.csv`}
            className="btn-ghost text-sm"
          >
            Export CSV
          </a>
        ) : (
          <span
            className="btn-ghost text-sm opacity-40 cursor-not-allowed select-none"
            title="No detections to export"
          >
            Export CSV
          </span>
        )}
      </div>

      {isLoading ? (
        <LoadingSkeleton />
      ) : !summary ? (
        <div className="text-slate-500 text-sm py-8 text-center">
          No detections on this day. Use ◄ ► or click the date to jump.
        </div>
      ) : (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-3 gap-3">
            <StatCard label="Unique species" value={summary.unique_species} />
            <StatCard label="Total detections" value={summary.total_detections} />
            <StatCard
              label="Peak hour"
              value={summary.peak_hour !== null
                ? formatHour(summary.peak_hour)
                : '—'}
            />
          </div>

          {/* Chart */}
          <div className="card p-4">
            {/* Chart mode toggle */}
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-slate-300">Activity</h2>
              <div className="flex rounded-lg bg-surface-elevated overflow-hidden text-xs">
                <button
                  onClick={() => setChartMode('hourly')}
                  className={`px-3 py-1.5 transition-colors ${
                    chartMode === 'hourly'
                      ? 'bg-accent text-white'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Hourly
                </button>
                <button
                  onClick={() => setChartMode('heatmap')}
                  className={`px-3 py-1.5 transition-colors ${
                    chartMode === 'heatmap'
                      ? 'bg-accent text-white'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Weekly Heatmap
                </button>
              </div>
            </div>

            {chartMode === 'hourly' ? (
              <HourlyActivityChart data={summary.hourly} peakHour={summary.peak_hour} />
            ) : (
              <div className="text-xs text-slate-500 mb-2">
                Based on last 4 weeks of data
              </div>
            )}
            {chartMode === 'heatmap' && (
              <ActivityHeatmap cells={[]} />
            )}
          </div>

          {/* Species table */}
          {summary.species.length > 0 && (
            <div className="card overflow-hidden">
              <div className="px-4 py-3 border-b border-surface-elevated">
                <h2 className="text-sm font-medium text-slate-300">Species</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-slate-500 border-b border-surface-elevated">
                      <th className="text-left px-4 py-2 font-medium">Species</th>
                      <th className="text-right px-4 py-2 font-medium">Count</th>
                      <th className="text-right px-4 py-2 font-medium hidden sm:table-cell">First seen</th>
                      <th className="text-right px-4 py-2 font-medium hidden sm:table-cell">Last seen</th>
                      <th className="text-right px-4 py-2 font-medium">Best score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.species.map(s => (
                      <tr
                        key={s.scientific_name}
                        className="border-b border-surface-elevated/50 hover:bg-surface-card/50 transition-colors"
                      >
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <span className="text-slate-200">{s.common_name}</span>
                            {s.is_first_ever && (
                              <span className="badge badge-new text-xs">⭐ First!</span>
                            )}
                          </div>
                          <div className="text-xs text-slate-500 italic">{s.scientific_name}</div>
                        </td>
                        <td className="px-4 py-2.5 text-right text-slate-200 tabular-nums">
                          {s.count}
                        </td>
                        <td className="px-4 py-2.5 text-right text-slate-500 tabular-nums hidden sm:table-cell">
                          {new Date(s.first_seen).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td className="px-4 py-2.5 text-right text-slate-500 tabular-nums hidden sm:table-cell">
                          {new Date(s.last_seen).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums">
                          {s.category_name === 'frigate_classified'
                            ? <span className="badge badge-frigate">Frigate</span>
                            : s.best_score !== null
                              ? <span className="text-slate-400">{Math.round(s.best_score * 100)}%</span>
                              : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {summary.species.length === 0 && (
            <div className="text-center py-12 text-slate-600 text-sm">
              No detections on this day. Use ◄ ► or click the date to jump.
            </div>
          )}
        </>
      )}
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card p-3 text-center">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-xl font-semibold text-slate-200 mt-0.5">{value}</p>
    </div>
  )
}

function formatHour(h: number): string {
  if (h === 0)  return '12 am'
  if (h < 12)  return `${h} am`
  if (h === 12) return '12 pm'
  return `${h - 12} pm`
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="grid grid-cols-3 gap-3">
        {[1, 2, 3].map(i => (
          <div key={i} className="card p-3 h-16 bg-surface-card" />
        ))}
      </div>
      <div className="card h-48 bg-surface-card" />
    </div>
  )
}
