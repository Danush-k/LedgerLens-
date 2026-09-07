import { Copy, ExternalLink, X } from 'lucide-react'
import { toast } from 'sonner'
import type { GraphNode } from '../types'
import { explorerUrl } from '../utils/explorer'
import { TaintBar } from './ui/Primitives'

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

  async function copyAddress() {
    try {
      await navigator.clipboard.writeText(node.address)
      toast.success('Address copied')
    } catch {
      toast.error('Could not copy — clipboard access blocked')
    }
  }

  return (
    <div className="absolute inset-x-3 bottom-3 rounded-lg border border-ink-200 bg-surface/95 p-3.5 shadow-lg backdrop-blur">
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

      {/* Taint: the evidentiary claim about this wallet. "Connected to the
          victim" is weak; a percentage is what supports a seizure request. */}
      {node.taint_ratio !== undefined && (
        <div className="mt-2.5 rounded border border-ink-200 bg-surface-sunk px-2.5 py-2">
          <div className="flex items-center justify-between gap-3">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">
              Victim funds
            </span>
            <TaintBar ratio={node.taint_ratio} value={node.tainted_value} />
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-ink-500">
            {Math.round(node.taint_ratio * 100)}% of the value reaching this wallet along
            traced paths is attributable to the reported victim
            {node.tainted_value !== undefined && ` (${node.tainted_value} ${node.chain})`}.
          </p>
        </div>
      )}

      {/* Provenance: why this wallet is in the investigation at all. */}
      {node.why_included && (
        <p className="mt-2 text-[11px] leading-relaxed text-ink-600">
          <span className="font-semibold text-ink-500">Why included: </span>
          {node.why_included}
        </p>
      )}
      <div className="mt-2 flex items-center gap-3">
        <button
          onClick={copyAddress}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-600 hover:text-ink-900"
        >
          Copy address <Copy size={12} />
        </button>
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-600 hover:underline"
          >
            View on block explorer <ExternalLink size={12} />
          </a>
        )}
      </div>
    </div>
  )
}
