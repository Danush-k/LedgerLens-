import { ExternalLink, X } from 'lucide-react'
import type { GraphNode } from '../types'
import { explorerUrl } from '../utils/explorer'

const TYPE_LABELS: Record<string, string> = {
  reported: 'Reported wallet',
  exchange: 'Exchange / VASP',
  mixer: 'Mixer',
  bridge: 'Bridge',
  unresolved: 'Unresolved address',
  intermediate: 'Intermediate hop',
}

export function NodeInspector({ node, onClose }: { node: GraphNode; onClose: () => void }) {
  const url = explorerUrl(node.chain, node.address)

  return (
    <div className="absolute inset-x-3 bottom-3 rounded-lg border border-ink-200 bg-white/95 p-3.5 shadow-lg backdrop-blur">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-400">
            {TYPE_LABELS[node.node_type] ?? node.node_type}
          </p>
          {node.label_name && <p className="mt-0.5 text-sm font-bold text-ink-900">{node.label_name}</p>}
          <p className="mt-0.5 break-all font-mono text-xs text-ink-600">{node.address}</p>
        </div>
        <button onClick={onClose} className="shrink-0 text-ink-300 hover:text-ink-600">
          <X size={16} />
        </button>
      </div>
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-brand-600 hover:underline"
        >
          View on block explorer <ExternalLink size={12} />
        </a>
      )}
    </div>
  )
}
