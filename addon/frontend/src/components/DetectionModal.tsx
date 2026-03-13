import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { Detection } from '../types/api'
import { aabUrl, frigateEventUrl, detections as detectionsApi, species as speciesApi } from '../api/client'

interface DetectionModalProps {
  detection: Detection
  frigateBaseUrl: string
  onClose: () => void
  onRemove?: (id: number) => void
}

function SourceBadge({ detection }: { detection: Detection }) {
  if (detection.category_name === 'frigate_classified') {
    return <span className="badge badge-frigate">Frigate sublabel</span>
  }
  if (detection.category_name === 'human_reclassified') {
    return <span className="text-slate-400 text-sm">Human corrected</span>
  }
  // ai_classified
  const score = detection.score !== null ? `${Math.round(detection.score * 100)}%` : null
  return <span className="text-slate-200">{score ? `AI · ${score}` : 'AI'}</span>
}

function ReclassifyPanel({
  detectionId,
  onSuccess,
  onCancel,
}: {
  detectionId: number
  onSuccess: (scientificName: string, commonName: string) => void
  onCancel: () => void
}) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Array<{ scientific_name: string; common_name: string }>>([])
  const [selected, setSelected] = useState<{ scientific_name: string; common_name: string } | null>(null)
  const [confirming, setConfirming] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (query.trim().length < 2) {
      setResults([])
      return
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await speciesApi.search(query.trim(), 10)
        setResults(data)
      } catch {
        // silently ignore
      }
    }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [query])

  async function handleConfirm() {
    if (!selected) return
    setConfirming(true)
    try {
      await detectionsApi.reclassify(detectionId, {
        scientific_name: selected.scientific_name,
        common_name: selected.common_name,
      })
      onSuccess(selected.scientific_name, selected.common_name)
    } catch (err) {
      console.error('Reclassify failed:', err)
    } finally {
      setConfirming(false)
    }
  }

  return (
    <div className="mt-3 p-3 bg-surface-elevated rounded-lg space-y-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-slate-300">Reclassify as…</span>
        <button onClick={onCancel} className="text-slate-500 hover:text-slate-300 text-xs">Cancel</button>
      </div>
      <input
        type="text"
        placeholder="Search species…"
        value={query}
        onChange={e => { setQuery(e.target.value); setSelected(null) }}
        className="w-full bg-surface-card border border-surface-elevated rounded px-2 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-accent"
        autoFocus
      />
      {results.length > 0 && !selected && (
        <ul className="space-y-0.5 max-h-40 overflow-y-auto">
          {results.map(r => (
            <li key={r.scientific_name}>
              <button
                onClick={() => setSelected(r)}
                className="w-full text-left px-2 py-1 rounded hover:bg-surface-card text-sm"
              >
                <span className="text-slate-200">{r.common_name}</span>
                <span className="text-slate-500 italic ml-2 text-xs">{r.scientific_name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {selected && (
        <div className="flex items-center justify-between gap-2 pt-1">
          <span className="text-sm text-slate-200">
            Reclassify as <strong>{selected.common_name}</strong>?
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setSelected(null)}
              className="btn-ghost text-xs"
            >
              Back
            </button>
            <button
              onClick={handleConfirm}
              disabled={confirming}
              className="btn-ghost text-xs text-accent disabled:opacity-50"
            >
              {confirming ? 'Saving…' : 'Confirm'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function DetectionModal({
  detection,
  frigateBaseUrl,
  onClose,
  onRemove,
}: DetectionModalProps) {
  const backdropRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()
  const [showVideo, setShowVideo] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showReclassify, setShowReclassify] = useState(false)
  const [currentDetection, setCurrentDetection] = useState(detection)

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

  const snapshotUrl = detectionsApi.snapshotUrl(currentDetection.id)
  const clipUrl = detectionsApi.clipUrl(currentDetection.id)
  const allAboutBirdsLink = aabUrl(currentDetection.common_name, currentDetection.scientific_name)
  const frigateLink = frigateBaseUrl && currentDetection.frigate_event_id
    ? frigateEventUrl(frigateBaseUrl, currentDetection.frigate_event_id)
    : null

  async function handleDelete() {
    setDeleting(true)
    try {
      await detectionsApi.delete(currentDetection.id)
      queryClient.invalidateQueries({ queryKey: ['species'] })
      onRemove?.(currentDetection.id)
      onClose()
    } catch (err) {
      console.error('Delete failed:', err)
      setDeleting(false)
      setDeleteConfirm(false)
    }
  }

  function handleReclassifySuccess(scientificName: string, commonName: string) {
    setCurrentDetection(d => ({
      ...d,
      scientific_name: scientificName,
      common_name: commonName,
      category_name: 'human_reclassified',
    }))
    setShowReclassify(false)
    queryClient.invalidateQueries({ queryKey: ['detections'] })
    queryClient.invalidateQueries({ queryKey: ['species'] })
  }

  const isDuplicate = currentDetection.common_name === currentDetection.scientific_name

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === backdropRef.current) onClose() }}
      role="dialog"
      aria-modal="true"
      aria-label={`${currentDetection.common_name} detection details`}
    >
      <div className="card w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between p-4 border-b border-surface-elevated">
          <div>
            <h2 className="text-lg font-semibold text-slate-200">
              {currentDetection.common_name}
            </h2>
            {!isDuplicate && (
              <p className="text-sm text-slate-400 italic">{currentDetection.scientific_name}</p>
            )}
          </div>
          <div className="flex items-center gap-1">
            {/* Trash / delete button */}
            {!deleteConfirm ? (
              <button
                onClick={() => setDeleteConfirm(true)}
                className="text-slate-500 hover:text-red-400 p-1 rounded transition-colors"
                aria-label="Delete detection"
                title="Delete detection"
              >
                <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </button>
            ) : (
              <div className="flex items-center gap-1 text-xs mr-1">
                <span className="text-slate-400">Delete?</span>
                <button
                  onClick={() => setDeleteConfirm(false)}
                  className="btn-ghost text-xs py-0.5"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="btn-ghost text-xs py-0.5 text-red-400 disabled:opacity-50"
                >
                  {deleting ? '…' : 'Delete'}
                </button>
              </div>
            )}
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
        </div>

        {/* Media — snapshot by default, video on demand */}
        {!showVideo ? (
          <div className="bg-black relative">
            <img
              src={snapshotUrl}
              alt={currentDetection.common_name}
              className="w-full max-h-80 object-contain"
              onError={(e) => {
                const el = e.target as HTMLImageElement
                el.style.display = 'none'
                el.parentElement!.innerHTML +=
                  '<div class="p-8 text-center text-slate-500 text-sm">Snapshot no longer available</div>'
              }}
            />
            {frigateBaseUrl && (
              <button
                onClick={() => setShowVideo(true)}
                className="absolute bottom-2 right-2 flex items-center gap-1.5 bg-black/70 hover:bg-black/90 text-slate-200 text-xs px-2.5 py-1.5 rounded-full transition-colors"
                aria-label="Play video clip"
              >
                <svg className="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                </svg>
                Play clip
              </button>
            )}
          </div>
        ) : (
          <div className="border-t border-surface-elevated">
            <video
              autoPlay
              controls
              className="w-full max-h-64 bg-black"
              onError={(e) => {
                const el = e.target as HTMLVideoElement
                el.style.display = 'none'
                el.parentElement!.innerHTML +=
                  '<p class="p-3 text-xs text-slate-500 text-center">Video clip no longer available — adjust Frigate\'s retention settings to keep clips longer.</p>'
              }}
            >
              <source src={clipUrl} type="video/mp4" />
            </video>
            <button
              onClick={() => setShowVideo(false)}
              className="w-full py-1 text-xs text-slate-500 hover:text-slate-300 transition-colors border-t border-surface-elevated"
            >
              ← Back to snapshot
            </button>
          </div>
        )}

        {/* Metadata */}
        <div className="p-4 space-y-3">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div>
              <dt className="text-slate-500">Detected</dt>
              <dd className="text-slate-200">
                {new Date(currentDetection.detected_at).toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Camera</dt>
              <dd className="text-slate-200">{currentDetection.camera_name}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Source</dt>
              <dd><SourceBadge detection={currentDetection} /></dd>
            </div>
            <div>
              <dt className="text-slate-500">Frigate event</dt>
              <dd className="text-slate-400 font-mono text-xs truncate">
                {currentDetection.frigate_event_id}
              </dd>
            </div>
          </dl>

          {/* Action links */}
          <div className="flex flex-wrap gap-2 pt-2 border-t border-surface-elevated">
            {allAboutBirdsLink && (
              <a
                href={allAboutBirdsLink}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-ghost text-accent text-xs"
              >
                View on AllAboutBirds ↗
              </a>
            )}
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
            <button
              onClick={() => setShowReclassify(r => !r)}
              className="btn-ghost text-xs text-slate-400 hover:text-slate-200"
            >
              Reclassify…
            </button>
          </div>

          {showReclassify && (
            <ReclassifyPanel
              detectionId={currentDetection.id}
              onSuccess={handleReclassifySuccess}
              onCancel={() => setShowReclassify(false)}
            />
          )}
        </div>
      </div>
    </div>
  )
}
