/**
 * Evidence-backed findings from the pattern detectors.
 *
 * Each finding carries the transactions it was derived from, so a claim on
 * screen can always be checked against the chain. That is the difference
 * between an assertion and evidence, and it is why the transaction hashes
 * are shown rather than summarised away.
 */
import { ChevronDown, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import type { Pattern } from '../types'
import { explorerUrl } from '../utils/explorer'
import { Address, EmptyState, Panel, SeverityPill } from './ui/Primitives'

const SEVERITY_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 }

/**
 * Findings grouped by the question each one answers.
 *
 * Severity alone ranks findings but does not explain them: it puts "reached
 * an exchange" next to "seen in another case" purely because both are high,
 * when one tells the investigator where to send a notice and the other
 * tells them who else to call. Grouping by the decision a finding informs
 * means the panel can be read top to bottom as an account of the case
 * rather than a scoreboard.
 *
 * Order is deliberate: where the money went comes first, because that is
 * the actionable answer. What limits the trace comes last, because it
 * qualifies everything above it.
 */
const GROUPS: { key: string; title: string; blurb: string; patterns: string[] }[] = [
  {
    key: 'destination',
    title: 'Where the money went',
    blurb: 'Who to serve, and how directly funds reached them.',
    patterns: ['exchange_deposit', 'mixer_hit', 'bridge_hit', 'service_hit'],
  },
  {
    key: 'movement',
    title: 'How the money was moved',
    blurb: 'Laundering behaviour visible in the traced subgraph.',
    patterns: ['peel_chain', 'fan_out', 'fan_in', 'rapid_movement', 'pass_through'],
  },
  {
    key: 'limits',
    title: 'Limits of this trace',
    blurb: 'What this trace could not establish.',
    patterns: ['untraced_termination', 'commingling', 'partial_data'],
  },
]

const CROSS_CASE = ['prior_report', 'shared_downstream']

function groupOf(pattern: string): string {
  return GROUPS.find(g => g.patterns.includes(pattern))?.key ?? 'movement'
}

const SEVERITY_STRIPE: Record<string, string> = {
  high: 'border-l-critical',
  medium: 'border-l-warning',
  low: 'border-l-ink-300',
}

function txUrl(chain: string, hash: string): string | null {
  const base = explorerUrl(chain, '')
  if (!base) return null
  return `${base.replace('/address/', '/tx/')}${hash}`
}

export function FindingsPanel({ patterns, chain }: { patterns: Pattern[] | null; chain: string }) {
  const [showAll, setShowAll] = useState(false)

  // Cross-case signals have their own panel, which names the wallet behind
  // each link. Repeating them here would state the same thing twice.
  const all = [...(patterns ?? [])]
    .filter(f => !CROSS_CASE.includes(f.pattern))
    .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3))

  // Low-severity findings are context, not decisions. A trace produces
  // several and they push what needs acting on below the fold, so they stay
  // one click away rather than being dropped - the count is still shown, so
  // nothing is hidden silently.
  const minor = all.filter(f => f.severity === 'low').length
  const findings = showAll ? all : all.filter(f => f.severity !== 'low')

  const counts = all.reduce<Record<string, number>>((acc, f) => {
    acc[f.severity] = (acc[f.severity] ?? 0) + 1
    return acc
  }, {})

  return (
    <Panel
      title="Findings"
      subtitle={
        all.length
          ? `${counts.high ?? 0} high · ${counts.medium ?? 0} medium · ${counts.low ?? 0} low`
          : undefined
      }
      dense
    >
      {all.length === 0 ? (
        <EmptyState
          icon={<ShieldCheck size={24} />}
          title="No patterns detected"
          detail="The detectors found nothing notable in this trace. That is a result about the traced subgraph, not a clearance of the wallet."
        />
      ) : (
        GROUPS.map(group => {
          const inGroup = findings.filter(f => groupOf(f.pattern) === group.key)
          if (inGroup.length === 0) return null
          return (
            <section key={group.key}>
              <div className="flex flex-wrap items-baseline gap-x-2 border-b border-ink-200 bg-surface-sunk px-3.5 py-1.5">
                <h3 className="text-[11px] font-semibold uppercase tracking-wide text-ink-700">
                  {group.title}
                </h3>
                <p className="text-[11px] text-ink-500">{group.blurb}</p>
              </div>
              <ul className="divide-y divide-ink-100">
                {inGroup.map((f, i) => (
                  <Finding key={`${f.pattern}-${i}`} finding={f} chain={chain} />
                ))}
              </ul>
            </section>
          )
        })
      )}

      {minor > 0 && (
        <button
          onClick={() => setShowAll(v => !v)}
          aria-expanded={showAll}
          className="flex w-full cursor-pointer items-center justify-center gap-1 border-t border-ink-200 py-2 text-[11px] font-medium text-ink-500 transition-colors hover:bg-ink-50 hover:text-brand-600"
        >
          {showAll
            ? 'Show only what needs a decision'
            : `Show ${minor} further low-severity finding${minor === 1 ? '' : 's'}`}
          <ChevronDown size={12} className={showAll ? 'rotate-180' : ''} />
        </button>
      )}
    </Panel>
  )
}

function Finding({ finding, chain }: { finding: Pattern; chain: string }) {
  const [open, setOpen] = useState(false)
  const hasEvidence = finding.transactions.length > 0 || finding.addresses.length > 0

  return (
    <li className={`border-l-[3px] ${SEVERITY_STRIPE[finding.severity] ?? 'border-l-ink-300'}`}>
      <div className="px-3.5 py-2.5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[13px] font-semibold text-ink-900">{finding.title}</span>
              <SeverityPill severity={finding.severity} />
            </div>
            <p className="mt-1 text-xs leading-relaxed text-ink-600">{finding.evidence}</p>
          </div>
          {hasEvidence && (
            <button
              onClick={() => setOpen(o => !o)}
              aria-expanded={open}
              className="flex shrink-0 cursor-pointer items-center gap-1 rounded px-1.5 py-1 text-[11px] font-medium text-ink-500 transition-colors hover:bg-ink-50 hover:text-brand-600"
            >
              Evidence
              <ChevronDown
                size={12}
                className={`transition-transform ${open ? 'rotate-180' : ''}`}
              />
            </button>
          )}
        </div>

        {open && hasEvidence && (
          <div className="mt-2.5 space-y-2 rounded border border-ink-200 bg-surface-sunk p-2.5">
            {finding.addresses.length > 0 && (
              <div>
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink-500">
                  Addresses
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {finding.addresses.map(a => (
                    <Address key={a} address={a} chain={chain} />
                  ))}
                </div>
              </div>
            )}
            {finding.transactions.length > 0 && (
              <div>
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink-500">
                  Transactions ({finding.transactions.length})
                </p>
                <div className="flex flex-col gap-1">
                  {finding.transactions.map(tx => {
                    const url = txUrl(chain, tx)
                    return url ? (
                      <a
                        key={tx}
                        href={url}
                        target="_blank"
                        rel="noreferrer"
                        className="addr text-brand-600 hover:underline"
                      >
                        {tx}
                      </a>
                    ) : (
                      <span key={tx} className="addr text-ink-700">{tx}</span>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </li>
  )
}
