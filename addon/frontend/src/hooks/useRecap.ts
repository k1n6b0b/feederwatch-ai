import { useQuery } from '@tanstack/react-query'
import { recap as recapApi } from '../api/client'
import type { MonthlyRecap } from '../types/api'

export function useMonthlyRecap(year: number, month: number) {
  return useQuery<MonthlyRecap>({
    queryKey: ['recap', 'monthly', year, month],
    queryFn: () => recapApi.monthly(year, month),
    staleTime: 5 * 60_000,
    enabled: year > 0 && month >= 1 && month <= 12,
  })
}
