import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useStatus, deriveChipInfo } from '../hooks/useStatus'

const STATE_STYLES = {
  connected: {
    dot: 'bg-status-connected',
    text: 'text-status-connected',
    ring: 'ring-status-connected/20',
    bg:   'hover:bg-status-connected/10',
  },
  degraded: {
    dot: 'bg-status-degraded animate-pulse',
    text: 'text-status-degraded',
    ring: 'ring-status-degraded/20',
    bg:   'hover:bg-status-degraded/10',
  },
  error: {
    dot: 'bg-status-error animate-pulse',
    text: 'text-status-error',
    ring: 'ring-status-error/20',
    bg:   'hover:bg-status-error/10',
  },
}

export default function StatusChip() {
  const { data, isLoading, isError } = useStatus()
  const location = useLocation()
  const isActive = location.pathname === '/connection-status'

  const chipInfo = isError || !data
    ? { state: 'error' as const, label: 'Error' }
    : !isLoading ? deriveChipInfo(data) : { state: 'connected' as const, label: 'Connecting…' }

  const [faded, setFaded] = useState(false)
  useEffect(() => {
    if (chipInfo.state !== 'connected') { setFaded(false); return }
    const t = setTimeout(() => setFaded(true), 5000)
    return () => clearTimeout(t)
  }, [chipInfo.state])

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm text-slate-500">
        <span className="w-2 h-2 rounded-full bg-slate-600 animate-pulse" />
        <span>Connecting…</span>
      </div>
    )
  }

  const styles = STATE_STYLES[chipInfo.state]

  // Build tooltip from degraded services
  let tooltip = ''
  if (data && chipInfo.state !== 'connected') {
    const issues: string[] = []
    if (!data.mqtt.connected)    issues.push('MQTT disconnected')
    if (!data.frigate.reachable) issues.push('Frigate unreachable')
    if (!data.model.loaded)      issues.push('Model not loaded')
    if (!data.database.ok)       issues.push('Database error')
    tooltip = issues.join(' · ')
  }

  return (
    <Link
      to="/connection-status"
      title={tooltip || 'View system status'}
      aria-label={`System status: ${chipInfo.label}${tooltip ? ` — ${tooltip}` : ''}`}
      className={[
        'flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium',
        'ring-1 transition-all duration-500',
        styles.text,
        styles.ring,
        styles.bg,
        isActive ? 'ring-2' : '',
        faded ? 'opacity-[0.15] hover:opacity-100' : '',
      ].join(' ')}
    >
      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${styles.dot}`} />
      <span>{chipInfo.label}</span>
    </Link>
  )
}
