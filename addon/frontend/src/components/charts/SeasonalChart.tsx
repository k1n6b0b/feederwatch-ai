/**
 * Species count by week/month for the full year.
 * Migration spikes visible in Mar–May and Aug–Nov.
 */

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

interface WeeklyPoint {
  week: string  // ISO week label e.g. "Jan W1"
  species: number
  detections: number
}

interface Props {
  data: WeeklyPoint[]
}

export function SeasonalChart({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis
          dataKey="week"
          tick={{ fill: '#64748b', fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          interval={3}
        />
        <YAxis
          tick={{ fill: '#64748b', fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '8px',
            fontSize: '12px',
            color: '#e2e8f0',
          }}
        />
        <Line
          type="monotone"
          dataKey="species"
          stroke="#10b981"
          strokeWidth={2}
          dot={false}
          name="Unique species"
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
