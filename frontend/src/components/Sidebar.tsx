import { BarChart3, FolderSearch, LayoutGrid, LogOut, ShieldCheck, Upload, UserCircle2 } from 'lucide-react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { ThemeToggle } from './ThemeToggle'

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: BarChart3, end: true },
  { to: '/cases', label: 'Cases', icon: LayoutGrid, end: false },
  { to: '/new', label: 'New trace', icon: FolderSearch, end: false },
  { to: '/bulk', label: 'Bulk upload', icon: Upload, end: false },
]

export function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-chrome-border bg-chrome-bg text-chrome-text-primary">
      <div className="flex items-center gap-2.5 px-5 py-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500">
          <ShieldCheck size={18} className="text-white" />
        </div>
        <div>
          <p className="text-sm font-bold leading-tight">LedgerLens</p>
          <p className="text-[11px] leading-tight text-chrome-text-muted">Crypto attribution</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors cursor-pointer ${
                isActive
                  ? 'bg-brand-500/15 text-brand-300'
                  : 'text-chrome-text-secondary hover:bg-chrome-border-subtle hover:text-chrome-text-primary'
              }`
            }
          >
            <Icon size={17} />
            {label}
          </NavLink>
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
