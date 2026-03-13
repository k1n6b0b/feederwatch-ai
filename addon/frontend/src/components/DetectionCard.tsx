import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { detections as detectionsApi } from '../api/client'
import type { Detection } from '../types/api'
import DetectionModal from './DetectionModal'
import { useStatus } from '../hooks/useStatus'

interface DetectionCardProps {
  detection: Detection
  isNew?: boolean
  onRemove?: (id: number) => void
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

export default function DetectionCard({ detection, isNew = false, onRemove }: DetectionCardProps) {
  const [imgFailed, setImgFailed] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const { data: statusData } = useStatus()
  const queryClient = useQueryClient()

  const isFrigateClassified = detection.category_name === 'frigate_classified'
  const threshold = 0.7 // default
  const isLowConfidence = !isFrigateClassified && detection.score !== null
    && detection.score < threshold + 0.05

  const snapshotUrl = detectionsApi.snapshotUrl(detection.id)
  const isDuplicate = detection.common_name === detection.scientific_name

  async function handleDelete(e: React.MouseEvent) {
    e.stopPropagation()
    setDeleting(true)
    try {
      await detectionsApi.delete(detection.id)
      queryClient.invalidateQueries({ queryKey: ['species'] })
      onRemove?.(detection.id)
    } catch (err) {
      console.error('Delete failed:', err)
      setDeleting(false)
      setDeleteConfirm(false)
    }
  }

  return (
    <>
      <div
        className={[
          'card text-left w-full hover:ring-1 hover:ring-accent/40',
          'transition-all duration-150 group relative',
          isNew ? 'animate-fade-in-down' : '',
          isLowConfidence ? 'ring-1 ring-amber-500/40' : '',
        ].join(' ')}
      >
        {/* Snapshot — click to open modal */}
        <button
          onClick={() => setModalOpen(true)}
          className="block w-full cursor-pointer"
          aria-label={`${detection.common_name} detection — click for details`}
        >
          <div className="aspect-video bg-surface-elevated overflow-hidden relative">
            {imgFailed ? (
              <div className="w-full h-full flex items-center justify-center text-slate-600">
                <span className="text-3xl">🪶</span>
              </div>
            ) : (
              <img
                src={snapshotUrl}
                alt={detection.common_name}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                loading="lazy"
                onError={() => setImgFailed(true)}
              />
            )}
            {/* Camera badge */}
            <span className="absolute bottom-2 left-2 text-xs bg-black/60 text-slate-300 px-1.5 py-0.5 rounded">
              {detection.camera_name}
            </span>
            {detection.is_first_ever && (
              <span className="absolute top-2 right-2 badge badge-new">⭐ First ever!</span>
            )}
            {/* Trash icon on hover */}
            <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
              {!detection.is_first_ever && (
                <div onClick={e => e.stopPropagation()}>
                  {!deleteConfirm ? (
                    <button
                      onClick={(e) => { e.stopPropagation(); setDeleteConfirm(true) }}
                      className="bg-black/70 hover:bg-red-900/80 text-slate-300 hover:text-red-200 p-1 rounded transition-colors"
                      title="Delete detection"
                    >
                      <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                    </button>
                  ) : (
                    <div className="flex items-center gap-1 bg-black/80 rounded px-1.5 py-0.5">
                      <button
                        onClick={(e) => { e.stopPropagation(); setDeleteConfirm(false) }}
                        className="text-slate-400 hover:text-slate-200 text-xs"
                      >
                        ✕
                      </button>
                      <button
                        onClick={handleDelete}
                        disabled={deleting}
                        className="text-red-400 hover:text-red-200 text-xs disabled:opacity-50"
                      >
                        {deleting ? '…' : 'Del'}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </button>

        {/* Info — click to open modal */}
        <button
          onClick={() => setModalOpen(true)}
          className="block w-full text-left cursor-pointer p-3 space-y-2"
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-medium text-slate-200 text-sm leading-tight">
                {detection.common_name}
              </p>
              {!isDuplicate && (
                <p className="text-xs text-slate-500 italic mt-0.5">
                  {detection.scientific_name}
                </p>
              )}
            </div>
            <RelativeTime isoString={detection.detected_at} />
          </div>

        </button>
      </div>

      {modalOpen && (
        <DetectionModal
          detection={detection}
          frigateBaseUrl={statusData?.frigate.clips_ui_url ?? ''}
          onClose={() => setModalOpen(false)}
          onRemove={onRemove}
        />
      )}
    </>
  )
}
