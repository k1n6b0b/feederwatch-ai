import { NavLink } from 'react-router-dom'
import StatusChip from './StatusChip'

const NAV_ITEMS = [
  { to: '/',        label: 'Feed',    exact: true },
  { to: '/gallery', label: 'Gallery', exact: false },
  { to: '/daily',   label: 'Daily',   exact: false },
]

interface ShellProps {
  children: React.ReactNode
}

export default function Shell({ children }: ShellProps) {
  return (
    <div className="min-h-screen flex flex-col bg-surface-base">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-surface-base/95 backdrop-blur border-b border-surface-elevated">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-14">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <span className="text-xl" aria-hidden>🪶</span>
              <span className="font-semibold text-slate-200 tracking-tight">
                FeederWatch AI
              </span>
            </div>

            {/* Nav — connection-status intentionally absent */}
            <nav className="flex items-center gap-1" aria-label="Main navigation">
              {NAV_ITEMS.map(({ to, label, exact }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={exact}
                  className={({ isActive }) =>
                    ['nav-link', isActive ? 'nav-link-active' : ''].join(' ')
                  }
                >
                  {label}
                </NavLink>
              ))}
            </nav>

            {/* Status chip — only path to /connection-status */}
            <StatusChip />
          </div>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-6">
        {children}
      </main>
    </div>
  )
}
