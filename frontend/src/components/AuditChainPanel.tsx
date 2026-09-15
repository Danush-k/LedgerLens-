/**
 * The case's audit log, shown with its integrity verification.
 *
 * The two are deliberately not separable. A history without provenance
 * invites the reader to trust it, and the whole reason this log is
 * hash-chained is that trust in a mutable table is misplaced. So the
 * verdict sits above the entries, and it states what it actually
 * establishes rather than showing a reassuring tick.
 */
import { AlertTriangle, ChevronDown, ShieldCheck, ShieldX } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getAuditChain } from '../api/client'
import type { AuditChain } from '../types'
import { Panel, Pill } from './ui/Primitives'

const EVENT_LABELS: Record<string, string> = {
  case_created: 'Case created',
  trace_started: 'Trace started',
  trace_completed: 'Trace completed',
  trace_failed: 'Trace failed',
  exchange_identified: 'Exchange identified',
  alert_sent: 'Alert dispatched',
  ncrp_intake_received: 'NCRP intake received',
}

export function AuditChainPanel({ caseId }: { caseId: string }) {
  const [chain, setChain] = useState<AuditChain | null>(null)
  const [failed, setFailed] = useState(false)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    let cancelled = false
    getAuditChain(caseId)
      .then(data => !cancelled && setChain(data))
      .catch(() => !cancelled && setFailed(true))
    return () => { cancelled = true }
  }, [caseId])

  if (failed) {
    return (
      <Panel title="Chain of custody">
        <p className="text-xs text-ink-500">
          Could not load the audit record. This says nothing about the record's
          integrity — only that it could not be read.
        </p>
      </Panel>
    )
  }

  if (!chain) {
    return (
      <Panel title="Chain of custody">
        <div className="h-16 animate-skeleton rounded bg-ink-200" />
      </Panel>
    )
  }

  const { verification, entries } = chain
  const intact = verification.intact && verification.entry_count > 0

  return (
    <Panel
      title="Chain of custody"
      subtitle={`${verification.entry_count} recorded ${verification.entry_count === 1 ? 'action' : 'actions'}`}
      dense
    >
      {/* The verdict, stated in full. */}
      <div className={`flex gap-2.5 border-b border-ink-200 px-3.5 py-3 ${
        verification.intact ? '' : 'bg-critical-soft'
      }`}>
        {verification.intact
          ? <ShieldCheck size={16} className="mt-0.5 shrink-0 text-good" />
          : <ShieldX size={16} className="mt-0.5 shrink-0 text-critical" />}
        <div className="min-w-0">
          <p className={`text-[13px] font-semibold ${
            verification.intact ? 'text-good' : 'text-critical'
          }`}>
            {intact ? 'Record verified' :
             verification.entry_count === 0 ? 'No actions recorded' :
             'Record does not verify'}
          </p>
          <p className="mt-0.5 text-xs leading-relaxed text-ink-600">{verification.reason}</p>
          {verification.chain_head && (
            <p className="mt-1.5 text-[11px] text-ink-500">
              Chain head{' '}
              <span className="addr text-ink-700">{verification.chain_head.slice(0, 32)}…</span>
            </p>
          )}
        </div>
      </div>

      {entries.length > 0 && (
        <>
          <ol className="divide-y divide-ink-100">
            {(expanded ? entries : entries.slice(-4)).map(entry => {
              const broken = verification.first_broken_sequence === entry.sequence
              return (
                <li
                  key={entry.sequence}
                  className={`px-3.5 py-2 ${broken ? 'border-l-[3px] border-l-critical bg-critical-soft' : ''}`}
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                    <span className="flex items-center gap-2 text-[13px] font-medium text-ink-900">
                      <span className="tabular text-[11px] text-ink-400">
                        {String(entry.sequence).padStart(2, '0')}
                      </span>
                      {EVENT_LABELS[entry.event] ?? entry.event.replace(/_/g, ' ')}
                      {entry.simulated && <Pill tone="neutral">simulated</Pill>}
                      {broken && (
                        <span className="flex items-center gap-1 text-[11px] font-medium text-critical">
                          <AlertTriangle size={11} /> break detected here
                        </span>
                      )}
                    </span>
                    <time className="tabular shrink-0 text-[11px] text-ink-500">
                      {new Date(entry.created_at).toLocaleString()}
                    </time>
                  </div>
                  {entry.detail && (
                    <p className="mt-0.5 text-xs leading-relaxed text-ink-600">{entry.detail}</p>
                  )}
                  {expanded && entry.entry_hash && (
                    <p className="addr mt-1 truncate text-[10px] text-ink-400">
                      {entry.entry_hash}
                    </p>
                  )}
                </li>
              )
            })}
          </ol>

          {entries.length > 4 && (
            <button
              onClick={() => setExpanded(e => !e)}
              aria-expanded={expanded}
              className="flex w-full cursor-pointer items-center justify-center gap-1 border-t border-ink-200 py-2 text-[11px] font-medium text-ink-500 transition-colors hover:bg-ink-50 hover:text-brand-600"
            >
              {expanded ? 'Show recent only' : `Show all ${entries.length} actions and hashes`}
              <ChevronDown size={12} className={expanded ? 'rotate-180' : ''} />
            </button>
          )}
        </>
      )}
    </Panel>
  )
}
