/**
 * Other cases this one connects to, and the wallet doing the connecting.
 *
 * The connection used to be reported as a count — "appears in 8 other
 * cases" — which tells an investigator something is there but not what to
 * do about it. The wallet creating the link is the actionable part: it is
 * the address to put in a request, to search other complaints for, and the
 * one that has to hold up if the link is challenged.
 *
 * Links are grouped by relationship rather than listed flat, because the
 * shared fact belongs to the group, not to each row. Every case that
 * reported the same wallet is linked by that one address, so printing it
 * per row said the same thing three times and pushed the cases themselves
 * — the part worth clicking — off the screen. Stated once, the cases
 * reduce to a line each.
 *
 * The two relationships stay visually distinct because they support
 * different claims. The same wallet reported twice is near-direct
 * corroboration. Two traces meeting at a third wallet is shared fund flow,
 * which a payment processor produces just as readily.
 */
import { ArrowUpRight, GitMerge, Repeat } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getCaseLinks } from '../api/client'
import type { CaseLink } from '../types'
import { Address, Panel, RiskBadge } from './ui/Primitives'

function CaseRow({ link, showWallet, chain }: {
  link: CaseLink
  /** Only where the wallet varies between rows in the group. */
  showWallet?: boolean
  chain: string
}) {
  const extra = link.shared_addresses.length - 1
  return (
    <li className="relative flex flex-wrap items-center gap-x-3 gap-y-1 px-3.5 py-2 transition-colors hover:bg-ink-50 focus-within:bg-ink-50">
      {showWallet && link.shared_addresses[0] && (
        <span className="flex min-w-0 items-center gap-1.5">
          <Address address={link.shared_addresses[0]} chain={chain} />
          {extra > 0 && (
            <span
              className="shrink-0 text-[11px] text-ink-500"
              title={link.shared_addresses.slice(1).join('\n')}
            >
              +{extra}
            </span>
          )}
        </span>
      )}
      <RiskBadge score={link.risk_score} />
      <span className="text-[11px] text-ink-500">
        {link.complaint_ref ?? 'no reference'}
      </span>
      <span className="text-[11px] text-ink-400">
        {new Date(link.created_at).toLocaleDateString()}
      </span>
      {/* The whole row is the target - a case is one thing, and asking the
          reader to hit a short word at the far right of a wide row is a
          smaller target than the row they are already looking at. The
          button stays as the visible affordance. */}
      <Link
        to={`/cases/${link.case_id}`}
        className="ml-auto inline-flex shrink-0 items-center gap-1 rounded border border-ink-200 bg-surface px-2 py-1 text-[11px] font-medium text-brand-600 transition-colors hover:border-brand-500 hover:bg-brand-50"
      >
        Open case <ArrowUpRight size={11} />
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
    getCaseLinks(caseId)
      .then(data => !cancelled && setLinks(data))
      .catch(() => !cancelled && setFailed(true))
    return () => { cancelled = true }
  }, [caseId])

  if (failed) {
    return (
      <Panel title="Links to other cases">
        <p className="text-xs text-ink-500">
          Could not load linked cases. This says nothing about whether links exist —
          only that they could not be read.
        </p>
      </Panel>
    )
  }

  if (!links) {
    return (
      <Panel title="Links to other cases">
        <div className="h-16 animate-skeleton rounded bg-ink-200" />
      </Panel>
    )
  }

  if (links.length === 0) {
    return (
      <Panel title="Links to other cases">
        <p className="text-xs leading-relaxed text-ink-500">
          No other case in this system shares a wallet with this one. That is a
          statement about the cases recorded here, not about the wallet — a
          syndicate operating outside this dataset would look the same.
        </p>
      </Panel>
    )
  }

  const repeats = links.filter(l => l.relationship === 'same_wallet')
  const shared = links.filter(l => l.relationship === 'shared_wallet')

  // Every repeat link is the same address by definition: this case's own
  // reported wallet. So it is a property of the group, not of each row.
  const repeatedWallet = repeats[0]?.shared_addresses[0]

  return (
    <Panel
      title="Links to other cases"
      subtitle={[
        repeats.length && `${repeats.length} named the same wallet`,
        shared.length && `${shared.length} share a downstream wallet`,
      ].filter(Boolean).join(' · ')}
      dense
    >
      {repeats.length > 0 && (
        <section className="border-l-[3px] border-l-critical">
          <div className="border-b border-ink-100 px-3.5 py-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <Repeat size={13} className="shrink-0 text-critical" />
              <span className="text-[12px] font-semibold text-critical">
                Same wallet reported {repeats.length}{' '}
                {repeats.length === 1 ? 'other time' : 'other times'}
              </span>
            </div>
            {repeatedWallet && (
              <div className="mt-1.5">
                <Address address={repeatedWallet} chain={chain} short={false} />
              </div>
            )}
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-500">
              Separate complainants named this exact address. Repeat use across
              independent complaints is the strongest link this system produces.
            </p>
          </div>
          <ul className="divide-y divide-ink-100">
            {repeats.map(link => (
              <CaseRow key={link.case_id} link={link} chain={chain} />
            ))}
          </ul>
        </section>
      )}

      {shared.length > 0 && (
        <section className="border-l-[3px] border-l-warning">
          <div className="border-b border-ink-100 px-3.5 py-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <GitMerge size={13} className="shrink-0 text-warning" />
              <span className="text-[12px] font-semibold text-warning">
                Traces meet at a shared wallet
              </span>
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-500">
              These cases route funds through a wallet this one also passes
              through. That is shared fund flow, not proof of common control —
              a payment processor produces the same shape.
            </p>
          </div>
          <ul className="divide-y divide-ink-100">
            {shared.map(link => (
              <CaseRow
                key={link.case_id}
                link={link}
                /* Here the wallet genuinely differs per case, so it earns
                   its place on the row. */
                showWallet
                chain={chain}
              />
            ))}
          </ul>
        </section>
      )}
    </Panel>
  )
}
