/**
 * Per-species hour-of-day bar chart.
 * "This bird is a dawn visitor" — shows when a specific species visits the feeder.
 */

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { HourlyBucket } from '../../types/api'

interface Props {
  data: HourlyBucket[]
}

function formatHour(h: number): string {
  if (h === 0)  return '12a'
  if (h < 12)  return `${h}a`
  if (h === 12) return '12p'
  return `${h - 12}p`
}

export function SpeciesTimeOfDay({ data }: Props) {
  const peakHour = data.reduce((best, d) => d.count > best.count ? d : best, data[0])

  return (
    <div className="space-y-2">
      {peakHour?.count > 0 && (
        <p className="text-xs text-slate-500">
          Peak activity at <span className="text-accent font-medium">{formatHour(peakHour.hour)}</span>
        </p>
      )}
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={data} margin={{ top: 2, right: 4, left: -24, bottom: 0 }}>
          <XAxis
            dataKey="hour"
            tickFormatter={formatHour}
            tick={{ fill: '#64748b', fontSize: 9 }}
            tickLine={false}
            axisLine={false}
            interval={2}
          />
          <YAxis
            tick={{ fill: '#64748b', fontSize: 9 }}
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
          />
          <Tooltip
            cursor={{ fill: 'rgba(255,255,255,0.05)' }}
            contentStyle={{
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '8px',
              fontSize: '11px',
              color: '#e2e8f0',
            }}
            formatter={(v: number) => [v, 'Detections']}
            labelFormatter={(h: number) => formatHour(h)}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {data.map(entry => (
              <Cell
                key={`cell-${entry.hour}`}
                fill={entry.hour === peakHour?.hour ? '#10b981' : '#334155'}
                opacity={entry.count === 0 ? 0.2 : 1}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
