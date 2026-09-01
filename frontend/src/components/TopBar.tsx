import { ChevronRight, Fingerprint, Search } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { HashVerifierModal } from './HashVerifierModal'

const SECTION_LABELS: Record<string, string> = {
  '': 'Overview',
  cases: 'Cases',
  new: 'New Trace',
  bulk: 'Bulk Upload',
}

function useBreadcrumb() {
  const location = useLocation()
  const { caseId } = useParams<{ caseId?: string }>()
  const segments = location.pathname.split('/').filter(Boolean)

  if (segments.length === 0) return [{ label: 'Overview', to: '/' }]

  const crumbs = [{ label: 'Cases', to: '/cases' }]
  if (segments[0] === 'cases' && caseId) {
    crumbs.push({ label: `#${caseId.slice(0, 8)}`, to: `/cases/${caseId}` })
    return crumbs
  }
  const label = SECTION_LABELS[segments[0]] ?? segments[0]
  return [{ label, to: `/${segments[0]}` }]
}

export function TopBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  const crumbs = useBreadcrumb()
  const [hashModalOpen, setHashModalOpen] = useState(false)

  return (
    <>
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-ink-100 bg-surface px-8 shadow-2xs">
        <nav className="flex items-center gap-2 text-xs">
          {crumbs.map((crumb, i) => (
            <span key={crumb.to} className="flex items-center gap-2">
              {i > 0 && <ChevronRight size={13} className="text-ink-300" />}
              {i === crumbs.length - 1 ? (
                <span className="font-semibold text-ink-900">{crumb.label}</span>
              ) : (
                <Link to={crumb.to} className="font-medium text-ink-500 hover:text-brand-600 transition-colors">
                  {crumb.label}
                </Link>
              )}
            </span>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setHashModalOpen(true)}
            className="cursor-pointer flex items-center gap-1.5 rounded-lg border border-ink-200 bg-surface px-3 py-1.5 text-xs font-medium text-ink-700 shadow-2xs transition-colors hover:border-brand-500 hover:bg-brand-50 hover:text-brand-600"
          >
            <Fingerprint size={14} className="text-brand-600" />
            Verify Hash
          </button>

          <button
            onClick={onOpenPalette}
            className="cursor-pointer flex items-center gap-2 rounded-lg border border-ink-200 bg-surface px-3 py-1.5 text-xs font-medium text-ink-600 shadow-2xs transition-colors hover:border-brand-500 hover:bg-brand-50 hover:text-brand-600"
          >
            <Search size={14} className="text-ink-500" />
            <span>Search</span>
            <kbd className="rounded border border-ink-200 bg-ink-50 px-1.5 py-0.5 font-sans text-[10px] font-semibold text-ink-500">
              ⌘K
            </kbd>
          </button>
        </div>
      </header>

      <HashVerifierModal
        open={hashModalOpen}
        onClose={() => setHashModalOpen(false)}
      />
    </>
  )
}
