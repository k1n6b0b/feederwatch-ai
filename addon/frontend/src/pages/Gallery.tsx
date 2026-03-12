import { useState, useMemo } from 'react'
import { useSpeciesList, useSpeciesDetail, useSpeciesPhenology, type SpeciesSort } from '../hooks/useSpecies'
import SpeciesCard from '../components/SpeciesCard'
import { aabUrl } from '../api/client'
import { SpeciesTimeOfDay } from '../components/charts/SpeciesTimeOfDay'
import { PhenologyCalendar } from '../components/charts/PhenologyCalendar'

const SORT_OPTIONS: { value: SpeciesSort; label: string }[] = [
  { value: 'count',  label: 'Most Seen' },
  { value: 'recent', label: 'Most Recent' },
  { value: 'alpha',  label: 'Alphabetical' },
  { value: 'first',  label: 'First Seen' },
]

export default function Gallery() {
  const [sort, setSort] = useState<SpeciesSort>('count')
  const [search, setSearch] = useState('')
  const [selectedSpecies, setSelectedSpecies] = useState<string | null>(null)

  const { data: speciesList, isLoading } = useSpeciesList(sort)

  const today = new Date().toDateString()
  const todaySpecies = useMemo(() => {
    if (!speciesList) return new Set<string>()
    return new Set(
      speciesList
        .filter(s => new Date(s.last_seen).toDateString() === today &&
                     new Date(s.first_seen).toDateString() === today)
        .map(s => s.scientific_name)
    )
  }, [speciesList, today])

  const filtered = useMemo(() => {
    if (!speciesList) return []
    if (!search.trim()) return speciesList
    const q = search.toLowerCase()
    return speciesList.filter(
      s => s.common_name.toLowerCase().includes(q) ||
           s.scientific_name.toLowerCase().includes(q)
    )
  }, [speciesList, search])

  if (selectedSpecies) {
    return (
      <SpeciesDetail
        scientificName={selectedSpecies}
        onBack={() => setSelectedSpecies(null)}
      />
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-200">Species Gallery</h1>
          <p className="text-sm text-slate-500">
            {speciesList?.length ?? 0} species observed all-time
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Search */}
          <input
            type="search"
            placeholder="Search species…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input w-48"
            aria-label="Search species"
          />

          {/* Sort */}
          <select
            value={sort}
            onChange={e => setSort(e.target.value as SpeciesSort)}
            className="input w-36"
            aria-label="Sort species"
          >
            {SORT_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <SkeletonGrid />
      ) : filtered.length === 0 ? (
        <EmptyState search={search} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(s => (
            <SpeciesCard
              key={s.scientific_name}
              species={s}
              isNewToday={todaySpecies.has(s.scientific_name)}
              onClick={() => setSelectedSpecies(s.scientific_name)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Species detail view
// ---------------------------------------------------------------------------

function SpeciesDetail({ scientificName, onBack }: { scientificName: string; onBack: () => void }) {
  const { data: detail, isLoading } = useSpeciesDetail(scientificName)
  const { data: phenology } = useSpeciesPhenology(scientificName)

  if (isLoading || !detail) {
    return (
      <div className="space-y-4">
        <button onClick={onBack} className="btn-ghost">← Back to Gallery</button>
        <div className="text-slate-500 text-sm">Loading…</div>
      </div>
    )
  }

  const showPhenology = phenology && phenology.length >= 2

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={onBack} className="btn-ghost">← Back</button>
        <div>
          <h1 className="text-lg font-semibold text-slate-200">{detail.common_name}</h1>
          <p className="text-sm text-slate-500 italic">{detail.scientific_name}</p>
        </div>
        <a
          href={aabUrl(detail.common_name)}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto btn-ghost text-accent text-sm"
        >
          AllAboutBirds ↗
        </a>
      </div>

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
          <h2 className="text-sm font-medium text-slate-300 mb-1">Arrival & departure by year</h2>
          <p className="text-xs text-slate-600 mb-3">First and last detection each year</p>
          <PhenologyCalendar data={phenology} />
        </div>
      )}
    </div>
  )
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="card animate-pulse">
          <div className="aspect-video bg-surface-elevated" />
          <div className="p-3 space-y-2">
            <div className="h-4 bg-surface-elevated rounded w-3/4" />
            <div className="h-3 bg-surface-elevated rounded w-1/2" />
          </div>
        </div>
      ))}
    </div>
  )
}

function EmptyState({ search }: { search: string }) {
  return (
    <div className="text-center py-16 text-slate-500">
      {search ? `No species matching "${search}"` : 'No species detected yet'}
    </div>
  )
}
