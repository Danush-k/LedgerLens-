/**
 * Network Explorer — the cross-case view.
 *
 * Every other screen in this application is scoped to one complaint. This
 * one asks what the whole body of cases says collectively: which wallets
 * collect from several victims, and which addresses are controlled by the
 * same actor. Neither question is answerable from a single case file, which
 * is the entire reason this screen exists.
 */
import { GitMerge, Info, Network, Search, Users } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { getConvergence, getEntities } from '../api/client'
import { ChainMark } from '../components/ChainMark'
import { LoadingRing } from '../components/Logo'
import {
  Address,
  EmptyState,
  Panel,
  Pill,
  RiskBadge,
  StatTile,
  Table,
  Td,
  Th,
} from '../components/ui/Primitives'
import type { ConvergencePoint, ConvergenceResult, Entity, EntityResult } from '../types'
import { formatAmount } from '../utils/format'

type Tab = 'convergence' | 'entities'

export function NetworkExplorer() {
  const [tab, setTab] = useState<Tab>('convergence')
  const [convergence, setConvergence] = useState<ConvergenceResult | null>(null)
  const [entities, setEntities] = useState<EntityResult | null>(null)
  const [minCases, setMinCases] = useState(2)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([getConvergence(minCases), getEntities()])
      .then(([c, e]) => {
        if (cancelled) return
        setConvergence(c)
        setEntities(e)
      })
      .catch(() => {
        if (!cancelled) toast.error('Could not load network intelligence.')
      })
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [minCases])

  const points = useMemo(() => {
    const all = convergence?.convergence_points ?? []
    if (!query.trim()) return all
    const q = query.trim().toLowerCase()
    return all.filter(p =>
      p.address.toLowerCase().includes(q) ||
      p.cases.some(c => c.reported_address.toLowerCase().includes(q) ||
                        (c.complaint_ref ?? '').toLowerCase().includes(q)))
  }, [convergence, query])

  const filteredEntities = useMemo(() => {
    const all = entities?.entities ?? []
    if (!query.trim()) return all
    const q = query.trim().toLowerCase()
    return all.filter(e =>
      e.addresses.some(a => a.toLowerCase().includes(q)) ||
      e.entity_id.toLowerCase().includes(q))
  }, [entities, query])

  const multiCaseEntities = (entities?.entities ?? []).filter(e => e.case_count > 1).length
  const totalConverged = (convergence?.convergence_points ?? [])
    .reduce((sum, p) => sum + p.total_value, 0)

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-5">
      <header className="mb-4">
        <h1 className="text-lg font-semibold text-ink-900">Network Explorer</h1>
        <p className="mt-0.5 text-[13px] text-ink-500">
          Structure that only appears when cases are read together — shared wallets
          across complaints, and addresses proven to share an owner.
        </p>
      </header>

      <div className="mb-4 grid grid-cols-2 gap-px overflow-hidden rounded-md border border-ink-200 bg-ink-200 sm:grid-cols-4">
        <StatTile
          label="Convergence points"
          value={convergence?.count ?? '—'}
          sub={`wallets in ≥${minCases} cases`}
          tone={convergence?.count ? 'critical' : 'neutral'}
        />
        <StatTile
          label="Value converged"
          value={totalConverged ? formatAmount(totalConverged) : '—'}
          sub="traced into shared wallets"
        />
        <StatTile
          label="Resolved entities"
          value={entities?.count ?? '—'}
          sub="address groups, one owner each"
        />
        <StatTile
          label="Multi-case entities"
          value={multiCaseEntities || '—'}
          sub="actors spanning complaints"
          tone={multiCaseEntities ? 'warning' : 'neutral'}
        />
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="flex rounded-md border border-ink-200 bg-surface p-0.5">
          {([['convergence', 'Convergence', Network], ['entities', 'Entities', Users]] as const)
            .map(([key, label, Icon]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`flex cursor-pointer items-center gap-1.5 rounded px-3 py-1.5 text-[13px] font-medium transition-colors ${
                  tab === key
                    ? 'bg-brand-500 text-white'
                    : 'text-ink-600 hover:bg-ink-50 hover:text-ink-900'
                }`}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
        </div>

        <div className="relative min-w-[220px] flex-1">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-400" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Filter by address, entity or complaint reference…"
            className="w-full rounded-md border border-ink-200 bg-surface py-1.5 pl-8 pr-3 text-[13px] text-ink-900 outline-none placeholder:text-ink-400 focus:border-brand-500"
          />
        </div>

        {tab === 'convergence' && (
          <label className="flex items-center gap-2 text-xs text-ink-600">
            Minimum cases
            <select
              value={minCases}
              onChange={e => setMinCases(Number(e.target.value))}
              className="cursor-pointer rounded-md border border-ink-200 bg-surface px-2 py-1.5 text-[13px] text-ink-900 outline-none focus:border-brand-500"
            >
              {[2, 3, 4, 5].map(n => <option key={n} value={n}>{n}+</option>)}
            </select>
          </label>
        )}
      </div>

      {loading ? (
        <div className="rounded-md border border-ink-200 bg-surface py-16">
          <LoadingRing size={40} label="Correlating cases…" />
        </div>
      ) : tab === 'convergence' ? (
        <ConvergenceTab points={points} note={convergence?.note} minCases={minCases} />
      ) : (
        <EntitiesTab entities={filteredEntities} note={entities?.note} />
      )}
    </div>
  )
}

function ConvergenceTab({ points, note, minCases }: {
  points: ConvergencePoint[]
  note?: string
  minCases: number
}) {
  if (points.length === 0) {
    return (
      <Panel>
        <EmptyState
          icon={<Network size={26} />}
          title={`No wallet has received funds from ${minCases} or more separate cases`}
          detail={note ?? 'Convergence needs at least two completed traces before it can find anything.'}
        />
      </Panel>
    )
  }

  return (
    <div className="grid gap-3">
      {points.map(point => (
        <ConvergenceCard key={`${point.chain}:${point.address}`} point={point} />
      ))}
    </div>
  )
}

function ConvergenceCard({ point }: { point: ConvergencePoint }) {
  return (
    <Panel dense>
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-ink-200 px-3.5 py-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <ChainMark chain={point.chain} size={16} />
            <Address address={point.address} chain={point.chain} short={false} />
            {point.label_name && (
              <span className="text-[11px] text-ink-500">· {point.label_name}</span>
            )}
          </div>
          <p className="mt-1 text-xs text-ink-500">
            Closest approach hop {point.min_hop}
            {point.min_hop === 0 && ' — reported directly by a complainant'}
          </p>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-right">
            <p className="tabular text-[17px] font-semibold leading-none text-ink-900">
              {point.case_count}
            </p>
            <p className="mt-0.5 text-[10px] uppercase tracking-wide text-ink-500">complaints</p>
          </div>
          <div className="text-right">
            <p className="tabular text-[17px] font-semibold leading-none text-ink-900">
              {formatAmount(point.total_value)}
            </p>
            <p className="mt-0.5 text-[10px] uppercase tracking-wide text-ink-500">traced in</p>
          </div>
        </div>
      </div>

      <Table
        head={<>
          <Th>Complaint</Th><Th>Reported wallet</Th><Th>Typology</Th>
          <Th className="text-right">Hop</Th><Th className="text-right">Value in</Th><Th>Risk</Th>
        </>}
      >
        {point.cases.map(c => (
          <tr key={c.case_id} className="border-b border-ink-100 last:border-0 hover:bg-ink-50">
            <Td>
              <Link to={`/cases/${c.case_id}`} className="font-medium text-brand-600 hover:underline">
                {c.complaint_ref ?? `#${c.case_id.slice(0, 8)}`}
              </Link>
            </Td>
            <Td><Address address={c.reported_address} chain={point.chain} /></Td>
            <Td className="text-ink-600">{c.fraud_typology?.replace(/_/g, ' ') ?? '—'}</Td>
            <Td className="tabular text-right text-ink-700">{c.hop}</Td>
            <Td className="tabular text-right text-ink-700">{formatAmount(c.value_in)}</Td>
            <Td><RiskBadge score={c.risk_score} /></Td>
          </tr>
        ))}
      </Table>

      <div className="flex gap-2 border-t border-ink-200 bg-surface-sunk px-3.5 py-2.5">
        <Info size={13} className="mt-0.5 shrink-0 text-ink-400" />
        <p className="text-xs leading-relaxed text-ink-600">{point.evidence}</p>
      </div>
    </Panel>
  )
}

function EntitiesTab({ entities, note }: { entities: Entity[]; note?: string }) {
  if (entities.length === 0) {
    return (
      <Panel>
        <EmptyState
          icon={<Users size={26} />}
          title="No entities resolved yet"
          detail={note ?? 'Entities form when addresses are spent together as inputs to one transaction, which proves a shared key holder. Trace more cases to accumulate that evidence.'}
        />
      </Panel>
    )
  }

  return (
    <div className="grid gap-3">
      {entities.map(entity => (
        <Panel key={entity.entity_id} dense>
          <div className={`flex flex-wrap items-start justify-between gap-3 border-b border-ink-200 px-3.5 py-3 ${
            entity.likely_service ? 'opacity-70' : ''
          }`}>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <GitMerge size={15} className={entity.likely_service ? 'text-ink-400' : 'text-brand-600'} />
                <span className="addr text-[13px] font-semibold text-ink-900">{entity.entity_id}</span>
                {/* An oversized cluster must never read as a suspect. */}
                {entity.likely_service
                  ? <Pill tone="neutral" title="Too large to be one person - almost certainly an exchange or custodial service">
                      likely service infrastructure
                    </Pill>
                  : entity.case_count > 1 && (
                      <Pill tone="warning">spans {entity.case_count} cases</Pill>
                    )}
                {entity.labels.map(l => <Pill key={l} tone="info">{l}</Pill>)}
              </div>
              <p className="mt-1 text-xs text-ink-500">
                {entity.address_count.toLocaleString()} addresses under one key holder
                {entity.complaint_refs.length > 0 && ` · ${entity.complaint_refs.join(', ')}`}
              </p>
            </div>
            <div className="text-right">
              <p className="tabular text-lg font-semibold leading-none text-ink-900">
                {formatAmount(entity.tainted_value)}
              </p>
              <p className="text-[11px] text-ink-500">{entity.chain} traced</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-1.5 px-3.5 py-3">
            {entity.addresses.slice(0, 40).map(a => (
              <span key={a} className="rounded border border-ink-200 bg-surface-sunk px-1.5 py-1">
                <Address address={a} chain={entity.chain} />
              </span>
            ))}
            {entity.addresses.length > 40 && (
              <span className="self-center text-xs text-ink-500">
                +{(entity.addresses.length - 40).toLocaleString()} more
              </span>
            )}
          </div>

          {entity.possible_associates.length > 0 && (
            <div className="border-t border-ink-100 px-3.5 py-2.5">
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                Possible associates — weaker signal, not merged
              </p>
              <div className="flex flex-wrap gap-1.5">
                {entity.possible_associates.slice(0, 12).map(a => (
                  <span key={a} className="rounded border border-dashed border-ink-300 px-1.5 py-1">
                    <Address address={a} chain={entity.chain} link={false} />
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-2 border-t border-ink-200 bg-surface-sunk px-3.5 py-2.5">
            <Info size={13} className="mt-0.5 shrink-0 text-ink-400" />
            <p className="text-xs leading-relaxed text-ink-600">{entity.evidence}</p>
          </div>
        </Panel>
      ))}
    </div>
  )
}
