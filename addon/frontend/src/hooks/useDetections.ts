import { useQuery } from '@tanstack/react-query'
import { detections as detectionsApi } from '../api/client'

export function useDailyDetections(date: string) {
  return useQuery({
    queryKey: ['detections', 'daily', date],
    queryFn: () => detectionsApi.daily(date),
  })
}

export function useDailySummary(date: string) {
  return useQuery({
    queryKey: ['detections', 'summary', date],
    queryFn: () => detectionsApi.dailySummary(date),
  })
}
