/**
 * Command centre.
 *
 * Opens with what needs a decision today, not with totals. A count of cases
 * is a vanity metric; a wallet collecting from four separate victims is a
 * lead, and it goes at the top.
 */
import {
  AlertTriangle, ArrowRight, Building2, Network, ShieldAlert,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { getAnalyticsOverview, getConvergence } from '../api/client'
import { HorizontalBars } from '../components/HorizontalBars'
import { LoadingRing } from '../components/Logo'
import {
  Address, EmptyState, Panel, Pill, RiskBadge, StatTile, StatusPill, Table, Td, Th,
} from '../components/ui/Primitives'
import type { AnalyticsOverview, ConvergenceResult } from '../types'
import { formatAmount } from '../utils/format'

export function Overview() {
  const [data, setData] = useState<AnalyticsOverview | null>(null)
  const [convergence, setConvergence] = useState<ConvergenceResult | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    Promise.all([getAnalyticsOverview(), getConvergence(2)])
      .then(([overview, conv]) => {
        if (cancelled) return
        setData(overview)
        setConvergence(conv)
      })
      .catch(() => !cancelled && toast.error('Could not load the command centre.'))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center py-24">
        <LoadingRing size={40} label="Loading case load…" />
      </div>
    )
  }

  if (!data) return null

  const inProgress = (data.by_status.queued ?? 0) + (data.by_status.tracing ?? 0)
  const convergencePoints = convergence?.convergence_points ?? []
  const topConvergence = convergencePoints.slice(0, 4)

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-5">
      <header className="mb-4">
        <h1 className="text-lg font-semibold text-ink-900">Command centre</h1>
        <p className="mt-0.5 text-[13px] text-ink-500">
          Case load and network posture across every trace on record.
        </p>
      </header>

      {/* Leads first. A convergence point is the only thing on this screen
          that names a specific next action. */}
      {topConvergence.length > 0 && (
        <Panel
          title="Convergence alerts"
          subtitle="Wallets receiving funds traced from more than one complaint"
          actions={
            <Link
              to="/network"
              className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline"
            >
              Network explorer <ArrowRight size={12} />
            </Link>
          }
          dense
        >
          <ul className="divide-y divide-ink-100">
            {topConvergence.map(point => (
              <li key={point.address} className="border-l-[3px] border-l-critical px-3.5 py-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <AlertTriangle size={14} className="text-critical" />
                    <Address address={point.address} chain={point.chain} />
                    <Pill tone="critical">{point.case_count} cases</Pill>
                    {point.min_hop === 0 && <Pill tone="warning">reported directly</Pill>}
                  </div>
                  <span className="tabular text-xs text-ink-600">
                    {formatAmount(point.total_value)} {point.chain} traced in
                  </span>
                </div>
                <p className="mt-1 text-xs text-ink-500">
                  Complaints:{' '}
                  {point.cases.map((c, i) => (
                    <span key={c.case_id}>
                      {i > 0 && ', '}
                      <Link to={`/cases/${c.case_id}`} className="text-brand-600 hover:underline">
                        {c.complaint_ref ?? `#${c.case_id.slice(0, 8)}`}
                      </Link>
                    </span>
                  ))}
                </p>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className={`grid grid-cols-2 gap-px overflow-hidden rounded-md border border-ink-200 bg-ink-200 sm:grid-cols-5 ${topConvergence.length > 0 ? 'mt-3' : ''}`}>
        <StatTile label="Total cases" value={data.total_cases} sub={`${inProgress} in progress`} />
        <StatTile
          label="High risk"
          value={data.risk_buckets.high}
          sub="score ≥ 70"
          tone={data.risk_buckets.high > 0 ? 'critical' : 'neutral'}
        />
        <StatTile
          label="Exchange identified"
          value={`${data.exchange_found_rate}%`}
          sub={`${data.exchange_found_count} of ${data.total_cases}`}
          tone={data.exchange_found_rate > 0 ? 'good' : 'neutral'}
        />
        <StatTile
          label="Avg risk"
          value={data.avg_risk_score ?? '—'}
          sub={data.avg_risk_score === null ? 'no scored cases' : 'across scored cases'}
        />
        <StatTile
          label="Convergence"
          value={convergence?.count ?? 0}
          sub="shared wallets"
          tone={(convergence?.count ?? 0) > 0 ? 'critical' : 'neutral'}
        />
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <Panel title="Risk distribution" subtitle="Rule-based score, by band">
          {data.total_cases === 0 ? (
            <EmptyState title="No cases traced yet" />
          ) : (
            <HorizontalBars
              items={[
                { label: 'High (≥70)', value: data.risk_buckets.high, color: 'var(--color-risk-high)' },
                { label: 'Medium (35–69)', value: data.risk_buckets.medium, color: 'var(--color-risk-medium)' },
                { label: 'Low (<35)', value: data.risk_buckets.low, color: 'var(--color-risk-low)' },
              ]}
            />
          )}
        </Panel>

        <Panel title="Cases by chain">
          {Object.keys(data.by_chain).length === 0 ? (
            <EmptyState title="No cases traced yet" />
          ) : (
            <HorizontalBars
              items={Object.entries(data.by_chain).map(([label, value]) => ({ label, value }))}
            />
          )}
        </Panel>

        <Panel
          title="Fraud typologies"
          subtitle="Classified from the complaint narrative"
        >
          {Object.keys(data.typology_counts).length === 0 ? (
            <EmptyState
              title="No cases tagged yet"
              detail="Typology is derived from the complaint narrative — add one when submitting a trace."
            />
          ) : (
            <HorizontalBars
              items={Object.entries(data.typology_counts)
                .map(([label, value]) => ({ label: label.replace(/_/g, ' '), value }))}
            />
          )}
        </Panel>

        <Panel title="Destination exchanges" subtitle="Where traced funds resolved">
          {data.top_exchanges.length === 0 ? (
            <EmptyState
              icon={<Building2 size={22} />}
              title="No exchange identified yet"
              detail="An exchange appears here once a trace resolves to a labelled deposit address."
            />
          ) : (
            <HorizontalBars
              items={data.top_exchanges.map(e => ({ label: e.name, value: e.count }))}
            />
          )}
        </Panel>
      </div>

      <div className="mt-3">
        <Panel
          title="Recent high-risk cases"
          subtitle="Score ≥ 50, newest first"
          actions={
            <Link to="/cases" className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline">
              All cases <ArrowRight size={12} />
            </Link>
          }
          dense
        >
          {data.recent_high_risk.length === 0 ? (
            <EmptyState
              icon={<ShieldAlert size={22} />}
              title="No high-risk cases"
              detail="Nothing has scored 50 or above yet. This reflects the cases traced so far, not an absence of risk."
            />
          ) : (
            <Table head={<><Th>Reported wallet</Th><Th>Chain</Th><Th>Status</Th><Th>Risk</Th><Th>Exchange</Th></>}>
              {data.recent_high_risk.map(c => (
                <tr key={c.id} className="border-b border-ink-100 last:border-0 hover:bg-ink-50">
                  <Td>
                    <Link to={`/cases/${c.id}`} className="text-brand-600 hover:underline">
                      <Address address={c.reported_address} link={false} />
                    </Link>
                  </Td>
                  <Td><Pill>{c.chain}</Pill></Td>
                  <Td><StatusPill status={c.status} /></Td>
                  <Td><RiskBadge score={c.risk_score} showBar /></Td>
                  <Td className="text-ink-600">
                    {c.nearest_exchange
                      ? `${c.nearest_exchange.name} · hop ${c.nearest_exchange.hops}`
                      : <span className="text-ink-400">not identified</span>}
                  </Td>
                </tr>
              ))}
            </Table>
          )}
        </Panel>
      </div>

      {data.total_cases === 0 && (
        <div className="mt-3">
          <Panel>
            <EmptyState
              icon={<Network size={26} />}
              title="No traces on record"
              detail="Submit a wallet address under New trace to begin. Cross-case intelligence needs at least two completed traces before it can find anything."
            />
          </Panel>
        </div>
      )}
    </div>
  )
}
