import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { HourlyBucket } from '../../types/api'

interface Props {
  data: HourlyBucket[]
  peakHour?: number | null
}

function formatHour(hour: number): string {
  if (hour === 0)  return '12a'
  if (hour < 12)   return `${hour}a`
  if (hour === 12) return '12p'
  return `${hour - 12}p`
}

export function HourlyActivityChart({ data, peakHour }: Props) {
  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis
          dataKey="hour"
          tickFormatter={formatHour}
          tick={{ fill: '#64748b', fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          interval={2}
        />
        <YAxis
          tick={{ fill: '#64748b', fontSize: 10 }}
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
            fontSize: '12px',
            color: '#e2e8f0',
          }}
          formatter={(value: number) => [value, 'Detections']}
          labelFormatter={(hour: number) => `${formatHour(hour)} — ${formatHour(hour + 1)}`}
        />
        <Bar dataKey="count" radius={[3, 3, 0, 0]}>
          {data.map((entry) => (
            <Cell
              key={`cell-${entry.hour}`}
              fill={entry.hour === peakHour ? '#10b981' : '#334155'}
              opacity={entry.count === 0 ? 0.3 : 1}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
