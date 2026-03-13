import { useParams, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query'
import { useSpeciesDetail, useSpeciesPhenology } from '../hooks/useSpecies'
import { aabUrl, detections as detectionsApi, species as speciesApi } from '../api/client'
import { SpeciesTimeOfDay } from '../components/charts/SpeciesTimeOfDay'
import { PhenologyCalendar } from '../components/charts/PhenologyCalendar'
import DetectionModal from '../components/DetectionModal'
import { useStatus } from '../hooks/useStatus'
import type { Detection } from '../types/api'

const PAGE_SIZE = 20

export default function SpeciesDetail() {
  const { scientificName } = useParams<{ scientificName: string }>()
  const navigate = useNavigate()

  if (!scientificName) {
    navigate('/gallery', { replace: true })
    return null
  }

  return <SpeciesDetailInner scientificName={decodeURIComponent(scientificName)} navigate={navigate} />
}

function SpeciesDetailInner({
  scientificName,
  navigate,
}: {
  scientificName: string
  navigate: ReturnType<typeof useNavigate>
}) {
  const [selectedDetection, setSelectedDetection] = useState<Detection | null>(null)
  const { data: statusData } = useStatus()
  const queryClient = useQueryClient()

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (selectedDetection) {
          setSelectedDetection(null)
        } else {
          navigate(-1)
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [navigate, selectedDetection])

  const { data: detail, isLoading } = useSpeciesDetail(scientificName)
  const { data: phenology } = useSpeciesPhenology(scientificName)

  const {
    data: photosData,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['species-detections', scientificName],
    queryFn: ({ pageParam = 0 }) =>
      speciesApi.detections(scientificName, PAGE_SIZE, pageParam as number),
    getNextPageParam: (lastPage: Detection[], allPages: Detection[][]) =>
      lastPage.length === PAGE_SIZE ? allPages.length * PAGE_SIZE : undefined,
    initialPageParam: 0,
  })

  if (isLoading || !detail) {
    return (
      <div className="space-y-4">
        <button onClick={() => navigate(-1)} className="btn-ghost">← Back</button>
        <div className="text-slate-500 text-sm">Loading…</div>
      </div>
    )
  }

  const showPhenology = phenology && phenology.length >= 2
  const aab = aabUrl(detail.common_name, detail.scientific_name)
  const allPhotos = photosData?.pages.flat() ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(-1)} className="btn-ghost">← Back</button>
        <div>
          <h1 className="text-lg font-semibold text-slate-200">{detail.common_name}</h1>
          <p className="text-sm text-slate-500 italic">{detail.scientific_name}</p>
        </div>
        {aab && (
          <a
            href={aab}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto btn-ghost text-accent text-sm"
          >
            AllAboutBirds ↗
          </a>
        )}
      </div>

      {/* Hero photo */}
      {detail.best_detection_id != null && (
        <div className="rounded-xl overflow-hidden bg-black aspect-video">
          <img
            src={detectionsApi.snapshotUrl(detail.best_detection_id)}
            alt={detail.common_name}
            className="w-full h-full object-contain"
          />
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total sightings', value: detail.total_detections.toLocaleString() },
          { label: 'Best score', value: detail.best_score ? `${Math.round(detail.best_score * 100)}%` : '—' },
          { label: 'First seen', value: new Date(detail.first_seen).toLocaleDateString() },
          { label: 'Last seen', value: new Date(detail.last_seen).toLocaleDateString() },
        ].map(stat => (
          <div key={stat.label} className="card p-3">
            <p className="text-xs text-slate-500">{stat.label}</p>
            <p className="text-lg font-semibold text-slate-200 mt-0.5">{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Time of day chart */}
      <div className="card p-4">
        <h2 className="text-sm font-medium text-slate-300 mb-3">Activity by hour of day</h2>
        <SpeciesTimeOfDay data={detail.hourly_activity} />
      </div>

      {/* Phenology */}
      {showPhenology && (
        <div className="card p-4">
          <h2 className="text-sm font-medium text-slate-300 mb-1">Arrival &amp; departure by year</h2>
          <p className="text-xs text-slate-600 mb-3">First and last detection each year</p>
          <PhenologyCalendar data={phenology} />
        </div>
      )}

      {/* Photo grid */}
      {allPhotos.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-slate-300">All photos</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {allPhotos.map(d => (
              <button
                key={d.id}
                onClick={() => setSelectedDetection(d)}
                className="aspect-square bg-surface-elevated rounded-lg overflow-hidden hover:ring-1 hover:ring-accent/40 transition-all"
                aria-label={`View ${detail.common_name} detection from ${new Date(d.detected_at).toLocaleDateString()}`}
              >
                <img
                  src={detectionsApi.snapshotUrl(d.id)}
                  alt={`${detail.common_name} — ${new Date(d.detected_at).toLocaleDateString()}`}
                  className="w-full h-full object-cover"
                  loading="lazy"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none'
                  }}
                />
              </button>
            ))}
          </div>
          {hasNextPage && (
            <div className="text-center">
              <button
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className="btn-ghost text-sm disabled:opacity-50"
              >
                {isFetchingNextPage ? 'Loading…' : 'Load more'}
              </button>
            </div>
          )}
        </div>
      )}

      {selectedDetection && (
        <DetectionModal
          detection={selectedDetection}
          frigateBaseUrl={statusData?.frigate.url ?? ''}
          onClose={() => setSelectedDetection(null)}
          onRemove={(_id) => {
            queryClient.invalidateQueries({ queryKey: ['species-detections', scientificName] })
            queryClient.invalidateQueries({ queryKey: ['species'] })
            setSelectedDetection(null)
            // Navigate back if this was the last photo
            if (allPhotos.length <= 1) navigate(-1)
          }}
        />
      )}
    </div>
  )
}
