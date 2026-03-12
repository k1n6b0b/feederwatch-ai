import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { species as speciesApi } from '../api/client'

export type SpeciesSort = 'count' | 'recent' | 'alpha' | 'first'

export function useSpeciesList(sort: SpeciesSort = 'count') {
  return useQuery({
    queryKey: ['species', 'list', sort],
    queryFn: () => speciesApi.list(sort, 100),
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  })
}

export function useSpeciesDetail(scientificName: string) {
  return useQuery({
    queryKey: ['species', 'detail', scientificName],
    queryFn: () => speciesApi.get(scientificName),
    enabled: !!scientificName,
  })
}

export function useSpeciesPhenology(scientificName: string) {
  return useQuery({
    queryKey: ['species', 'phenology', scientificName],
    queryFn: () => speciesApi.phenology(scientificName),
    enabled: !!scientificName,
  })
}
