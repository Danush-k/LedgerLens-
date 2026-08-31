import { FolderSearch, LayoutGrid, ShieldCheck } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Cases', icon: LayoutGrid, end: true },
  { to: '/new', label: 'New trace', icon: FolderSearch, end: false },
]

export function Sidebar() {
  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-ink-800 bg-ink-950 text-ink-100">
      <div className="flex items-center gap-2.5 px-5 py-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500">
          <ShieldCheck size={18} className="text-white" />
        </div>
        <div>
          <p className="text-sm font-bold leading-tight">FraudMap</p>
          <p className="text-[11px] leading-tight text-ink-500">Crypto attribution</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-brand-500/15 text-brand-300'
                  : 'text-ink-300 hover:bg-white/5 hover:text-white'
              }`
            }
          >
            <Icon size={17} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-ink-800 px-5 py-4 text-[11px] leading-relaxed text-ink-500">
        Reads public on-chain data only.
        <br />
        No wallet, funds, or custody involved.
      </div>
    </aside>
  )
}
