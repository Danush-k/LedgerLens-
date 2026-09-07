import { Repeat } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { CaseSummary } from '../types'

export function RelatedCases({ cases }: { cases: CaseSummary[] }) {
  if (cases.length === 0) return null

  return (
    <div className="rounded-md border border-warning/25 bg-risk-medium/[0.06] p-6">
      <div className="mb-3 flex items-center gap-1.5">
        <Repeat size={14} className="text-warning" />
        <h2 className="text-sm font-semibold text-warning">
          Reported in {cases.length} other case{cases.length === 1 ? '' : 's'}
        </h2>
      </div>
      <p className="mb-3 text-xs text-ink-600">
        This exact wallet has been independently reported before — a repeat-offender signal worth
        cross-referencing with the other complaint(s).
      </p>
      <ul className="space-y-1.5">
        {cases.map((c) => (
          <li key={c.id}>
            <Link
              to={`/cases/${c.id}`}
              className="flex items-center justify-between text-xs font-medium text-warning hover:underline"
            >
              <span>{new Date(c.created_at).toLocaleDateString([], { dateStyle: 'medium' })}</span>
              <span>{c.risk_score !== null ? `risk ${Math.round(c.risk_score)}` : c.status}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
