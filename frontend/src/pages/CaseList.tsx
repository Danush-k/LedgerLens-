import { ArrowUpRight, Plus, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listCases } from '../api/client'
import { ChainBadge } from '../components/ChainBadge'
import { StatusBadge } from '../components/StatusBadge'
import type { CaseSummary } from '../types'

function riskDot(score: number | null) {
  if (score === null) return 'bg-ink-300'
  if (score >= 70) return 'bg-red-500'
  if (score >= 35) return 'bg-amber-500'
  return 'bg-emerald-500'
}

export function CaseList() {
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const load = () => listCases().then((data) => active && setCases(data))
    load().finally(() => setLoading(false))

    // Simple fixed-interval refresh so in-progress traces update live -
    // cheap enough at dashboard scale, no need for websockets yet.
    const interval = setInterval(load, 3500)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [])

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-ink-900">Investigation cases</h1>
          <p className="mt-1 text-sm text-ink-500">
            Every wallet address traced through the attribution pipeline.
          </p>
        </div>
        <Link
          to="/new"
          className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-brand-500/20 transition-colors hover:bg-brand-600"
        >
          <Plus size={16} />
          New trace
        </Link>
      </div>

      {loading ? (
        <div className="py-24 text-center text-sm text-ink-500">Loading cases…</div>
      ) : cases.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-ink-300 py-24 text-center">
          <Search size={28} className="text-ink-300" />
          <p className="text-sm text-ink-500">No cases yet. Submit a wallet address to start tracing.</p>
          <Link to="/new" className="text-sm font-semibold text-brand-600 hover:underline">
            Start a new trace →
          </Link>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-ink-100 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-ink-100 bg-ink-50/60 text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-5 py-3 font-medium">Wallet</th>
                <th className="px-5 py-3 font-medium">Chain</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Risk</th>
                <th className="px-5 py-3 font-medium">Nearest exchange</th>
                <th className="px-5 py-3 font-medium">Reported</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {cases.map((c) => (
                <tr key={c.id} className="transition-colors hover:bg-ink-50/60">
                  <td className="px-5 py-3.5 font-mono text-xs text-ink-800">
                    {c.reported_address.slice(0, 10)}…{c.reported_address.slice(-8)}
                  </td>
                  <td className="px-5 py-3.5">
                    <ChainBadge chain={c.chain} />
                  </td>
                  <td className="px-5 py-3.5">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-5 py-3.5">
                    {c.risk_score !== null ? (
                      <span className="flex items-center gap-1.5 font-medium text-ink-800">
                        <span className={`h-2 w-2 rounded-full ${riskDot(c.risk_score)}`} />
                        {Math.round(c.risk_score)}
                      </span>
                    ) : (
                      <span className="text-ink-400">—</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5 text-ink-700">
                    {c.nearest_exchange ? c.nearest_exchange.name : <span className="text-ink-400">—</span>}
                  </td>
                  <td className="px-5 py-3.5 text-ink-500">
                    {new Date(c.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <Link
                      to={`/cases/${c.id}`}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:underline"
                    >
                      View <ArrowUpRight size={13} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
