import { useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMonthlyRecap } from '../hooks/useRecap'
import { detections } from '../api/client'

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

function formatHour(h: number): string {
  if (h === 0) return '12 am'
  if (h < 12) return `${h} am`
  if (h === 12) return '12 pm'
  return `${h - 12} pm`
}

function formatDate(iso: string): string {
  return new Date(iso + 'T12:00:00').toLocaleDateString('en-US', {
    month: 'long', day: 'numeric',
  })
}

// ---------------------------------------------------------------------------
// Snapshot image with feather fallback
// ---------------------------------------------------------------------------

function RecapSnapshot({ detectionId, className }: { detectionId: number | null; className?: string }) {
  const [failed, setFailed] = useState(false)
  if (!detectionId || failed) {
    return (
      <div className={`flex items-center justify-center bg-surface-elevated rounded-2xl ${className ?? ''}`}>
        <span className="text-6xl" aria-hidden>🪶</span>
      </div>
    )
  }
  return (
    <img
      src={detections.snapshotUrl(detectionId)}
      className={`object-cover rounded-2xl ${className ?? ''}`}
      onError={() => setFailed(true)}
      alt=""
    />
  )
}

// ---------------------------------------------------------------------------
// Slide wrapper
// ---------------------------------------------------------------------------

function Slide({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <section
      className={`h-screen snap-start snap-always flex flex-col items-center justify-center px-8 gap-6 ${className}`}
    >
      {children}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Download helper — captures all slides as one tall PNG
// ---------------------------------------------------------------------------

async function downloadRecapPng(
  containerEl: HTMLDivElement,
  filename: string,
  onStart: () => void,
  onDone: () => void,
) {
  // Lazy-load html2canvas to avoid bloating the initial bundle
  const { default: html2canvas } = await import('html2canvas')

  onStart()

  // Temporarily expand the scroll container so html2canvas can see all slides
  const original = {
    height: containerEl.style.height,
    overflow: containerEl.style.overflow,
    scrollSnapType: containerEl.style.scrollSnapType,
  }
  containerEl.style.height = 'auto'
  containerEl.style.overflow = 'visible'
  containerEl.style.scrollSnapType = 'none'

  const sections = containerEl.querySelectorAll<HTMLElement>('section')
  const sectionOriginals = Array.from(sections).map(s => ({
    height: s.style.height,
    minHeight: s.style.minHeight,
    scrollSnapAlign: s.style.scrollSnapAlign,
  }))
  sections.forEach(s => {
    s.style.height = 'auto'
    s.style.minHeight = '100vh'
    s.style.scrollSnapAlign = 'none'
  })

  // Wait one animation frame so layout reflows before capture
  await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))

  try {
    const canvas = await html2canvas(containerEl, {
      scale: 2,           // retina quality
      useCORS: true,
      logging: false,
      backgroundColor: '#0f172a',
    })

    const link = document.createElement('a')
    link.download = filename
    link.href = canvas.toDataURL('image/png')
    link.click()
  } finally {
    // Always restore original layout even if capture fails
    containerEl.style.height = original.height
    containerEl.style.overflow = original.overflow
    containerEl.style.scrollSnapType = original.scrollSnapType
    sections.forEach((s, i) => {
      s.style.height = sectionOriginals[i].height
      s.style.minHeight = sectionOriginals[i].minHeight
      s.style.scrollSnapAlign = sectionOriginals[i].scrollSnapAlign
    })
    onDone()
  }
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Recap() {
  const { year: yearStr, month: monthStr } = useParams<{ year: string; month: string }>()
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const [downloading, setDownloading] = useState(false)

  const year = parseInt(yearStr ?? '0', 10)
  const month = parseInt(monthStr ?? '0', 10)
  const monthName = MONTH_NAMES[month - 1] ?? 'Unknown'

  const { data: recap, isLoading } = useMonthlyRecap(year, month)

  const monthPadded = String(month).padStart(2, '0')
  const filename = `feederwatch-recap-${year}-${monthPadded}.png`

  function handleDownload() {
    if (!containerRef.current || downloading) return
    downloadRecapPng(containerRef.current, filename, () => setDownloading(true), () => setDownloading(false))
  }

  return (
    <div
      ref={containerRef}
      className="h-screen overflow-y-scroll snap-y snap-mandatory bg-surface-base text-slate-200 relative"
    >
      {/* Back button — fixed overlay */}
      <button
        onClick={() => navigate(-1)}
        className="fixed top-4 left-4 z-50 bg-surface-card/80 backdrop-blur-sm text-slate-400 hover:text-slate-200 rounded-full w-9 h-9 flex items-center justify-center transition-colors"
        aria-label="Go back"
      >
        ←
      </button>

      {/* Download button — fixed overlay, only shown when data is ready */}
      {recap && recap.total_visits > 0 && (
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="fixed top-4 right-4 z-50 bg-surface-card/80 backdrop-blur-sm text-slate-400 hover:text-slate-200 rounded-full px-3 h-9 flex items-center gap-1.5 text-sm transition-colors disabled:opacity-50"
          aria-label="Download recap as image"
        >
          {downloading ? (
            <span className="animate-spin text-base">⏳</span>
          ) : (
            <>↓ Save</>
          )}
        </button>
      )}

      {isLoading && (
        <Slide>
          <div className="animate-pulse flex flex-col items-center gap-4 w-full max-w-sm">
            <div className="h-24 w-48 bg-surface-elevated rounded-xl" />
            <div className="h-8 w-32 bg-surface-elevated rounded-xl" />
            <div className="h-6 w-56 bg-surface-elevated rounded-xl" />
          </div>
        </Slide>
      )}

      {!isLoading && recap && recap.total_visits === 0 && (
        <Slide>
          <p className="text-5xl" aria-hidden>🪶</p>
          <h1 className="text-2xl font-bold text-slate-200 text-center">
            No detections in {monthName} {year}
          </h1>
          <p className="text-slate-500 text-sm text-center">
            Check back after your feeder gets some visitors.
          </p>
          <button onClick={() => navigate(-1)} className="btn-primary mt-4 px-6">
            Back
          </button>
        </Slide>
      )}

      {!isLoading && recap && recap.total_visits > 0 && (
        <>
          {/* Slide 1 — Intro */}
          <Slide className="bg-gradient-to-b from-accent/10 to-surface-base">
            <div className="text-center">
              <p className="text-8xl font-black text-accent tabular-nums leading-none">{month}</p>
              <p className="text-3xl font-light text-slate-400 mt-2">{year}</p>
            </div>
            <div className="text-center">
              <p className="text-slate-500 text-sm font-medium uppercase tracking-widest">Your</p>
              <h1 className="text-4xl font-bold text-slate-200">{monthName} Recap</h1>
            </div>
            <p className="text-slate-600 text-sm">🪶 FeederWatch AI</p>
            <p className="text-slate-600 text-xs mt-8 animate-bounce">↓ scroll</p>
          </Slide>

          {/* Slide 2 — Stats */}
          <Slide>
            <p className="text-slate-400 text-sm font-medium uppercase tracking-widest">In {monthName}</p>
            <div className="text-center space-y-2">
              <div>
                <span className="text-6xl font-black text-accent tabular-nums">
                  {recap.unique_species.toLocaleString()}
                </span>
                <span className="text-xl text-slate-400 ml-2">species</span>
              </div>
              <div>
                <span className="text-6xl font-black text-accent tabular-nums">
                  {recap.total_visits.toLocaleString()}
                </span>
                <span className="text-xl text-slate-400 ml-2">visits</span>
              </div>
            </div>
            <RecapSnapshot detectionId={recap.featured_detection_id} className="w-full max-w-xs aspect-video" />
            <p className="text-slate-500 text-sm">
              Active {recap.period.days_with_detections} of {recap.period.total_days} days
            </p>
          </Slide>

          {/* Slide 3 — Top Visitor */}
          {recap.top_species && (
            <Slide>
              <p className="text-slate-400 text-sm font-medium uppercase tracking-widest text-center">
                Your most frequent visitor
              </p>
              <RecapSnapshot detectionId={recap.top_species.best_detection_id} className="w-full max-w-xs aspect-video" />
              <div className="text-center">
                <h2 className="text-3xl font-bold text-slate-100">{recap.top_species.common_name}</h2>
                <p className="text-slate-500 text-sm italic mt-1">{recap.top_species.scientific_name}</p>
                <p className="text-accent font-semibold mt-2">
                  {recap.top_species.count.toLocaleString()} visit{recap.top_species.count !== 1 ? 's' : ''} this month
                </p>
              </div>
            </Slide>
          )}

          {/* Slide 4 — New Arrivals */}
          <Slide>
            <p className="text-slate-400 text-sm font-medium uppercase tracking-widest text-center">
              First-time visitors this month
            </p>
            {recap.new_species.length === 0 ? (
              <div className="text-center">
                <p className="text-4xl mb-4" aria-hidden>🔁</p>
                <p className="text-slate-400">No new species this month</p>
                <p className="text-slate-600 text-sm mt-1">But every visit counts.</p>
              </div>
            ) : (
              <ul className="w-full max-w-sm space-y-3">
                {recap.new_species.slice(0, 5).map(sp => (
                  <li key={sp.scientific_name} className="flex items-center gap-3">
                    <div className="w-12 h-12 flex-shrink-0">
                      <RecapSnapshot detectionId={sp.best_detection_id} className="w-12 h-12" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-slate-200 truncate">{sp.common_name}</p>
                      <p className="text-slate-500 text-xs">First seen {formatDate(sp.first_seen)}</p>
                    </div>
                    <span className="badge badge-new flex-shrink-0">New!</span>
                  </li>
                ))}
                {recap.new_species.length > 5 && (
                  <li className="text-slate-500 text-sm text-center pt-1">
                    +{recap.new_species.length - 5} more
                  </li>
                )}
              </ul>
            )}
          </Slide>

          {/* Slide 5 — Peak Time */}
          <Slide>
            <p className="text-slate-400 text-sm font-medium uppercase tracking-widest text-center">
              Your feeder was busiest at
            </p>
            <p className="text-7xl font-black text-accent">
              {recap.peak_hour !== null ? formatHour(recap.peak_hour) : '—'}
            </p>
            {recap.busiest_day && (
              <div className="text-center">
                <p className="text-slate-400 text-sm">Busiest day</p>
                <p className="text-slate-200 font-semibold">
                  {formatDate(recap.busiest_day.date)} — {recap.busiest_day.count.toLocaleString()} visits
                </p>
              </div>
            )}
            <p className="text-slate-600 text-xs mt-8">↑ scroll to review</p>
          </Slide>
        </>
      )}
    </div>
  )
}
