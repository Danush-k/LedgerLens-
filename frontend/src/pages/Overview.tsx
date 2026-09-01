import { AlertTriangle, FolderSearch, Landmark, Percent } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAnalyticsOverview } from '../api/client'
import { CardSkeleton, StatTileSkeleton } from '../components/Skeleton'
import { ChainBadge } from '../components/ChainBadge'
import { HorizontalBars } from '../components/HorizontalBars'
import { StatTile } from '../components/StatTile'
import type { AnalyticsOverview } from '../types'

// Categorical slots from the validated reference palette, referenced via CSS
// custom properties (see index.css) so they flip correctly in dark mode -
// fixed order, not cycled, so a chain's color stays stable regardless of
// what else is shown.
const CHAIN_COLORS: Record<string, string> = {
  ethereum: 'var(--chart-blue)',
  bitcoin: 'var(--chart-orange)',
  polygon: 'var(--chart-aqua)',
  bsc: 'var(--chart-yellow)',
}

// Status colors (fixed roles, theme-reactive values) - risk bands are a state, not an identity.
const RISK_COLORS = {
  low: 'var(--color-risk-low)',
  medium: 'var(--color-risk-medium)',
  high: 'var(--color-risk-high)',
}

const CHAIN_LABELS: Record<string, string> = { ethereum: 'Ethereum', bitcoin: 'Bitcoin', polygon: 'Polygon', bsc: 'BSC' }

const TYPOLOGY_LABELS: Record<string, string> = {
  investment_scam: 'Investment scam',
  task_based_fraud: 'Task-based fraud',
  sextortion: 'Sextortion',
  ransomware: 'Ransomware',
  phishing: 'Phishing',
  darknet: 'Darknet',
  unclassified: 'Unclassified',
}
// Categorical slot 5 (chains already claimed slots 1-4).
const TYPOLOGY_COLOR = 'var(--chart-magenta)'

export function Overview() {
  const [data, setData] = useState<AnalyticsOverview | null>(null)

  useEffect(() => {
    let active = true
    const load = () => getAnalyticsOverview().then((d) => active && setData(d))
    load()
    const interval = setInterval(load, 5000)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [])

  if (!data) {
    return (
      <div className="mx-auto max-w-6xl px-8 py-8">
        <div className="mb-2 h-7 w-32 animate-skeleton rounded-md bg-ink-200" />
        <div className="mb-6 h-4 w-72 animate-skeleton rounded-md bg-ink-200" />
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <StatTileSkeleton key={i} />)}
        </div>
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} lines={3} />)}
        </div>
      </div>
    )
  }

  const flagItems = Object.entries(data.flag_counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([flag, count]) => ({ label: flag.replace(/_/g, ' '), value: count, color: 'var(--color-brand-500)' }))

  const chainItems = Object.entries(data.by_chain).map(([chain, count]) => ({
    label: CHAIN_LABELS[chain] ?? chain,
    value: count,
    color: CHAIN_COLORS[chain] ?? 'var(--color-ink-500)',
  }))

  const typologyItems = Object.entries(data.typology_counts)
    .sort((a, b) => b[1] - a[1])
    .map(([typology, count]) => ({
      label: TYPOLOGY_LABELS[typology] ?? typology.replace(/_/g, ' '),
      value: count,
      color: TYPOLOGY_COLOR,
    }))

  const riskItems = [
    { label: 'Low (0-34)', value: data.risk_buckets.low, color: RISK_COLORS.low },
    { label: 'Medium (35-69)', value: data.risk_buckets.medium, color: RISK_COLORS.medium },
    { label: 'High (70-100)', value: data.risk_buckets.high, color: RISK_COLORS.high },
  ]

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <h1 className="text-xl font-bold text-ink-900">Overview</h1>
      <p className="mt-1 text-sm text-ink-500">Portfolio-level intelligence across every traced case.</p>

      <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="Total cases" value={String(data.total_cases)} icon={<FolderSearch size={16} />} />
        <StatTile
          label="Exchange ID rate"
          value={`${data.exchange_found_rate}%`}
          hint={`${data.exchange_found_count} of ${data.total_cases} resolved`}
          icon={<Landmark size={16} />}
        />
        <StatTile
          label="Avg risk score"
          value={data.avg_risk_score !== null ? String(data.avg_risk_score) : '—'}
          icon={<Percent size={16} />}
        />
        <StatTile
          label="High-risk cases"
          value={String(data.risk_buckets.high)}
          hint="score ≥ 70"
          icon={<AlertTriangle size={16} />}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-ink-100 bg-surface p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-ink-800">Risk distribution</h2>
          <HorizontalBars items={riskItems} />
        </div>

        <div className="rounded-xl border border-ink-100 bg-surface p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-ink-800">Cases by chain</h2>
          {chainItems.length > 0 ? (
            <HorizontalBars items={chainItems} />
          ) : (
            <p className="py-6 text-center text-sm text-ink-400">No cases yet.</p>
          )}
        </div>

        <div className="rounded-xl border border-ink-100 bg-surface p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-ink-800">Most common flags</h2>
          {flagItems.length > 0 ? (
            <HorizontalBars items={flagItems} />
          ) : (
            <p className="py-6 text-center text-sm text-ink-400">No flags raised yet.</p>
          )}
        </div>

        <div className="rounded-xl border border-ink-100 bg-surface p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-ink-800">Fraud typologies</h2>
          {typologyItems.length > 0 ? (
            <HorizontalBars items={typologyItems} />
          ) : (
            <p className="py-6 text-center text-sm text-ink-400">
              No cases tagged yet — add a complaint narrative when submitting a trace.
            </p>
          )}
        </div>

        <div className="rounded-xl border border-ink-100 bg-surface p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-ink-800">Top identified exchanges</h2>
          {data.top_exchanges.length > 0 ? (
            <ul className="space-y-2.5">
              {data.top_exchanges.map((ex) => (
                <li key={ex.name} className="flex items-center justify-between text-sm">
                  <span className="font-medium text-ink-800">{ex.name}</span>
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                    {ex.count} case{ex.count === 1 ? '' : 's'}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-ink-400">No exchange identified yet.</p>
          )}
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-ink-100 bg-surface p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold text-ink-800">Recent high-risk cases</h2>
        {data.recent_high_risk.length > 0 ? (
          <div className="divide-y divide-ink-100">
            {data.recent_high_risk.map((c) => (
              <Link
                key={c.id}
                to={`/cases/${c.id}`}
                className="flex items-center justify-between gap-4 py-3 text-sm transition-colors hover:bg-ink-50/60"
              >
                <span className="font-mono text-xs text-ink-800">
                  {c.reported_address.slice(0, 12)}…{c.reported_address.slice(-8)}
                </span>
                <ChainBadge chain={c.chain} />
                <span className="flex items-center gap-1.5 font-semibold text-red-600">
                  <span className="h-2 w-2 rounded-full bg-red-500" />
                  {Math.round(c.risk_score ?? 0)}
                </span>
                <span className="flex-1 text-right text-ink-500">
                  {c.nearest_exchange ? c.nearest_exchange.name : 'No exchange found'}
                </span>
              </Link>
            ))}
          </div>
        ) : (
          <p className="py-6 text-center text-sm text-ink-400">No high-risk cases (score ≥ 50) yet.</p>
        )}
      </div>
    </div>
  )
}
