import { useEffect, useRef } from 'react'
import type { Detection } from '../types/api'
import { aabUrl, frigateEventUrl, detections as detectionsApi } from '../api/client'

interface DetectionModalProps {
  detection: Detection
  frigateBaseUrl: string
  onClose: () => void
}

export default function DetectionModal({
  detection,
  frigateBaseUrl,
  onClose,
}: DetectionModalProps) {
  const backdropRef = useRef<HTMLDivElement>(null)

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  // Prevent scroll
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  const snapshotUrl = detectionsApi.snapshotUrl(detection.id)
  const clipUrl = `${frigateBaseUrl}/api/events/${detection.frigate_event_id}/clip.mp4`
  const allAboutBirdsLink = aabUrl(detection.common_name)
  const frigateLink = frigateBaseUrl
    ? frigateEventUrl(frigateBaseUrl, detection.frigate_event_id)
    : null

  const scoreLabel = detection.score !== null
    ? `${Math.round(detection.score * 100)}%`
    : null

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === backdropRef.current) onClose() }}
      role="dialog"
      aria-modal="true"
      aria-label={`${detection.common_name} detection details`}
    >
      <div className="card w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between p-4 border-b border-surface-elevated">
          <div>
            <h2 className="text-lg font-semibold text-slate-200">
              {detection.common_name}
            </h2>
            <p className="text-sm text-slate-400 italic">{detection.scientific_name}</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-slate-300 p-1 rounded transition-colors"
            aria-label="Close"
          >
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" />
            </svg>
          </button>
        </div>

        {/* Snapshot */}
        <div className="bg-black">
          <img
            src={snapshotUrl}
            alt={detection.common_name}
            className="w-full max-h-80 object-contain"
            onError={(e) => {
              const el = e.target as HTMLImageElement
              el.style.display = 'none'
              el.parentElement!.innerHTML +=
                '<div class="p-8 text-center text-slate-500 text-sm">Snapshot no longer available</div>'
            }}
          />
        </div>

        {/* Video clip */}
        {frigateBaseUrl && (
          <div className="border-t border-surface-elevated">
            <video
              controls
              preload="none"
              className="w-full max-h-48 bg-black"
              onError={(e) => {
                const el = e.target as HTMLVideoElement
                el.style.display = 'none'
                el.parentElement!.innerHTML +=
                  '<p class="p-3 text-xs text-slate-500 text-center">Video clip no longer available — adjust Frigate\'s retention settings to keep clips longer.</p>'
              }}
            >
              <source src={clipUrl} type="video/mp4" />
            </video>
          </div>
        )}

        {/* Metadata */}
        <div className="p-4 space-y-3">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div>
              <dt className="text-slate-500">Detected</dt>
              <dd className="text-slate-200">
                {new Date(detection.detected_at).toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Camera</dt>
              <dd className="text-slate-200">{detection.camera_name}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Confidence</dt>
              <dd className="text-slate-200">
                {detection.category_name === 'frigate_classified'
                  ? <span className="badge badge-frigate">Frigate sublabel</span>
                  : scoreLabel ?? '—'}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Frigate event</dt>
              <dd className="text-slate-400 font-mono text-xs truncate">
                {detection.frigate_event_id}
              </dd>
            </div>
          </dl>

          {/* Action links */}
          <div className="flex flex-wrap gap-2 pt-2 border-t border-surface-elevated">
            <a
              href={allAboutBirdsLink}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost text-accent text-xs"
            >
              View on AllAboutBirds ↗
            </a>
            {frigateLink && (
              <a
                href={frigateLink}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-ghost text-xs"
              >
                View in Frigate ↗
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
