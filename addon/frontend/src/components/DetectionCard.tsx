import { useState } from 'react'
import { detections as detectionsApi } from '../api/client'
import type { Detection } from '../types/api'
import DetectionModal from './DetectionModal'
import { useStatus } from '../hooks/useStatus'

interface DetectionCardProps {
  detection: Detection
  isNew?: boolean
}

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = pct >= 85 ? 'bg-accent' : pct >= 70 ? 'bg-amber-400' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-surface-elevated rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-mono text-slate-400 tabular-nums w-8 text-right">
        {pct}%
      </span>
    </div>
  )
}

function RelativeTime({ isoString }: { isoString: string }) {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)

  let label: string
  if (diffSec < 60)       label = `${diffSec}s ago`
  else if (diffSec < 3600) label = `${Math.floor(diffSec / 60)}m ago`
  else if (diffSec < 86400) label = `${Math.floor(diffSec / 3600)}h ago`
  else                    label = date.toLocaleDateString()

  return (
    <time dateTime={isoString} className="text-xs text-slate-500 tabular-nums">
      {label}
    </time>
  )
}

export default function DetectionCard({ detection, isNew = false }: DetectionCardProps) {
  const [modalOpen, setModalOpen] = useState(false)
  const { data: statusData } = useStatus()

  const isFrigateClassified = detection.category_name === 'frigate_classified'
  const threshold = statusData?.model.loaded ? 0.7 : 0.7 // default; ideally from config
  const isLowConfidence = !isFrigateClassified && detection.score !== null
    && detection.score < threshold + 0.05

  const snapshotUrl = detectionsApi.snapshotUrl(detection.id)

  return (
    <>
      <button
        onClick={() => setModalOpen(true)}
        className={[
          'card text-left w-full hover:ring-1 hover:ring-accent/40',
          'transition-all duration-150 cursor-pointer group',
          isNew ? 'animate-fade-in-down' : '',
          isLowConfidence ? 'ring-1 ring-amber-500/40' : '',
        ].join(' ')}
        aria-label={`${detection.common_name} detection — click for details`}
      >
        {/* Snapshot */}
        <div className="aspect-video bg-surface-elevated overflow-hidden relative">
          <img
            src={snapshotUrl}
            alt={detection.common_name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
            onError={(e) => {
              (e.target as HTMLImageElement).src =
                'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60"%3E%3Crect width="100" height="60" fill="%231e293b"/%3E%3Ctext x="50" y="35" text-anchor="middle" fill="%2364748b" font-size="10"%3ENo image%3C/text%3E%3C/svg%3E'
            }}
          />
          {/* Camera badge */}
          <span className="absolute bottom-2 left-2 text-xs bg-black/60 text-slate-300 px-1.5 py-0.5 rounded">
            {detection.camera_name}
          </span>
          {detection.is_first_ever && (
            <span className="absolute top-2 right-2 badge badge-new">⭐ First ever!</span>
          )}
        </div>

        {/* Info */}
        <div className="p-3 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-medium text-slate-200 text-sm leading-tight">
                {detection.common_name}
              </p>
              <p className="text-xs text-slate-500 italic mt-0.5">
                {detection.scientific_name}
              </p>
            </div>
            <RelativeTime isoString={detection.detected_at} />
          </div>

          {isFrigateClassified ? (
            <span className="badge badge-frigate">Frigate</span>
          ) : detection.score !== null ? (
            <ConfidenceBar score={detection.score} />
          ) : null}
        </div>
      </button>

      {modalOpen && (
        <DetectionModal
          detection={detection}
          frigateBaseUrl={statusData?.frigate.url ?? ''}
          onClose={() => setModalOpen(false)}
        />
      )}
    </>
  )
}
