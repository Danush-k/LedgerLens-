import { Link2 } from 'lucide-react'
import type { WalletCluster } from '../types'

const TYPE_LABELS: Record<string, string> = {
  common_input: 'Common-input-ownership (strong)',
  shared_funder: 'Shared funder (weaker)',
}

export function ClusterPanel({ clusters }: { clusters: WalletCluster[] }) {
  if (clusters.length === 0) return null

  return (
    <div className="rounded-xl border border-ink-100 bg-white p-6 shadow-sm">
      <div className="mb-3 flex items-center gap-1.5">
        <Link2 size={14} className="text-ink-400" />
        <h2 className="text-sm font-semibold text-ink-800">Wallet clusters</h2>
      </div>
      <div className="space-y-4">
        {clusters.map((cluster, i) => (
          <div key={i} className="rounded-lg border border-ink-100 bg-ink-50/60 p-3">
            <span className="inline-flex items-center rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-600 ring-1 ring-ink-200">
              {TYPE_LABELS[cluster.type] ?? cluster.type}
            </span>
            <p className="mt-2 text-xs text-ink-600">{cluster.note}</p>
            <ul className="mt-2 space-y-1">
              {cluster.addresses.map((addr) => (
                <li key={addr} className="break-all font-mono text-[11px] text-ink-500">
                  {addr}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
