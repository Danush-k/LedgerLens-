/**
 * Other cases this one connects to, and the wallet doing the connecting.
 *
 * The connection was previously reported as a count — "appears in 8 other
 * cases" — which tells an investigator that something is there but not what
 * to do about it. The wallet creating the link is the actionable part: it is
 * the address to put in a request, the one to search other complaints for,
 * and the one that has to hold up if the link is challenged. So the address
 * leads, and the case it points to sits beside it.
 *
 * The two link types are kept visually distinct because they support
 * different claims. The same wallet reported twice is close to direct
 * corroboration. Two traces meeting at a third wallet is weaker: it is
 * shared fund flow, and a payment processor produces the same shape. The
 * panel says which is which rather than presenting one strength of evidence.
 */
import { ArrowUpRight, GitMerge, Repeat } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getCaseLinks } from '../api/client'
import type { CaseLink } from '../types'
import { Address, Panel, RiskBadge } from './ui/Primitives'

const RELATIONSHIP = {
  same_wallet: {
    label: 'Same wallet reported',
    icon: Repeat,
    claim: 'The identical address was reported by another complainant.',
    tone: 'text-critical',
    stripe: 'border-l-critical',
  },
  shared_wallet: {
    label: 'Traces meet at a wallet',
    icon: GitMerge,
    claim: 'Both traces pass through this wallet. Shared fund flow, not proof of common control.',
    tone: 'text-warning',
    stripe: 'border-l-warning',
  },
} as const

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

  const repeats = links.filter(l => l.relationship === 'same_wallet').length

  return (
    <Panel
      title="Links to other cases"
      subtitle={
        repeats > 0
          ? `${links.length} linked · ${repeats} reported the same wallet`
          : `${links.length} linked through a shared wallet`
      }
      dense
    >
      <ul className="divide-y divide-ink-100">
        {links.map(link => {
          const meta = RELATIONSHIP[link.relationship]
          const Icon = meta.icon
          return (
            <li key={link.case_id} className={`border-l-[3px] ${meta.stripe} px-3.5 py-3`}>
              <div className="flex flex-wrap items-center gap-2">
                <Icon size={13} className={`shrink-0 ${meta.tone}`} />
                <span className={`text-[12px] font-semibold ${meta.tone}`}>{meta.label}</span>
                {link.risk_score != null && <RiskBadge score={link.risk_score} />}
                <Link
                  to={`/cases/${link.case_id}`}
                  className="ml-auto flex items-center gap-1 text-[11px] font-medium text-brand-600 hover:underline"
                >
                  Open case <ArrowUpRight size={11} />
                </Link>
              </div>

              {/* The wallet that creates the link, given first billing. It is
                  what an investigator carries into the next step. */}
              <div className="mt-2">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink-500">
                  {link.shared_addresses.length === 1
                    ? 'Linking wallet'
                    : `Linking wallets (${link.shared_addresses.length})`}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {link.shared_addresses.slice(0, 6).map(a => (
                    <Address key={a} address={a} chain={chain} />
                  ))}
                  {link.shared_addresses.length > 6 && (
                    <span className="self-center text-[11px] text-ink-500">
                      +{link.shared_addresses.length - 6} more
                    </span>
                  )}
                </div>
              </div>

              <p className="mt-2 text-[11px] leading-relaxed text-ink-500">
                {meta.claim}
              </p>

              <p className="mt-1.5 text-[11px] text-ink-500">
                That case reported{' '}
                <span className="addr text-ink-700">
                  {link.reported_address.length > 22
                    ? `${link.reported_address.slice(0, 12)}…${link.reported_address.slice(-6)}`
                    : link.reported_address}
                </span>
                {link.complaint_ref && <> · ref {link.complaint_ref}</>}
                {' · '}
                {new Date(link.created_at).toLocaleDateString()}
              </p>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}
