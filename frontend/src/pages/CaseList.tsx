import { ArrowUpRight, Download, Plus, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { listCases } from '../api/client'
import { ChainBadge } from '../components/ChainBadge'
import { StatusBadge } from '../components/StatusBadge'
import { TableRowSkeleton } from '../components/Skeleton'
import type { CaseFilters, CaseStatus, CaseSummary, Chain } from '../types'

function riskDot(score: number | null) {
  if (score === null) return 'bg-ink-300'
  if (score >= 70) return 'bg-red-500'
  if (score >= 35) return 'bg-amber-500'
  return 'bg-emerald-500'
}

const CHAINS: Chain[] = ['ethereum', 'bsc', 'polygon', 'bitcoin']
const STATUSES: CaseStatus[] = ['queued', 'tracing', 'complete', 'failed']

type SortKey = 'reported_address' | 'chain' | 'status' | 'risk_score' | 'created_at'

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'reported_address', label: 'Wallet' },
  { key: 'chain', label: 'Chain' },
  { key: 'status', label: 'Status' },
  { key: 'risk_score', label: 'Risk' },
  { key: 'created_at', label: 'Reported' },
]

function toCsv(cases: CaseSummary[]): string {
  const header = ['address', 'chain', 'status', 'risk_score', 'nearest_exchange', 'created_at']
  const rows = cases.map((c) => [
    c.reported_address,
    c.chain,
    c.status,
    c.risk_score ?? '',
    c.nearest_exchange?.name ?? '',
    c.created_at,
  ])
  return [header, ...rows].map((row) => row.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
}

export function CaseList() {
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [chain, setChain] = useState('')
  const [status, setStatus] = useState('')
  const [minRisk, setMinRisk] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('created_at')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const filters: CaseFilters = {
    ...(search.trim() && { search: search.trim() }),
    ...(chain && { chain }),
    ...(status && { status }),
    ...(minRisk && { min_risk: Number(minRisk) }),
  }
  const filterKey = JSON.stringify(filters)

  useEffect(() => {
    let active = true
    setLoading(true)
    const load = () => listCases(filters).then((data) => active && setCases(data))
    load().finally(() => active && setLoading(false))

    // Simple fixed-interval refresh so in-progress traces update live -
    // cheap enough at dashboard scale, no need for websockets yet.
    const interval = setInterval(load, 3500)
    return () => {
      active = false
      clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey])

  const sortedCases = useMemo(() => {
    const sorted = [...cases].sort((a, b) => {
      const dir = sortDir === 'asc' ? 1 : -1
      const av = a[sortKey]
      const bv = b[sortKey]
      if (av === null) return 1
      if (bv === null) return -1
      return av > bv ? dir : av < bv ? -dir : 0
    })
    return sorted
  }, [cases, sortKey, sortDir])

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  function exportCsv() {
    const blob = new Blob([toCsv(sortedCases)], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `fraudmap-cases-${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  const hasFilters = Boolean(search || chain || status || minRisk)

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-ink-900">Investigation cases</h1>
          <p className="mt-1 text-sm text-ink-500">
            Every wallet address traced through the attribution pipeline.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={exportCsv}
            disabled={sortedCases.length === 0}
            className="flex items-center gap-2 rounded-lg border border-ink-200 px-3.5 py-2.5 text-sm font-semibold text-ink-700 transition-colors hover:border-ink-300 disabled:opacity-40"
          >
            <Download size={15} />
            Export CSV
          </button>
          <Link
            to="/new"
            className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-brand-500/20 transition-colors hover:bg-brand-600"
          >
            <Plus size={16} />
            New trace
          </Link>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2.5">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by wallet address…"
            className="w-full rounded-lg border border-ink-200 bg-surface py-2 pl-9 pr-3 text-sm text-ink-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          />
        </div>
        <select
          value={chain}
          onChange={(e) => setChain(e.target.value)}
          className="rounded-lg border border-ink-200 bg-surface px-3 py-2 text-sm text-ink-700 outline-none focus:border-brand-500"
        >
          <option value="">All chains</option>
          {CHAINS.map((c) => (
            <option key={c} value={c}>
              {c[0].toUpperCase() + c.slice(1)}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-lg border border-ink-200 bg-surface px-3 py-2 text-sm text-ink-700 outline-none focus:border-brand-500"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s[0].toUpperCase() + s.slice(1)}
            </option>
          ))}
        </select>
        <select
          value={minRisk}
          onChange={(e) => setMinRisk(e.target.value)}
          className="rounded-lg border border-ink-200 bg-surface px-3 py-2 text-sm text-ink-700 outline-none focus:border-brand-500"
        >
          <option value="">Any risk</option>
          <option value="35">Medium+ (35+)</option>
          <option value="70">High only (70+)</option>
        </select>
        {hasFilters && (
          <button
            onClick={() => {
              setSearch('')
              setChain('')
              setStatus('')
              setMinRisk('')
            }}
            className="text-xs font-semibold text-ink-500 hover:text-brand-600"
          >
            Clear filters
          </button>
        )}
      </div>

      {loading ? (
        <div className="overflow-hidden rounded-xl border border-ink-100 bg-surface shadow-sm">
          <table className="w-full text-left text-sm">
            <tbody className="divide-y divide-ink-100">
              {Array.from({ length: 6 }).map((_, i) => <TableRowSkeleton key={i} columns={7} />)}
            </tbody>
          </table>
        </div>
      ) : cases.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-ink-300 py-24 text-center">
          <Search size={28} className="text-ink-300" />
          <p className="text-sm text-ink-500">
            {hasFilters ? 'No cases match these filters.' : 'No cases yet. Submit a wallet address to start tracing.'}
          </p>
          {!hasFilters && (
            <Link to="/new" className="text-sm font-semibold text-brand-600 hover:underline">
              Start a new trace →
            </Link>
          )}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-ink-100 bg-surface shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-ink-100 bg-ink-50 text-xs uppercase tracking-wide text-ink-500">
              <tr>
                {COLUMNS.map((col) => (
                  <th key={col.key} className="px-5 py-3 font-medium">
                    <button
                      onClick={() => toggleSort(col.key)}
                      className="flex items-center gap-1 transition-colors hover:text-ink-800"
                    >
                      {col.label}
                      {sortKey === col.key && <span className="text-brand-500">{sortDir === 'asc' ? '↑' : '↓'}</span>}
                    </button>
                  </th>
                ))}
                <th className="px-5 py-3 font-medium">Nearest exchange</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {sortedCases.map((c) => (
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
                  <td className="px-5 py-3.5 text-ink-500">
                    {new Date(c.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                  </td>
                  <td className="px-5 py-3.5 text-ink-700">
                    {c.nearest_exchange ? c.nearest_exchange.name : <span className="text-ink-400">—</span>}
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
