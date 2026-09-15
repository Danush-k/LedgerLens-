/**
 * Shared UI vocabulary.
 *
 * Every one of these encodes state with a shape or a word as well as a
 * colour. These screens get read on uncalibrated monitors, projected in
 * briefing rooms, and by people who don't distinguish red from green -
 * colour alone is not a signal here.
 */
import { Check, Copy, ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { explorerUrl } from '../../utils/explorer'

type Tone = 'neutral' | 'info' | 'good' | 'warning' | 'critical'

const TONE_CLASS: Record<Tone, string> = {
  neutral: 'bg-ink-100 text-ink-700 border-ink-200',
  info: 'bg-brand-50 text-brand-700 border-brand-200',
  good: 'bg-good-soft text-good border-good/25',
  warning: 'bg-warning-soft text-warning border-warning/25',
  critical: 'bg-critical-soft text-critical border-critical/25',
}

export function Pill({ tone = 'neutral', children, title }: {
  tone?: Tone
  children: React.ReactNode
  title?: string
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium leading-tight whitespace-nowrap ${TONE_CLASS[tone]}`}
    >
      {children}
    </span>
  )
}

/** Case status. The word is the signal; colour only reinforces it. */
export function StatusPill({ status }: { status: string }) {
  const tone: Tone =
    status === 'complete' ? 'good'
    : status === 'failed' ? 'critical'
    : status === 'tracing' ? 'info'
    : 'neutral'
  return <Pill tone={tone}>{status}</Pill>
}

export function SeverityPill({ severity }: { severity: string }) {
  const tone: Tone =
    severity === 'high' ? 'critical' : severity === 'medium' ? 'warning' : 'neutral'
  return <Pill tone={tone}>{severity}</Pill>
}

export function riskBand(score: number): { label: string; tone: Tone } {
  // Thresholds mirror the backend rubric exactly - see risk/rules.py.
  if (score >= 70) return { label: 'high', tone: 'critical' }
  if (score >= 35) return { label: 'medium', tone: 'warning' }
  return { label: 'low', tone: 'good' }
}

/** Risk as number + band + a proportional bar, so it reads at any glance depth. */
export function RiskBadge({ score, showBar = false }: { score: number | null; showBar?: boolean }) {
  if (score === null || score === undefined) {
    return <span className="text-xs text-ink-400">—</span>
  }
  const { label, tone } = riskBand(score)
  const barColor =
    tone === 'critical' ? 'bg-risk-high' : tone === 'warning' ? 'bg-risk-medium' : 'bg-risk-low'
  return (
    <div className="flex items-center gap-2">
      <span className="tabular text-sm font-semibold text-ink-900">{score.toFixed(0)}</span>
      <Pill tone={tone}>{label}</Pill>
      {showBar && (
        <div className="h-1 w-16 overflow-hidden rounded-full bg-ink-200" role="presentation">
          <div className={`h-full ${barColor}`} style={{ width: `${Math.min(100, score)}%` }} />
        </div>
      )}
    </div>
  )
}

/**
 * Taint: the share of value arriving at a wallet attributable to the victim.
 * Shown as a percentage *and* a bar because the number is the evidentiary
 * claim and the bar is what makes a list of wallets scannable.
 */
export function TaintBar({ ratio, value }: { ratio?: number; value?: number }) {
  if (ratio === undefined) return <span className="text-xs text-ink-400">—</span>
  const pct = Math.round(ratio * 100)
  const color =
    pct >= 75 ? 'bg-taint-100' : pct >= 50 ? 'bg-taint-75'
    : pct >= 25 ? 'bg-taint-50' : pct > 0 ? 'bg-taint-25' : 'bg-taint-0'
  return (
    <div className="flex items-center gap-2" title={
      value !== undefined ? `${value} of traced value attributable to the victim` : undefined
    }>
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-ink-200">
        <div className={`h-full ${color}`} style={{ width: `${Math.max(pct, pct > 0 ? 4 : 0)}%` }} />
      </div>
      <span className="tabular text-xs text-ink-600">{pct}%</span>
    </div>
  )
}

/**
 * An address. Always monospace, always copyable in full, and truncated only
 * in the middle so both ends stay checkable - an investigator compares the
 * first and last characters, so eliding either end defeats the purpose.
 */
export function Address({ address, chain, short = true, link = true }: {
  address: string
  chain?: string
  short?: boolean
  link?: boolean
}) {
  const [copied, setCopied] = useState(false)
  const display = short && address.length > 20
    ? `${address.slice(0, 10)}…${address.slice(-6)}`
    : address

  async function copy() {
    try {
      await navigator.clipboard.writeText(address)
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    } catch {
      // Clipboard is unavailable over plain http on some browsers; the full
      // address is in the title attribute either way.
    }
  }

  return (
    <span className="group inline-flex items-center gap-1.5" title={address}>
      <span className="addr text-ink-800">{display}</span>
      <button
        onClick={copy}
        aria-label={copied ? 'Address copied' : 'Copy address'}
        className="cursor-pointer opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
      >
        {copied
          ? <Check size={12} className="text-good" />
          : <Copy size={12} className="text-ink-400 hover:text-brand-600" />}
      </button>
      {link && chain && explorerUrl(chain, address) && (
        <a
          href={explorerUrl(chain, address)!}
          target="_blank"
          rel="noreferrer"
          aria-label="Open in block explorer"
          className="opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
        >
          <ExternalLink size={12} className="text-ink-400 hover:text-brand-600" />
        </a>
      )}
    </span>
  )
}

/** A titled region. Border and background mark a container; nothing else does. */
export function Panel({ title, subtitle, actions, children, dense = false }: {
  title?: string
  subtitle?: string
  actions?: React.ReactNode
  children: React.ReactNode
  dense?: boolean
}) {
  return (
    <section className="overflow-hidden rounded-md border border-ink-200 bg-surface">
      {title && (
        <header className="flex items-center justify-between gap-3 border-b border-ink-200 px-3.5 py-2.5">
          <div className="min-w-0">
            <h2 className="text-[13px] font-semibold text-ink-900">{title}</h2>
            {subtitle && <p className="mt-0.5 text-xs text-ink-500">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className={dense ? '' : 'p-3.5'}>{children}</div>
    </section>
  )
}

/**
 * An empty state says which of two very different things happened: we have
 * no data yet, or we looked and found nothing. Conflating them is how a
 * dashboard implies innocence it hasn't established.
 */
export function EmptyState({ icon, title, detail }: {
  icon?: React.ReactNode
  title: string
  detail?: string
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-1.5 px-4 py-10 text-center">
      {icon && <div className="text-ink-300">{icon}</div>}
      <p className="text-sm font-medium text-ink-700">{title}</p>
      {detail && <p className="max-w-md text-xs leading-relaxed text-ink-500">{detail}</p>}
    </div>
  )
}

/** A headline figure. Used sparingly - only where the number is the point. */
export function StatTile({ label, value, sub, tone = 'neutral', onClick }: {
  label: string
  value: React.ReactNode
  sub?: string
  tone?: Tone
  onClick?: () => void
}) {
  const accent =
    tone === 'critical' ? 'border-l-critical'
    : tone === 'warning' ? 'border-l-warning'
    : tone === 'good' ? 'border-l-good'
    : tone === 'info' ? 'border-l-brand-500'
    : 'border-l-ink-300'

  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag
      onClick={onClick}
      className={`flex flex-col gap-0.5 border border-l-[3px] border-ink-200 ${accent} bg-surface px-3.5 py-2.5 text-left ${
        onClick ? 'cursor-pointer transition-colors hover:bg-ink-50' : ''
      }`}
    >
      <span className="text-[11px] font-medium uppercase tracking-wide text-ink-500">{label}</span>
      <span className="tabular text-xl font-semibold leading-tight text-ink-900">{value}</span>
      {sub && <span className="text-[11px] text-ink-500">{sub}</span>}
    </Tag>
  )
}

/** Dense table shell. Rows, not cards - an officer scans hundreds of these. */
export function Table({ head, children }: { head: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[13px]">
        <thead className="bg-surface-sunk">
          <tr className="border-b border-ink-200 text-left">{head}</tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

export function Th({ children, className = '' }: { children?: React.ReactNode; className?: string }) {
  return (
    <th className={`px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-500 whitespace-nowrap ${className}`}>
      {children}
    </th>
  )
}

export function Td({ children, className = '' }: { children?: React.ReactNode; className?: string }) {
  return <td className={`px-3 py-2 align-middle ${className}`}>{children}</td>
}
