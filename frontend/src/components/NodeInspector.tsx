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
    <div className="absolute top-14 right-3 bottom-3 z-30 flex w-[calc(100%-24px)] sm:w-88 md:w-96 flex-col rounded-xl border border-ink-200/90 bg-surface/95 shadow-2xl backdrop-blur-md overflow-hidden transition-all animate-in fade-in slide-in-from-right-3 duration-200">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b border-ink-100 bg-surface px-4 py-3">
        <div className="min-w-0 flex-1">
          <span className="inline-flex items-center rounded-md bg-ink-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-ink-700">
            {TYPE_LABELS[node.node_type] ?? node.node_type}
          </span>
          {node.label_name && (
            <p className="mt-1 truncate text-sm font-bold text-ink-900">{node.label_name}</p>
          )}
          <p className="mt-1 break-all font-mono text-[11px] text-ink-600 bg-ink-50/80 p-1.5 rounded border border-ink-100 select-all">
            {node.address}
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-700 transition-colors"
          title="Close inspector"
        >
          <X size={16} />
        </button>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 text-xs">
        {/* Taint: the evidentiary claim about this wallet */}
        {node.taint_ratio !== undefined && (
          <div className="rounded-lg border border-ink-100 bg-surface-sunk p-3 shadow-2xs">
            <div className="flex items-center justify-between gap-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-ink-500">
                Victim Funds
              </span>
              <TaintBar ratio={node.taint_ratio} value={node.tainted_value} />
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-600">
              <span className="font-semibold text-ink-800">{Math.round(node.taint_ratio * 100)}%</span> of the value reaching this wallet along traced paths is attributable to the reported victim
              {node.tainted_value !== undefined && (
                <span className="font-semibold text-ink-800"> ({node.tainted_value} {node.chain})</span>
              )}.
            </p>
          </div>
        )}

        {/* Provenance: why this wallet is in the investigation at all */}
        {node.why_included && (
          <div className="rounded-lg border border-ink-100 bg-ink-50/60 p-2.5">
            <span className="font-semibold text-ink-500 text-[10px] uppercase tracking-wider block mb-1">
              Provenance
            </span>
            <p className="text-[11px] leading-relaxed text-ink-700">
              {node.why_included}
            </p>
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="border-t border-ink-100 bg-surface px-4 py-2.5 flex items-center justify-between gap-2">
        <button
          onClick={copyAddress}
          className="inline-flex items-center gap-1.5 rounded-md border border-ink-200 bg-surface px-3 py-1.5 text-xs font-semibold text-ink-700 shadow-2xs hover:bg-ink-50 hover:text-ink-900 transition-colors"
        >
          <Copy size={13} />
          Copy
        </button>
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-brand-200 bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-600 hover:bg-brand-100 hover:text-brand-700 transition-colors"
          >
            Explorer <ExternalLink size={13} />
          </a>
        )}
      </div>
    </div>
  )
}
