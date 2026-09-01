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
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-ink-100 bg-surface px-6">
        <nav className="flex items-center gap-1.5 text-xs">
          {crumbs.map((crumb, i) => (
            <span key={crumb.to} className="flex items-center gap-1.5">
              {i > 0 && <ChevronRight size={13} className="text-ink-300" />}
              {i === crumbs.length - 1 ? (
                <span className="font-medium text-ink-800">{crumb.label}</span>
              ) : (
                <Link to={crumb.to} className="text-ink-500 hover:text-brand-600">
                  {crumb.label}
                </Link>
              )}
            </span>
          ))}
        </nav>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setHashModalOpen(true)}
            className="flex items-center gap-1.5 rounded-md border border-ink-200 bg-ink-50 px-2.5 py-1 text-xs text-ink-500 transition-colors hover:border-brand-500 hover:bg-surface hover:text-brand-600"
          >
            <Fingerprint size={13} />
            Verify Hash
          </button>

          <button
            onClick={onOpenPalette}
            className="flex items-center gap-2 rounded-md border border-ink-200 bg-ink-50 px-2.5 py-1 text-xs text-ink-400 transition-colors hover:border-ink-300 hover:text-ink-600"
          >
            <Search size={13} />
            Search
            <kbd className="rounded border border-ink-200 bg-surface px-1 py-px font-sans text-[10px] text-ink-400">
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
