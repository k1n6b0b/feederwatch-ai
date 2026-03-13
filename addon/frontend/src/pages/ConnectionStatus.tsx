/**
 * Connection Status page — advanced diagnostics.
 * Accessible ONLY via StatusChip click, not in nav.
 * Shows: component health, ring buffer of last 50 MQTT events.
 */

import { useRef, useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { admin, status as statusApi, events as eventsApi } from '../api/client'
import type { MqttRingEntry, StatusResponse } from '../types/api'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}h ${m}m`
}

function relativeTime(isoStr: string): string {
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000
  if (diff < 60) return `${Math.round(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

const ACTION_STYLES: Record<MqttRingEntry['action'], string> = {
  saved_ai:         'text-emerald-400',
  saved_frigate:    'text-sky-400',
  below_threshold:  'text-amber-400',
  no_bird:          'text-slate-500',
  error:            'text-red-400',
}

const ACTION_LABELS: Record<MqttRingEntry['action'], string> = {
  saved_ai:         'AI',
  saved_frigate:    'Frigate',
  below_threshold:  'Below threshold',
  no_bird:          'No bird',
  error:            'Error',
}

// ---------------------------------------------------------------------------

function StatusSection({ data }: { data: StatusResponse }) {
  const mqttHint = !data.mqtt.connected
    ? data.mqtt.error_type === 'auth'
      ? "Authentication failed — check username/password in add-on config"
      : data.discovery?.mqtt
        ? `Detected at ${data.discovery.mqtt.host}:${data.discovery.mqtt.port} — update add-on config to match`
        : "Not connected — check hostname. For HA add-ons use the Docker service name (e.g. \`core-mosquitto\` for Mosquitto; find yours in the add-on's Info tab)"
    : null

  const frigateHint = !data.frigate.reachable && data.discovery?.frigate_url
    ? `Detected at ${data.discovery.frigate_url} — update add-on config to match`
    : null

  return (
    <div className="card p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-slate-300">System Status</h2>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* MQTT */}
        <ServiceRow
          label="MQTT"
          ok={data.mqtt.connected}
          detail={`${data.mqtt.host}:${data.mqtt.port}${data.mqtt.authenticated ? ' (auth)' : ''}`}
          hint={mqttHint}
          error={data.mqtt.error}
        />
        {/* Frigate */}
        <ServiceRow
          label="Frigate"
          ok={data.frigate.reachable}
          detail={data.frigate.api_url}
          hint={frigateHint}
        />
        {/* Model */}
        <ServiceRow
          label="AI Model"
          ok={data.model.loaded && data.model.labels_loaded}
          detail={`${data.model.path} — ${data.model.input_size}px — labels: ${data.model.labels_loaded ? 'loaded' : 'missing'}`}
          okLabel="Loaded"
          failLabel="Missing"
        />
        {/* Database */}
        <ServiceRow
          label="Database"
          ok={data.database.ok}
          detail={`${data.database.detections.toLocaleString()} detections · ${formatBytes(data.database.size_bytes)}`}
          okLabel="OK"
          failLabel="Error"
        />
      </div>
    </div>
  )
}

function ServiceRow({
  label, ok, detail, okLabel = 'OK', failLabel = 'DOWN', hint, error,
}: {
  label: string; ok: boolean; detail: string; okLabel?: string; failLabel?: string; hint?: string | null; error?: string | null
}) {
  return (
    <div className="flex flex-col gap-1 p-3 rounded-lg bg-surface-elevated">
      <div className="flex items-start gap-3">
        <span
          className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${ok ? 'bg-emerald-400' : 'bg-red-400'}`}
          aria-hidden="true"
        />
        <div className="min-w-0 flex-1">
          <div className="text-sm text-slate-200">{label}</div>
          <div className="text-xs text-slate-500 truncate" title={detail}>{detail}</div>
        </div>
        <span className={`ml-auto text-xs font-medium flex-shrink-0 ${ok ? 'text-emerald-400' : 'text-red-400'}`}>
          {ok ? okLabel : failLabel}
        </span>
      </div>
      {hint && (
        <div className="text-xs text-amber-400 pl-5">{hint}</div>
      )}
      {error && (
        <div className="text-xs text-red-400 font-mono pl-5 break-all">{error}</div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------

function RingBuffer({ entries }: { entries: MqttRingEntry[] }) {
  if (entries.length === 0) {
    return (
      <div className="text-center py-8 text-slate-600 text-sm">
        No MQTT events recorded yet
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs min-w-[600px]">
        <thead>
          <tr className="text-slate-500 border-b border-surface-elevated">
            <th className="text-left px-3 py-2 font-medium">Time</th>
            <th className="text-left px-3 py-2 font-medium">Camera</th>
            <th className="text-left px-3 py-2 font-medium">Event ID</th>
            <th className="text-right px-3 py-2 font-medium">Score</th>
            <th className="text-right px-3 py-2 font-medium">Threshold</th>
            <th className="text-left px-3 py-2 font-medium">Action</th>
          </tr>
        </thead>
        <tbody>
          {[...entries].reverse().map((e, i) => (
            <tr
              key={i}
              className="border-b border-surface-elevated/40 hover:bg-surface-card/40 transition-colors"
            >
              <td className="px-3 py-1.5 text-slate-500 tabular-nums whitespace-nowrap">
                {relativeTime(e.timestamp)}
              </td>
              <td className="px-3 py-1.5 text-slate-300">{e.camera}</td>
              <td className="px-3 py-1.5 text-slate-500 font-mono truncate max-w-[120px]" title={e.frigate_event_id}>
                {e.frigate_event_id}
              </td>
              <td className="px-3 py-1.5 text-right tabular-nums text-slate-400">
                {e.our_score !== null ? `${Math.round(e.our_score * 100)}%` : '—'}
              </td>
              <td className="px-3 py-1.5 text-right tabular-nums text-slate-500">
                {Math.round(e.threshold * 100)}%
              </td>
              <td className={`px-3 py-1.5 font-medium ${ACTION_STYLES[e.action]}`}>
                {ACTION_LABELS[e.action]}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// WAMF import card
// ---------------------------------------------------------------------------

function WamfImportCard() {
  const [state, setState] = useState<'idle' | 'uploading' | 'done' | 'error'>('idle')
  const [result, setResult] = useState<{ imported: number; skipped: number } | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  async function handleFile(file: File) {
    setState('uploading')
    setResult(null)
    setErrorMsg('')
    try {
      const buf = await file.arrayBuffer()
      const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)))
      const data = await admin.importWamf(file.name, b64)
      setResult(data)
      setState('done')
      // Invalidate Feed and Gallery caches so imported data is visible without a force-refresh.
      // The SSE refresh sentinel only reaches subscribers on the Feed page; these invalidations
      // cover the case where the user imports from ConnectionStatus (no SSE subscriber active).
      queryClient.invalidateQueries({ queryKey: ['detections', 'recent', 'initial'] })
      queryClient.invalidateQueries({ queryKey: ['species'] })
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err))
      setState('error')
    }
  }

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full px-4 py-3 flex items-center justify-between text-sm font-medium text-slate-300 hover:text-slate-100 transition-colors"
      >
        <span>Import from WhosAtMyFeeder</span>
        <span className="text-slate-600 text-xs">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-surface-elevated">
          <p className="text-xs text-slate-500 pt-3">
            Upload your <code className="text-slate-400">speciesid.db</code> to import existing detection history.
          </p>

          {state === 'idle' || state === 'error' ? (
            <div
              className="border-2 border-dashed border-surface-elevated rounded-lg p-6 text-center cursor-pointer hover:border-slate-500 transition-colors"
              onClick={() => inputRef.current?.click()}
              onDragOver={e => e.preventDefault()}
              onDrop={e => {
                e.preventDefault()
                const f = e.dataTransfer.files[0]
                if (f) handleFile(f)
              }}
            >
              <p className="text-sm text-slate-400">Drag &amp; drop or <span className="text-emerald-400">click to select</span></p>
              <p className="text-xs text-slate-600 mt-1">speciesid.db</p>
              <input
                ref={inputRef}
                type="file"
                accept=".db"
                className="sr-only"
                onChange={e => {
                  const f = e.target.files?.[0]
                  if (f) handleFile(f)
                }}
              />
            </div>
          ) : null}

          {state === 'uploading' && (
            <div className="text-sm text-slate-400 animate-pulse">Importing…</div>
          )}

          {state === 'done' && result && (
            <div className="text-sm text-emerald-400">
              Import complete — {result.imported} detections added, {result.skipped} skipped.
            </div>
          )}

          {state === 'error' && (
            <div className="text-sm text-red-400">Import failed: {errorMsg}</div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------

export default function ConnectionStatus() {
  const navigate = useNavigate()

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') navigate(-1) }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [navigate])

  const { data: statusData, isLoading: statusLoading, refetch: refetchStatus } = useQuery({
    queryKey: ['status'],
    queryFn: statusApi.get,
    refetchInterval: 15_000,
  })

  const { data: ringData, isLoading: ringLoading } = useQuery({
    queryKey: ['events-recent'],
    queryFn: eventsApi.recent,
    refetchInterval: 10_000,
  })

  return (
    <div className="space-y-4">
      <h1 className="text-base font-medium text-slate-200">Connection Status</h1>

      {statusLoading ? (
        <div className="card p-4 h-40 animate-pulse bg-surface-card" />
      ) : statusData ? (
        <StatusSection data={statusData} />
      ) : (
        <div className="card p-4 flex items-center justify-between">
          <span className="text-sm text-red-400">Failed to load status</span>
          <button
            onClick={() => refetchStatus()}
            className="btn-ghost text-xs"
          >
            Retry
          </button>
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-surface-elevated flex items-center justify-between">
          <h2 className="text-sm font-medium text-slate-300">MQTT Event Log</h2>
          <span className="text-xs text-slate-600">Last 50 events (in-memory)</span>
        </div>
        {ringLoading ? (
          <div className="h-32 animate-pulse bg-surface-card" />
        ) : (
          <RingBuffer entries={ringData ?? []} />
        )}
      </div>

      <WamfImportCard />

      {statusData && (
        <footer className="flex items-center gap-6 pt-2 pb-1 text-sm text-slate-500 border-t border-surface-elevated">
          <span>Uptime: <span className="text-slate-400">{formatUptime(statusData.uptime_seconds)}</span></span>
          <span>Version: <span className="text-slate-400">{statusData.version}</span></span>
          <a
            href="https://github.com/k1n6b0b/feederwatch-ai"
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto text-accent hover:underline"
          >
            GitHub ↗
          </a>
        </footer>
      )}
    </div>
  )
}
