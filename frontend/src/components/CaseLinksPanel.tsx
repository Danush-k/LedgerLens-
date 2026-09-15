/**
 * Cross-Case Intelligence Panel
 *
 * Surfacing correlations across separate complaints that cannot be seen from
 * a single case file. When multiple victims report the same scam wallet,
 * it is highlighted with critical priority as the strongest investigative link.
 */
import { ArrowUpRight, GitMerge, Network, Repeat } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getCaseLinks } from '../api/client'
import type { CaseLink } from '../types'
import { Address, RiskBadge } from './ui/Primitives'

function CaseRow({
  link,
  showWallet,
  chain,
}: {
  link: CaseLink
  showWallet?: boolean
  chain: string
}) {
  const extra = link.shared_addresses.length - 1
  return (
    <li className="relative flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3 transition-colors hover:bg-intel-soft/30 focus-within:bg-intel-soft/30">
      {showWallet && link.shared_addresses[0] && (
        <span className="flex min-w-0 items-center gap-1.5">
          <Address address={link.shared_addresses[0]} chain={chain} />
          {extra > 0 && (
            <span
              className="shrink-0 rounded bg-ink-100 px-1.5 py-0.5 text-[10px] font-medium text-ink-600"
              title={link.shared_addresses.slice(1).join('\n')}
            >
              +{extra} more
            </span>
          )}
        </span>
      )}
      <RiskBadge score={link.risk_score} />
      <span className="addr truncate font-mono text-xs text-ink-700 select-all">
        {link.reported_address.length > 20
          ? `${link.reported_address.slice(0, 10)}…${link.reported_address.slice(-6)}`
          : link.reported_address}
      </span>
      <span className="text-xs font-medium text-ink-500">
        {link.complaint_ref ?? 'no reference'}
      </span>
      <span className="text-xs text-ink-400">
        {new Date(link.created_at).toLocaleDateString()}
      </span>
      <Link
        to={`/cases/${link.case_id}`}
        className="ml-auto inline-flex shrink-0 items-center gap-1.5 rounded-md border border-brand-200 bg-brand-50/70 px-2.5 py-1 text-xs font-semibold text-brand-700 transition-colors hover:border-brand-500 hover:bg-brand-100"
      >
        Open case <ArrowUpRight size={13} />
        <span className="absolute inset-0" aria-hidden="true" />
      </Link>
    </li>
  )
}

export function CaseLinksPanel({ caseId, chain }: { caseId: string; chain: string }) {
  const [links, setLinks] = useState<CaseLink[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLinks(null)
    setFailed(false)
    getCaseLinks(caseId)
      .then((data) => !cancelled && setLinks(data))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [caseId])

  if (failed) {
    return (
      <section className="overflow-hidden rounded-xl border-2 border-intel/30 bg-surface shadow-xs">
        <header className="bg-intel-soft/70 px-5 py-4 border-b border-intel/15">
          <div className="flex items-center gap-2">
            <Network size={16} className="shrink-0 text-intel" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-intel">
              Cross-case intelligence
            </h2>
          </div>
          <p className="mt-1 text-xs text-ink-600">
            Could not load linked cases. This indicates a network or database read issue, not that no links exist.
          </p>
        </header>
      </section>
    )
  }

  if (!links) {
    return (
      <section className="overflow-hidden rounded-xl border-2 border-intel/30 bg-surface shadow-xs">
        <header className="bg-intel-soft/70 px-5 py-4 border-b border-intel/15">
          <div className="flex items-center gap-2">
            <Network size={16} className="shrink-0 text-intel" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-intel">
              Cross-case intelligence
            </h2>
          </div>
          <div className="mt-2 h-8 w-64 animate-skeleton rounded bg-intel-soft" />
        </header>
      </section>
    )
  }

  if (links.length === 0) {
    return (
      <section className="overflow-hidden rounded-xl border-2 border-intel/30 bg-surface shadow-xs">
        <header className="bg-intel-soft/70 px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Network size={16} className="shrink-0 text-intel" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-intel">
                Cross-case intelligence
              </h2>
            </div>
            <span className="rounded-full bg-ink-100 dark:bg-ink-800 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-600 dark:text-ink-300">
              Isolated Incident
            </span>
          </div>
          <p className="mt-1.5 text-sm font-bold text-ink-900">
            No connected complaints found in dataset.
          </p>
          <p className="mt-1 text-xs leading-relaxed text-ink-600">
            No single case file shows cross-case links. As additional victim reports are filed or bulk spreadsheets ingested that name this wallet or share downstream hops, LedgerLens will automatically correlate and highlight them here.
          </p>
        </header>
      </section>
    )
  }

  const repeats = links.filter((l) => l.relationship === 'same_wallet')
  const shared = links.filter((l) => l.relationship === 'shared_wallet')
  const repeatedWallet = repeats[0]?.shared_addresses[0]
  const sharedWalletCount = new Set(shared.flatMap((l) => l.shared_addresses)).size

  return (
    <section className="overflow-hidden rounded-xl border-2 border-intel/40 bg-surface shadow-xs transition-all">
      {/* Header matching screenshot */}
      <header className="bg-intel-soft/80 px-5 py-4 border-b border-intel/15">
        <div className="flex items-center gap-2">
          <Network size={16} className="shrink-0 text-intel" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-intel">
            Cross-case intelligence
          </h2>
        </div>
        <p className="mt-1.5 text-sm font-bold text-ink-900 leading-snug">
          Connected to {links.length} other {links.length === 1 ? 'complaint' : 'complaints'}
          {sharedWalletCount > 0 && (
            <> through {sharedWalletCount} shared {sharedWalletCount === 1 ? 'wallet' : 'wallets'}</>
          )}.
        </p>
        <p className="mt-1 text-xs leading-relaxed text-ink-600">
          No single case file shows this. It appears only when complaints are read
          together, and it is the strongest available indication that separate
          reports describe one operation.
        </p>
      </header>

      {/* STRONGEST LINK BANNER (Repeated wallet reported across independent cases) */}
      {repeats.length > 0 && (
        <section className="border-t border-ink-200">
          <div className="bg-critical-soft/90 px-5 py-3.5 border-b border-critical/20">
            <div className="flex flex-wrap items-center gap-2">
              <Repeat size={14} className="shrink-0 text-critical" />
              <span className="text-xs font-bold text-critical">
                Same wallet reported {repeats.length}{' '}
                {repeats.length === 1 ? 'other time' : 'other times'}
              </span>
              <span className="rounded-full bg-critical/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-critical">
                Strongest link
              </span>
            </div>
            {repeatedWallet && (
              <p className="mt-2 font-mono text-xs font-semibold text-ink-900 select-all break-all">
                {repeatedWallet}
              </p>
            )}
            <p className="mt-1 text-[11px] text-ink-600">
              Separate complainants named this exact address.
            </p>
          </div>
          <ul className="divide-y divide-ink-100 bg-surface">
            {repeats.map((link) => (
              <CaseRow key={link.case_id} link={link} chain={chain} />
            ))}
          </ul>
        </section>
      )}

      {/* Shared downstream wallets */}
      {shared.length > 0 && (
        <section className="border-t border-ink-200">
          <div className="bg-intel-soft/60 px-5 py-3 border-b border-intel/15">
            <div className="flex flex-wrap items-center gap-2">
              <GitMerge size={14} className="shrink-0 text-intel" />
              <span className="text-xs font-bold text-intel">
                Traces converge at a shared wallet
              </span>
              <span className="rounded-full bg-intel/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-intel">
                {shared.length} {shared.length === 1 ? 'case' : 'cases'}
              </span>
            </div>
            <p className="mt-1 text-xs text-ink-600 leading-relaxed">
              These complaints route funds through wallets this case also passes
              through — a consolidation point. It is shared fund flow, not proof of
              common control: a payment processor produces the same shape.
            </p>
          </div>
          <ul className="divide-y divide-ink-100 bg-surface">
            {shared.map((link) => (
              <CaseRow key={link.case_id} link={link} showWallet chain={chain} />
            ))}
          </ul>
        </section>
      )}
    </section>
  )
}
