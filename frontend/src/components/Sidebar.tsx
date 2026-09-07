import {
  BarChart3, FolderSearch, LayoutGrid, LogOut, Network, Upload, UserCircle2,
} from 'lucide-react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Logo } from './Logo'
import { ThemeToggle } from './ThemeToggle'

// Grouped by what an investigator is doing, not by data model. "Intelligence"
// is deliberately its own section: it answers questions about the whole case
// load rather than about one complaint.
const NAV_GROUPS = [
  {
    label: 'Investigate',
    items: [
      { to: '/', label: 'Command centre', icon: BarChart3, end: true },
      { to: '/cases', label: 'Cases', icon: LayoutGrid, end: false },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { to: '/network', label: 'Network explorer', icon: Network, end: false },
    ],
  },
  {
    label: 'Intake',
    items: [
      { to: '/new', label: 'New trace', icon: FolderSearch, end: false },
      { to: '/bulk', label: 'Bulk upload', icon: Upload, end: false },
    ],
  },
]

export function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-chrome-border bg-chrome-bg text-chrome-text-primary">
      <div className="px-5 py-5">
        <Logo size={26} />
      </div>

      <nav className="flex-1 space-y-4 px-3">
        {NAV_GROUPS.map(group => (
          <div key={group.label}>
            <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-chrome-text-muted">
              {group.label}
            </p>
            <div className="space-y-0.5">
              {group.items.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 rounded px-3 py-1.5 text-[13px] font-medium transition-colors cursor-pointer ${
                      isActive
                        ? 'bg-brand-500 text-white'
                        : 'text-chrome-text-secondary hover:bg-chrome-border-subtle hover:text-chrome-text-primary'
                    }`
                  }
                >
                  <Icon size={15} />
                  {label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="flex items-center justify-between border-t border-chrome-border px-5 py-3">
        <span className="text-[11px] font-medium text-chrome-text-muted">Theme</span>
        <ThemeToggle />
      </div>

      {user && (
        <div className="border-t border-chrome-border px-4 py-3">
          <div className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-chrome-border-subtle">
            <div className="flex min-w-0 items-center gap-2">
              <UserCircle2 size={20} className="shrink-0 text-chrome-text-secondary" />
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-chrome-text-primary">{user.username}</p>
                <p className="text-[10px] uppercase tracking-wide text-chrome-text-muted">{user.role}</p>
              </div>
            </div>
            <button
              onClick={() => {
                logout()
                navigate('/login')
              }}
              title="Sign out"
              className="cursor-pointer shrink-0 rounded-md p-1.5 text-chrome-text-secondary transition-colors hover:bg-chrome-border-subtle hover:text-chrome-text-primary"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      )}
    </aside>
  )
}
