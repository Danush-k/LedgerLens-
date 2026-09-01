import { Command } from 'cmdk'
import { BarChart3, Clock, FolderSearch, LayoutGrid, Search, Upload } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listCases } from '../api/client'
import type { CaseSummary } from '../types'

const STATIC_COMMANDS = [
  { to: '/', label: 'Go to Overview', icon: BarChart3, keywords: ['dashboard', 'analytics', 'home'] },
  { to: '/cases', label: 'Go to Cases', icon: LayoutGrid, keywords: ['list', 'investigations'] },
  { to: '/new', label: 'New wallet trace', icon: FolderSearch, keywords: ['submit', 'trace', 'address'] },
  { to: '/bulk', label: 'Bulk CSV upload', icon: Upload, keywords: ['csv', 'many', 'import'] },
]

interface Props {
  open: boolean
  onClose: () => void
}

export function CommandPalette({ open, onClose }: Props) {
  const [recentCases, setRecentCases] = useState<CaseSummary[]>([])
  const navigate = useNavigate()

  useEffect(() => {
    if (open) {
      listCases({}).then((cases) => setRecentCases(cases.slice(0, 8))).catch(() => setRecentCases([]))
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [open, onClose])

  function go(path: string) {
    navigate(path)
    onClose()
  }

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-overlay pt-[15vh] animate-fade-in"
      onClick={onClose}
    >
      <div
        className="animate-slide-up w-full max-w-lg overflow-hidden rounded-xl border border-ink-200 bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <Command loop shouldFilter>
          <div className="flex items-center gap-2.5 border-b border-ink-100 px-4">
            <Search size={16} className="shrink-0 text-ink-400" />
            <Command.Input
              autoFocus
              placeholder="Search pages or paste a case ID…"
              className="w-full bg-transparent py-3.5 text-sm text-ink-900 outline-none placeholder:text-ink-400"
            />
            <kbd className="shrink-0 rounded border border-ink-200 px-1.5 py-0.5 text-[10px] font-medium text-ink-400">
              Esc
            </kbd>
          </div>

          <Command.List className="max-h-80 overflow-y-auto p-2">
            <Command.Empty className="py-6 text-center text-sm text-ink-400">No results.</Command.Empty>

            <Command.Group heading="Navigate" className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-ink-400 [&_[cmdk-group-items]]:mt-1">
              {STATIC_COMMANDS.map(({ to, label, icon: Icon, keywords }) => (
                <Command.Item
                  key={to}
                  value={label}
                  keywords={keywords}
                  onSelect={() => go(to)}
                  className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-ink-700 data-[selected=true]:bg-brand-50 data-[selected=true]:text-brand-700"
                >
                  <Icon size={15} className="shrink-0 text-ink-400" />
                  {label}
                </Command.Item>
              ))}
            </Command.Group>

            {recentCases.length > 0 && (
              <Command.Group heading="Recent cases" className="mt-2 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-ink-400 [&_[cmdk-group-items]]:mt-1">
                {recentCases.map((c) => (
                  <Command.Item
                    key={c.id}
                    value={`${c.reported_address} ${c.chain} ${c.id}`}
                    onSelect={() => go(`/cases/${c.id}`)}
                    className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-ink-700 data-[selected=true]:bg-brand-50 data-[selected=true]:text-brand-700"
                  >
                    <Clock size={15} className="shrink-0 text-ink-400" />
                    <span className="truncate font-mono text-xs">
                      {c.reported_address.slice(0, 14)}…{c.reported_address.slice(-6)}
                    </span>
                    <span className="ml-auto shrink-0 text-[11px] text-ink-400">{c.chain}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            )}
          </Command.List>
        </Command>
      </div>
    </div>
  )
}
