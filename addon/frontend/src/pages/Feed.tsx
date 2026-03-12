import { useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useDetectionStream } from '../hooks/useDetectionStream'
import { useStatus } from '../hooks/useStatus'
import DetectionCard from '../components/DetectionCard'

const COLUMNS = 3
const CARD_HEIGHT = 280 // approximate px per row

export default function Feed() {
  const { detections, streamState } = useDetectionStream()
  const { data: statusData } = useStatus()
  const parentRef = useRef<HTMLDivElement>(null)

  // Group detections into rows of COLUMNS for virtualizer
  const rows: typeof detections[] = []
  for (let i = 0; i < detections.length; i += COLUMNS) {
    rows.push(detections.slice(i, i + COLUMNS))
  }

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => CARD_HEIGHT,
    overscan: 3,
  })

  const mqttConnected = statusData?.mqtt.connected ?? true
  const streamBadge = mqttConnected ? {
    connecting: null,
    open:       <span className="text-xs text-accent">● Live</span>,
    polling:    <span className="text-xs text-amber-400">● Polling (10s)</span>,
    error:      <span className="text-xs text-red-400">● Stream error</span>,
  }[streamState] : null

  return (
    <div className="space-y-4">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-200">Live Feed</h1>
          <p className="text-sm text-slate-500">
            {detections.length > 0
              ? `${detections.length} recent detection${detections.length !== 1 ? 's' : ''}`
              : 'No detections yet'}
          </p>
        </div>
        {streamBadge}
      </div>

      {detections.length === 0 ? (
        <EmptyState />
      ) : (
        <div
          ref={parentRef}
          className="overflow-y-auto"
          style={{ height: 'calc(100vh - 180px)' }}
        >
          <div
            style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}
          >
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const row = rows[virtualRow.index]
              if (!row) return null
              return (
                <div
                  key={virtualRow.key}
                  style={{
                    position: 'absolute',
                    top: virtualRow.start,
                    width: '100%',
                  }}
                  className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 pb-4"
                >
                  {row.map((detection, colIdx) => (
                    <DetectionCard
                      key={detection.id}
                      detection={detection}
                      isNew={virtualRow.index === 0 && colIdx === 0}
                    />
                  ))}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <span className="text-5xl mb-4" aria-hidden>🪶</span>
      <h2 className="text-slate-400 font-medium mb-1">No detections yet</h2>
      <p className="text-slate-600 text-sm max-w-xs">
        Waiting for birds at your feeder. Make sure Frigate is sending events and your
        camera is configured.
      </p>
    </div>
  )
}
