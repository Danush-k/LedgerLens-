/**
 * Suspects: the wallets that matter, why, and the officer's ruling on each.
 *
 * This replaces reading the graph. Every row says what the wallet is in
 * plain words, how much of the victim's money it touched and the strongest
 * reason it is here; opening it shows every reason with the transactions
 * behind it and what to do next.
 *
 * The ranking is the system's; the decision is the officer's. Nothing goes
 * into the suspect report until someone confirms it, and dismissing a wallet
 * keeps it visible - so a ruling can be revisited instead of silently lost.
 */
import {
  AlertTriangle,
  ArrowDownToLine,
  ArrowRightLeft,
  Check,
  ChevronDown,
  CircleDashed,
  Crosshair,
  ExternalLink,
  FileText,
  Flag,
  GitMerge,
  Landmark,
  Link2,
  Loader2,
  Plus,
  Radio,
  RotateCcw,
  Shuffle,
  Split,
  Users,
  Wallet,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { decideSuspect, describeDownloadError, downloadSuspectReport } from '../api/client'
import type { EvidenceTx, Suspect, SuspectRole, SuspectsResult, SuspectStatus } from '../types'
import { explorerTxUrl } from '../utils/explorer'
import { formatChainAmount } from '../utils/format'
import { Address, EmptyState, Pill } from './ui/Primitives'

export type SuspectFilter = 'all' | 'pending' | 'confirmed' | 'dismissed' | 'holding'

interface Props {
  caseId: string
  result: SuspectsResult | null
  loading: boolean
  filter: SuspectFilter
  onFilterChange: (filter: SuspectFilter) => void
  onChanged: () => void
  onLocate: (address: string) => void
}

const ROLE_ICON: Record<SuspectRole, typeof Flag> = {
  reported: Flag,
  cashout: Landmark,
  holding: Wallet,
  collector: GitMerge,
  distributor: Split,
  relay: ArrowRightLeft,
  mixer_user: Shuffle,
  untraced: CircleDashed,
  recipient: ArrowDownToLine,
}

const PRIORITY_TONE = { high: 'critical', medium: 'warning', low: 'neutral' } as const
const PRIORITY_BAR = { high: 'bg-critical', medium: 'bg-warning', low: 'bg-ink-400' } as const

function when(ts: number | null) {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString(undefined, {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function uniqueByHash(transactions: EvidenceTx[]): EvidenceTx[] {
  return [...new Map(transactions.map(tx => [tx.tx_hash, tx])).values()]
}

function shortHash(hash: string) {
  return hash.length > 18 ? `${hash.slice(0, 10)}…${hash.slice(-6)}` : hash
}

function DecisionBadge({ suspect }: { suspect: Suspect }) {
  const { status, decided_by } = suspect.decision
  if (status === 'confirmed') {
    return <Pill tone="critical" title={decided_by ? `Confirmed by ${decided_by}` : undefined}><Check size={11} /> Confirmed</Pill>
  }
  if (status === 'dismissed') {
    return <Pill tone="neutral" title={decided_by ? `Dismissed by ${decided_by}` : undefined}><X size={11} /> Dismissed</Pill>
  }
  return null  // the Confirm / Dismiss buttons already say it needs a decision
}

function SuspectRow({ caseId, suspect, expanded, onToggle, onChanged, onLocate }: {
  caseId: string
  suspect: Suspect
  expanded: boolean
  onToggle: () => void
  onChanged: () => void
  onLocate: (address: string) => void
}) {
  const [note, setNote] = useState(suspect.decision.note ?? '')
  const [saving, setSaving] = useState<SuspectStatus | null>(null)
  const RoleIcon = ROLE_ICON[suspect.role] ?? ArrowDownToLine
  const status = suspect.decision.status
  const amount = (value: number) => formatChainAmount(value, suspect.chain)
  const topReason = suspect.reasons.find(r => r.kind === 'signal')
  const signals = suspect.reasons.filter(r => r.kind === 'signal')
  const caveats = suspect.reasons.filter(r => r.kind === 'caveat')

  useEffect(() => setNote(suspect.decision.note ?? ''), [suspect.decision.note])

  async function decide(next: SuspectStatus) {
    setSaving(next)
    try {
      await decideSuspect(caseId, suspect.address, next, note)
      toast.success(
        next === 'confirmed' ? 'Suspect confirmed — it will appear in the report'
        : next === 'dismissed' ? 'Suspect dismissed — it will be left out of the report'
        : 'Returned to review',
      )
      onChanged()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      toast.error(detail ?? 'Could not save the decision')
    } finally {
      setSaving(null)
    }
  }

  const decisionButtons = status === 'pending' ? (
    <>
      <button
        type="button"
        onClick={() => decide('confirmed')}
        disabled={saving !== null}
        className="inline-flex cursor-pointer items-center gap-1 rounded-md bg-ink-900 px-2.5 py-1.5 text-xs font-semibold text-surface transition-opacity hover:opacity-85 disabled:cursor-wait disabled:opacity-60"
      >
        {saving === 'confirmed' ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
        Confirm
      </button>
      <button
        type="button"
        onClick={() => decide('dismissed')}
        disabled={saving !== null}
        className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-ink-200 bg-surface px-2.5 py-1.5 text-xs font-medium text-ink-700 transition-colors hover:border-ink-400 disabled:cursor-wait disabled:opacity-60"
      >
        {saving === 'dismissed' ? <Loader2 size={13} className="animate-spin" /> : <X size={13} />}
        Dismiss
      </button>
    </>
  ) : (
    <button
      type="button"
      onClick={() => decide('pending')}
      disabled={saving !== null}
      className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-ink-200 bg-surface px-2.5 py-1.5 text-xs font-medium text-ink-600 transition-colors hover:border-ink-400 disabled:cursor-wait disabled:opacity-60"
    >
      {saving ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
      Undo
    </button>
  )

  return (
    <li className={`border-l-[3px] ${
      status === 'confirmed' ? 'border-l-critical bg-critical-soft/25'
      : status === 'dismissed' ? 'border-l-ink-200 opacity-70'
      : 'border-l-transparent'
    }`}>
      {/* Summary line */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 lg:flex-nowrap">
        <span className="tabular w-6 shrink-0 text-center text-xs font-semibold text-ink-400">
          {suspect.rank}
        </span>

        <div className="flex w-[92px] shrink-0 flex-col gap-1">
          <Pill tone={PRIORITY_TONE[suspect.priority]}>{suspect.priority} priority</Pill>
          <div className="h-1 w-full overflow-hidden rounded-full bg-ink-200" title={`Suspicion score ${suspect.score}/100`}>
            <div className={`h-full ${PRIORITY_BAR[suspect.priority]}`} style={{ width: `${suspect.score}%` }} />
          </div>
        </div>

        <div className="min-w-0 flex-1 basis-64">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-ink-900">
              <RoleIcon size={14} className="text-ink-500" aria-hidden="true" />
              {suspect.role_title}
              {suspect.exchange_name && <span className="font-normal text-ink-500">· {suspect.exchange_name}</span>}
            </span>
            <Address address={suspect.address} chain={suspect.chain} />
            {suspect.linked_cases.length > 0 && (
              <span className="inline-flex items-center gap-1 rounded bg-intel-soft px-1.5 py-0.5 text-[10px] font-semibold text-intel">
                <Users size={11} /> {suspect.linked_cases.length} other complaint{suspect.linked_cases.length === 1 ? '' : 's'}
              </span>
            )}
            {suspect.detected_live && (
              <span className="inline-flex items-center gap-1 rounded bg-warning-soft px-1.5 py-0.5 text-[10px] font-semibold text-warning">
                <Radio size={11} /> Active after trace
              </span>
            )}
          </div>
          {topReason && (
            <p className="mt-1 line-clamp-1 text-xs text-ink-600" title={topReason.text}>{topReason.text}</p>
          )}
        </div>

        <div className="w-[120px] shrink-0 text-right">
          <p className="tabular text-[13px] font-semibold text-ink-900">
            {amount(suspect.victim_funds)}
          </p>
          <p className="text-[11px] text-ink-500">{Math.round(suspect.victim_share * 100)}% of victim funds</p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <DecisionBadge suspect={suspect} />
          {decisionButtons}
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={expanded}
            aria-label={expanded ? 'Hide details' : 'Show details'}
            className="cursor-pointer rounded-md p-1.5 text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
          >
            <ChevronDown size={16} className={`transition-transform ${expanded ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {/* Detail */}
      {expanded && (
        <div className="grid grid-cols-1 gap-5 border-t border-ink-100 bg-surface-sunk/60 px-4 py-4 pl-14 lg:grid-cols-[1fr_320px]">
          <div className="min-w-0 space-y-3">
            <div>
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">Why this wallet</h4>
              <p className="mt-1 text-xs text-ink-500">{suspect.role_description}</p>
            </div>
            <ul className="space-y-2.5">
              {signals.map(reason => (
                <li key={reason.code} className="flex gap-2.5">
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-critical-soft text-critical">
                    <Plus size={10} strokeWidth={3} aria-hidden="true" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-[13px] leading-relaxed text-ink-800">{reason.text}</p>
                    {reason.transactions.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {/* One chip per transaction. A Bitcoin transaction paying
                            several wallets arrives once per output, and listing
                            the same hash twice says nothing while breaking the
                            list's keys. */}
                        {uniqueByHash(reason.transactions).slice(0, 4).map(tx => {
                          const url = explorerTxUrl(suspect.chain, tx.tx_hash)
                          return (
                            <a
                              key={tx.tx_hash}
                              href={url ?? undefined}
                              target="_blank"
                              rel="noreferrer"
                              title={`${tx.tx_hash}\n${when(tx.timestamp)}`}
                              className="inline-flex items-center gap-1 rounded border border-ink-200 bg-surface px-1.5 py-0.5 font-mono text-[10.5px] text-ink-600 hover:border-brand-500 hover:text-brand-600"
                            >
                              {shortHash(tx.tx_hash)}
                              <span className="font-sans text-ink-400">{amount(tx.value)}</span>
                              <ExternalLink size={10} aria-hidden="true" />
                            </a>
                          )
                        })}
                        {uniqueByHash(reason.transactions).length > 4 && (
                          <span className="px-1 py-0.5 text-[10.5px] text-ink-400">
                            +{uniqueByHash(reason.transactions).length - 4} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </li>
              ))}
              {caveats.map(reason => (
                <li key={reason.code} className="flex gap-2.5">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
                  <p className="text-[13px] leading-relaxed text-ink-700">
                    <span className="font-semibold text-warning">Caveat: </span>{reason.text}
                  </p>
                </li>
              ))}
            </ul>

            <div className="flex flex-wrap gap-x-6 gap-y-1 pt-1 text-[11px] text-ink-500">
              <span>{suspect.hop === 0 ? 'Reported wallet' : `${suspect.hop} hop${suspect.hop === 1 ? '' : 's'} from the reported wallet`}</span>
              <span>Received {amount(suspect.received)} · sent {amount(suspect.sent)}</span>
              <span>Active {when(suspect.first_activity)} – {when(suspect.last_activity)}</span>
            </div>
          </div>

          <div className="space-y-3">
            <div className="rounded-md border border-brand-500/30 bg-brand-500/10 p-3">
              <h4 className="text-[11px] font-semibold uppercase tracking-wide text-brand-500">Recommended action</h4>
              <p className="mt-1 text-xs leading-relaxed text-ink-800">{suspect.recommended_action}</p>
            </div>

            {suspect.linked_cases.length > 0 && (
              <div>
                <h4 className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">Linked complaints</h4>
                <ul className="mt-1 space-y-1">
                  {suspect.linked_cases.slice(0, 5).map(c => (
                    <li key={c.case_id}>
                      <Link to={`/cases/${c.case_id}`} className="inline-flex items-center gap-1 text-xs font-medium text-intel hover:underline">
                        <Link2 size={12} /> {c.complaint_ref ?? `Case ${c.case_id.slice(0, 8)}`}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {suspect.same_owner_as.length > 0 && (
              <div>
                <h4 className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">Same owner as</h4>
                <ul className="mt-1 space-y-1 text-xs">
                  {suspect.same_owner_as.slice(0, 4).map(a => <li key={a}><Address address={a} chain={suspect.chain} /></li>)}
                </ul>
              </div>
            )}

            <div>
              <label htmlFor={`note-${suspect.id}`} className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                Officer's note {status === 'pending' ? '(saved with your decision)' : ''}
              </label>
              <textarea
                id={`note-${suspect.id}`}
                value={note}
                onChange={e => setNote(e.target.value)}
                rows={2}
                maxLength={500}
                placeholder="e.g. Deposit time matches the victim's UPI payment"
                className="mt-1 w-full resize-y rounded-md border border-ink-200 bg-surface px-2.5 py-1.5 text-xs text-ink-800 placeholder:text-ink-400 focus:border-brand-500 focus:outline-hidden focus:ring-1 focus:ring-brand-500"
              />
              {status !== 'pending' && note !== (suspect.decision.note ?? '') && (
                <button
                  type="button"
                  onClick={() => decide(status)}
                  className="mt-1 cursor-pointer text-[11px] font-medium text-brand-600 hover:underline"
                >
                  Save note
                </button>
              )}
              {suspect.decision.decided_by && status !== 'pending' && (
                <p className="mt-1 text-[11px] text-ink-500">
                  {status === 'confirmed' ? 'Confirmed' : 'Dismissed'} by {suspect.decision.decided_by}
                  {suspect.decision.decided_at && ` on ${new Date(suspect.decision.decided_at).toLocaleString()}`}
                </p>
              )}
            </div>

            <button
              type="button"
              onClick={() => onLocate(suspect.address)}
              className="inline-flex cursor-pointer items-center gap-1.5 text-xs font-medium text-brand-600 hover:underline"
            >
              <Crosshair size={13} /> Show on graph
            </button>
          </div>
        </div>
      )}
    </li>
  )
}

export function SuspectsPanel({ caseId, result, loading, filter, onFilterChange, onChanged, onLocate }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const suspects = useMemo(() => result?.suspects ?? [], [result])

  const counts = useMemo(() => ({
    all: suspects.length,
    pending: suspects.filter(s => s.decision.status === 'pending').length,
    confirmed: suspects.filter(s => s.decision.status === 'confirmed').length,
    dismissed: suspects.filter(s => s.decision.status === 'dismissed').length,
    holding: suspects.filter(s => s.role === 'holding').length,
  }), [suspects])

  const visible = useMemo(() => suspects.filter(s =>
    filter === 'all' ? true
    : filter === 'holding' ? s.role === 'holding'
    : s.decision.status === filter,
  ), [suspects, filter])

  // Open the top suspect on first load so the reasoning is visible without
  // a click - the whole point is that nobody has to go looking for it.
  useEffect(() => {
    if (expanded === null && suspects.length > 0) setExpanded(suspects[0].id)
  }, [suspects, expanded])

  async function download() {
    setDownloading(true)
    try {
      await downloadSuspectReport(caseId)
      toast.success('Suspect report downloaded')
      onChanged()
    } catch (err) {
      toast.error(await describeDownloadError(err))
    } finally {
      setDownloading(false)
    }
  }

  const tabs: { key: SuspectFilter; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'pending', label: 'Needs review' },
    { key: 'confirmed', label: 'Confirmed' },
    { key: 'dismissed', label: 'Dismissed' },
    ...(counts.holding > 0 || filter === 'holding' ? [{ key: 'holding' as const, label: 'Holding funds' }] : []),
  ]

  return (
    <section id="suspects" aria-labelledby="suspects-title" className="scroll-mt-6 overflow-hidden rounded-md border border-ink-200 bg-surface">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-ink-200 px-4 py-3">
        <div className="min-w-0">
          <h2 id="suspects-title" className="text-sm font-semibold text-ink-900">Suspects</h2>
          <p className="mt-0.5 max-w-2xl text-xs leading-relaxed text-ink-500">
            Wallets ranked by the evidence against them. Confirm the ones you stand behind —
            only confirmed suspects are included in the suspect report.
          </p>
        </div>
        <button
          type="button"
          onClick={download}
          disabled={counts.confirmed === 0 || downloading}
          title={counts.confirmed === 0 ? 'Confirm at least one suspect first' : undefined}
          className="inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-md bg-brand-600 px-3 py-2 text-xs font-semibold text-white shadow-2xs transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-ink-200 disabled:text-ink-500"
        >
          {downloading ? <Loader2 size={14} className="animate-spin" /> : <FileText size={14} />}
          Suspect report{counts.confirmed > 0 ? ` (${counts.confirmed})` : ''}
        </button>
      </header>

      <div className="flex flex-wrap items-center gap-1 border-b border-ink-100 px-3 py-2" role="tablist" aria-label="Filter suspects">
        {tabs.map(tab => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={filter === tab.key}
            onClick={() => onFilterChange(tab.key)}
            className={`cursor-pointer rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
              filter === tab.key ? 'bg-ink-900 text-surface' : 'text-ink-600 hover:bg-ink-100'
            }`}
          >
            {tab.label}
            <span className={`tabular ml-1.5 ${filter === tab.key ? 'text-surface/70' : 'text-ink-400'}`}>
              {counts[tab.key]}
            </span>
          </button>
        ))}
      </div>

      {loading && !result ? (
        <div className="space-y-2 p-4">
          {[0, 1, 2].map(i => <div key={i} className="h-14 animate-skeleton rounded-md bg-ink-100" />)}
        </div>
      ) : !result?.ready ? (
        <EmptyState
          icon={<Users size={22} />}
          title="Suspects appear when the trace finishes"
          detail={result?.reason ?? 'The trace has to finish before its wallets can be assessed.'}
        />
      ) : visible.length === 0 ? (
        <EmptyState
          icon={<Users size={22} />}
          title={suspects.length === 0 ? 'No wallets stood out' : 'Nothing in this view'}
          detail={suspects.length === 0
            ? 'No wallet in this trace carried enough evidence to be listed. The detailed findings below show everything the trace observed.'
            : 'Choose another filter to see the rest of the list.'}
        />
      ) : (
        <ol className="divide-y divide-ink-100">
          {visible.map(suspect => (
            <SuspectRow
              key={suspect.id}
              caseId={caseId}
              suspect={suspect}
              expanded={expanded === suspect.id}
              onToggle={() => setExpanded(prev => (prev === suspect.id ? '' : suspect.id))}
              onChanged={onChanged}
              onLocate={onLocate}
            />
          ))}
        </ol>
      )}
    </section>
  )
}
