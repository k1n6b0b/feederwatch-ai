/**
 * SSE hook for the live detection feed.
 * Connects to /api/v1/detections/stream and pushes new detections in ~1s.
 * Falls back to polling /api/v1/detections/recent every 10s on persistent SSE failure.
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { detections as detectionsApi } from '../api/client'
import type { Detection } from '../types/api'

const SSE_URL = new URL('api/v1/detections/stream', document.baseURI).pathname
const MAX_FEED_SIZE = 200
const SSE_RETRY_LIMIT = 3
const POLL_INTERVAL = 10_000

type StreamState = 'connecting' | 'open' | 'polling' | 'error'

export function useDetectionStream() {
  const [detections, setDetections] = useState<Detection[]>([])
  const [streamState, setStreamState] = useState<StreamState>('connecting')
  const eventSourceRef = useRef<EventSource | null>(null)
  const retryCountRef = useRef(0)
  const pollingRef = useRef(false)
  const queryClient = useQueryClient()

  const prependDetection = useCallback((detection: Detection) => {
    setDetections(prev => {
      // Deduplicate by id
      if (prev.some(d => d.id === detection.id)) return prev
      const next = [detection, ...prev]
      return next.slice(0, MAX_FEED_SIZE)
    })
  }, [])

  // Load initial detections
  const { data: initialData } = useQuery({
    queryKey: ['detections', 'recent', 'initial'],
    queryFn: () => detectionsApi.recent(20),
    staleTime: Infinity,
  })

  useEffect(() => {
    if (initialData && detections.length === 0) {
      setDetections(initialData)
    }
  }, [initialData]) // eslint-disable-line react-hooks/exhaustive-deps

  // SSE connection
  const connectSSE = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    const es = new EventSource(SSE_URL)
    eventSourceRef.current = es
    setStreamState('connecting')

    es.onopen = () => {
      setStreamState('open')
      retryCountRef.current = 0
    }

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'refresh') {
          // WAMF import or other bulk change — invalidate cache and re-seed local state
          queryClient.invalidateQueries({ queryKey: ['detections', 'recent', 'initial'] })
          queryClient.invalidateQueries({ queryKey: ['species'] })
          detectionsApi.recent(20).then(fresh => setDetections(fresh)).catch(() => {})
          return
        }
        prependDetection(data as Detection)
      } catch {
        // Ignore malformed SSE data
      }
    }

    es.onerror = () => {
      es.close()
      eventSourceRef.current = null
      retryCountRef.current += 1

      if (retryCountRef.current >= SSE_RETRY_LIMIT) {
        setStreamState('polling')
        pollingRef.current = true
      } else {
        // Exponential backoff retry
        const delay = Math.min(1000 * 2 ** retryCountRef.current, 30_000)
        setTimeout(connectSSE, delay)
      }
    }
  }, [prependDetection, queryClient])

  // Polling fallback
  const { data: pollData } = useQuery({
    queryKey: ['detections', 'recent', 'poll'],
    queryFn: () => detectionsApi.recent(20),
    refetchInterval: pollingRef.current ? POLL_INTERVAL : false,
    enabled: streamState === 'polling',
  })

  useEffect(() => {
    if (pollData && streamState === 'polling') {
      setDetections(pollData)
    }
  }, [pollData, streamState])

  // Start SSE on mount
  useEffect(() => {
    connectSSE()
    return () => {
      eventSourceRef.current?.close()
    }
  }, [connectSSE])

  const removeDetection = useCallback((id: number) => {
    setDetections(prev => prev.filter(d => d.id !== id))
  }, [])

  const updateDetection = useCallback((id: number, patches: Partial<Detection>) => {
    setDetections(prev => prev.map(d => d.id === id ? { ...d, ...patches } : d))
  }, [])

  return { detections, streamState, prependDetection, removeDetection, updateDetection }
}
