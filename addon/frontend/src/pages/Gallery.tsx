import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useSpeciesList, type SpeciesSort } from '../hooks/useSpecies'
import SpeciesCard from '../components/SpeciesCard'
import { SeasonalChart } from '../components/charts/SeasonalChart'
import { species as speciesApi } from '../api/client'

const SORT_OPTIONS: { value: SpeciesSort; label: string }[] = [
  { value: 'count',  label: 'Most Seen' },
  { value: 'recent', label: 'Most Recent' },
  { value: 'alpha',  label: 'Alphabetical' },
  { value: 'first',  label: 'First Seen' },
]

export default function Gallery() {
  const [sort, setSort] = useState<SpeciesSort>('count')
  const [search, setSearch] = useState('')
  const navigate = useNavigate()

  const { data: speciesList, isLoading } = useSpeciesList(sort)
  const { data: seasonal } = useQuery({
    queryKey: ['species-seasonal'],
    queryFn: speciesApi.seasonal,
    staleTime: 5 * 60_000,
  })

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

  return (
    <div className="space-y-4">
      {seasonal && seasonal.length > 0 && (
        <div className="card p-4">
          <h2 className="text-sm font-medium text-slate-300 mb-3">Species activity — last 52 weeks</h2>
          <SeasonalChart data={seasonal} />
        </div>
      )}

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
              onClick={() => navigate(`/gallery/${encodeURIComponent(s.scientific_name)}`)}
            />
          ))}
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
