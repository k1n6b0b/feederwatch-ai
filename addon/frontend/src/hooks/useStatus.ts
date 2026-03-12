import { useQuery } from '@tanstack/react-query'
import { status as statusApi } from '../api/client'
import type { StatusChipInfo, StatusResponse } from '../types/api'

export function deriveChipInfo(s: StatusResponse): StatusChipInfo {
  if (!s.model.loaded || !s.database.ok) {
    return { state: 'error', label: 'Error' }
  }
  if (!s.mqtt.connected && !s.frigate.reachable) {
    return { state: 'degraded', label: 'MQTT & Frigate Unreachable' }
  }
  if (!s.mqtt.connected) {
    return { state: 'degraded', label: 'MQTT Disconnected' }
  }
  if (!s.frigate.reachable) {
    return { state: 'degraded', label: 'Frigate Unreachable' }
  }
  return { state: 'connected', label: 'Connected' }
}

export function useStatus() {
  return useQuery({
    queryKey: ['status'],
    queryFn: statusApi.get,
    refetchInterval: 30_000,
    refetchIntervalInBackground: true,
  })
}
