import type { Species } from '../types/api'
import { detections as detectionsApi } from '../api/client'

interface SpeciesCardProps {
  species: Species
  isNewToday: boolean
  onClick: () => void
}

export default function SpeciesCard({ species, isNewToday, onClick }: SpeciesCardProps) {
  const firstSeen = new Date(species.first_seen)
  const lastSeen  = new Date(species.last_seen)
  const today     = new Date()
  const isToday   = lastSeen.toDateString() === today.toDateString()

  return (
    <button
      onClick={onClick}
      className="card text-left w-full hover:ring-1 hover:ring-accent/40 transition-all duration-150 cursor-pointer group"
      aria-label={`${species.common_name} — ${species.total_detections} sightings`}
    >
      {/* Best photo */}
      <div className="aspect-video bg-surface-elevated overflow-hidden relative">
        {species.best_snapshot_path ? (
          <img
            src={detectionsApi.snapshotUrl(0)}
            alt={species.common_name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-600">
            <span className="text-3xl">🪶</span>
          </div>
        )}
        {isNewToday && (
          <span className="absolute top-2 right-2 badge badge-new">★ New today</span>
        )}
      </div>

      {/* Info */}
      <div className="p-3 space-y-1">
        <p className="font-medium text-slate-200 text-sm">{species.common_name}</p>
        <p className="text-xs text-slate-500 italic">{species.scientific_name}</p>

        <div className="pt-1 flex items-center justify-between text-xs text-slate-500">
          <span>📸 {species.total_detections.toLocaleString()} sighting{species.total_detections !== 1 ? 's' : ''}</span>
          {species.best_score !== null && (
            <span className="font-mono">{Math.round(species.best_score * 100)}% best</span>
          )}
        </div>

        <div className="text-xs text-slate-600 space-y-0.5">
          <div>First: {firstSeen.toLocaleDateString()}</div>
          <div>Last: {isToday ? 'today' : lastSeen.toLocaleDateString()}</div>
        </div>
      </div>
    </button>
  )
}
