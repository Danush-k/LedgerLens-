/**
 * The case, as an investigator would brief it.
 *
 * The graph shows everything; this says what it means. One paragraph of
 * what happened to the money, the four numbers a supervising officer will
 * ask for, and the next steps in the order they should be taken - each with
 * the button that starts it.
 */
import {
  ArrowRight,
  FileText,
  Gavel,
  Landmark,
  Link2,
  ListChecks,
  Users,
  Wallet,
} from 'lucide-react'
import type { CaseBriefingSummary, NextStep, NextStepAction } from '../types'
import { formatChainAmount } from '../utils/format'
import { RiskBadge } from './ui/Primitives'

interface Props {
  summary: CaseBriefingSummary
  riskScore: number | null
  onAction: (action: Exclude<NextStepAction, null>) => void
}

const ACTION_LABEL: Record<Exclude<NextStepAction, null>, string> = {
  legal_notice: 'Draft notice',
  filter_holding: 'Show wallets',
  review_suspects: 'Review',
  suspect_report: 'Download',
  linked_cases: 'View links',
}

const ACTION_ICON: Record<Exclude<NextStepAction, null>, typeof Gavel> = {
  legal_notice: Gavel,
  filter_holding: Wallet,
  review_suspects: ListChecks,
  suspect_report: FileText,
  linked_cases: Link2,
}

const STEP_TONE: Record<string, string> = {
  high: 'bg-critical-soft text-critical ring-1 ring-critical/40',
  medium: 'bg-warning-soft text-warning ring-1 ring-warning/40',
  low: 'bg-ink-100 text-ink-600 ring-1 ring-ink-300',
}

function Figure({ icon: Icon, label, value, sub, tone }: {
  icon: typeof Gavel
  label: string
  value: string
  sub: string
  tone: 'neutral' | 'good' | 'warning' | 'critical'
}) {
  const accent = {
    neutral: 'text-ink-500',
    good: 'text-good',
    warning: 'text-warning',
    critical: 'text-critical',
  }[tone]
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-md border border-ink-200 bg-surface px-4 py-3">
      <span className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-500">
        <Icon size={13} className={accent} aria-hidden="true" />
        {label}
      </span>
      <span className="tabular truncate text-xl font-semibold leading-tight text-ink-900">{value}</span>
      <span className="truncate text-[11px] text-ink-500" title={sub}>{sub}</span>
    </div>
  )
}

function StepRow({ step, index, onAction }: {
  step: NextStep
  index: number
  onAction: Props['onAction']
}) {
  const Icon = step.action ? ACTION_ICON[step.action] : null
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <span
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${STEP_TONE[step.priority]}`}
        aria-label={`Step ${index + 1}, ${step.priority} priority`}
      >
        {index + 1}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-semibold text-ink-900">{step.title}</p>
        <p className="mt-0.5 text-xs leading-relaxed text-ink-600">{step.detail}</p>
      </div>
      {step.action && Icon && (
        <button
          type="button"
          onClick={() => onAction(step.action!)}
          className="inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-md border border-ink-200 bg-surface px-2.5 py-1.5 text-xs font-medium text-ink-700 transition-colors hover:border-brand-500 hover:text-brand-600"
        >
          <Icon size={13} aria-hidden="true" />
          {ACTION_LABEL[step.action]}
          <ArrowRight size={12} aria-hidden="true" />
        </button>
      )}
    </li>
  )
}

export function CaseBriefing({ summary, riskScore, onAction }: Props) {
  const amount = (v: number) => formatChainAmount(v, summary.chain)
  const share = (v: number) =>
    summary.victim_total > 0 ? `${Math.round((v / summary.victim_total) * 100)}% of traced funds` : ''
  const { counts } = summary

  return (
    <section aria-labelledby="briefing-title" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="briefing-title" className="text-sm font-semibold text-ink-900">Case briefing</h2>
        <div className="flex items-center gap-2 text-xs text-ink-500">
          Case risk <RiskBadge score={riskScore} />
        </div>
      </div>

      <p className="max-w-4xl text-[15px] leading-relaxed text-ink-800">{summary.headline}</p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Figure
          icon={Wallet}
          label="Victim funds traced"
          value={amount(summary.victim_total)}
          sub="Sent out of the reported wallet"
          tone="neutral"
        />
        <Figure
          icon={Landmark}
          label="Reached an exchange"
          value={amount(summary.to_exchanges)}
          sub={summary.exchange_names.length
            ? `${summary.exchange_names.join(', ')} · ${share(summary.to_exchanges)}`
            : 'No exchange identified yet'}
          tone={summary.to_exchanges > 0 ? 'good' : 'neutral'}
        />
        <Figure
          icon={Wallet}
          label="Still in wallets"
          value={amount(summary.still_held)}
          sub={summary.still_held > 0
            ? `${summary.holding_wallets} wallet${summary.holding_wallets === 1 ? '' : 's'} · may be recoverable`
            : 'No unspent victim funds found'}
          tone={summary.still_held > 0 ? 'warning' : 'neutral'}
        />
        <Figure
          icon={Users}
          label="Suspects"
          value={`${counts.high} high priority`}
          sub={`${counts.total} identified · ${counts.confirmed} confirmed · ${counts.pending} to review`}
          tone={counts.high > 0 ? 'critical' : 'neutral'}
        />
      </div>

      {summary.next_steps.length > 0 && (
        <div className="overflow-hidden rounded-md border border-ink-200 bg-surface">
          <header className="border-b border-ink-200 px-4 py-2.5">
            <h3 className="text-[13px] font-semibold text-ink-900">Next steps</h3>
          </header>
          <ol className="divide-y divide-ink-100">
            {summary.next_steps.map((step, i) => (
              <StepRow key={step.key} step={step} index={i} onAction={onAction} />
            ))}
          </ol>
        </div>
      )}
    </section>
  )
}
