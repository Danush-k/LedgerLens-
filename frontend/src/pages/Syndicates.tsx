import { Layers, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getSyndicates } from '../api/client'

interface SyndicateItem {
  syndicate_id: string
  title: string
  chain: string
  target_address: string
  vasp_name: string
  linked_case_count: number
  linked_cases: Array<{
    case_id: string
    reported_address: string
    complaint_ref?: string
    risk_score?: number
    created_at?: string
  }>
  combined_risk_index: number
  type: string
}

export function Syndicates() {
  const [syndicates, setSyndicates] = useState<SyndicateItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getSyndicates()
      .then((data) => {
        setSyndicates(data.syndicates || [])
      })

      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="mx-auto max-w-7xl px-8 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-ink-100 pb-5">
        <div>
          <h1 className="text-xl font-extrabold text-ink-900">Syndicate Intelligence &amp; Repeat Offender Networks</h1>
          <p className="mt-1 text-xs text-ink-500">
            Cross-FIR clustering engine identifying shared mule accounts, deposit hubs, and repeat suspect wallets.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-brand-200 bg-brand-50 px-3.5 py-2 text-xs font-semibold text-brand-700 shadow-2xs">
            <Layers size={16} />
            <span>{syndicates.length} Active Syndicates Detected</span>
          </div>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-4">
          <div className="h-28 animate-skeleton rounded-xl bg-ink-200" />
          <div className="h-28 animate-skeleton rounded-xl bg-ink-200" />
        </div>
      ) : syndicates.length === 0 ? (
        <div className="rounded-xl border border-dashed border-ink-200 bg-surface p-12 text-center text-xs text-ink-500">
          <ShieldCheck className="mx-auto mb-3 h-10 w-10 text-emerald-500" />
          <p className="font-semibold text-ink-800 text-sm">No Multi-FIR Syndicate Clusters Detected</p>
          <p className="mt-1 text-ink-400">As more victim cases are ingested, cross-reporting patterns and shared deposit accounts will cluster here automatically.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {syndicates.map((syn) => (
            <div key={syn.syndicate_id} className="rounded-xl border border-ink-200 bg-surface p-6 shadow-2xs space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-ink-100 pb-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-brand-100 px-2 py-0.5 font-mono text-[11px] font-bold text-brand-700">
                      {syn.syndicate_id}
                    </span>
                    <h3 className="text-base font-bold text-ink-900">{syn.title}</h3>
                  </div>
                  <p className="font-mono text-xs text-ink-600">
                    Target Address ({syn.chain.toUpperCase()}): <span className="font-bold text-ink-900">{syn.target_address}</span>
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <span className="text-[10px] font-semibold uppercase text-ink-400">Risk Index</span>
                    <p className="text-lg font-black text-red-600">{syn.combined_risk_index} / 100</p>
                  </div>
                  <div className="rounded-lg bg-brand-600 px-3 py-2 text-center text-white">
                    <span className="block text-lg font-black leading-tight">{syn.linked_case_count}</span>
                    <span className="text-[10px] uppercase font-bold text-brand-100">Linked FIRs</span>
                  </div>
                </div>
              </div>

              {/* Linked Cases List */}
              <div className="space-y-2">
                <span className="text-xs font-bold text-ink-700 block">Linked Complaint Investigations:</span>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {syn.linked_cases.map((lc) => (
                    <Link
                      key={lc.case_id}
                      to={`/cases/${lc.case_id}`}
                      className="flex items-center justify-between rounded-lg border border-ink-100 bg-ink-50/50 p-3 text-xs transition-colors hover:border-brand-500 hover:bg-surface cursor-pointer"
                    >
                      <div className="space-y-0.5">
                        <span className="font-mono font-semibold text-brand-600 hover:underline">
                          #{lc.case_id.slice(0, 8)}
                        </span>
                        <p className="font-mono text-[11px] text-ink-600">{lc.reported_address.slice(0, 14)}…</p>
                      </div>
                      <div className="text-right">
                        <span className="text-[11px] font-medium text-ink-500">Ref: {lc.complaint_ref || 'N/A'}</span>
                        <span className="block font-semibold text-red-600">Risk {lc.risk_score || 0}</span>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
