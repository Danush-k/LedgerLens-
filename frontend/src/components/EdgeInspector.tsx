import { ArrowDown, Copy, ExternalLink, Hash, X } from 'lucide-react'
import { toast } from 'sonner'
import type { GraphEdge } from '../types'
import { explorerTxUrl } from '../utils/explorer'
import { formatAmount } from '../utils/format'

interface Props {
  edge: GraphEdge
  chain: string
  onClose: () => void
}

export function EdgeInspector({ edge, chain, onClose }: Props) {
  const txUrl = explorerTxUrl(chain, edge.tx_hash)

  const formattedDate = edge.timestamp
    ? new Date(edge.timestamp * 1000).toLocaleString('en-US', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'UTC',
      }) + ' UTC'
    : 'Unknown time'

  async function copyText(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text)
      toast.success(`${label} copied`)
    } catch {
      toast.error('Could not copy to clipboard')
    }
  }

  // Clean address from potential "chain:" prefix in Cytoscape ids
  const cleanSource = edge.source.includes(':') ? edge.source.split(':', 2)[1] : edge.source
  const cleanTarget = edge.target.includes(':') ? edge.target.split(':', 2)[1] : edge.target

  return (
    <div className="absolute top-14 right-3 bottom-3 z-30 flex w-[calc(100%-24px)] sm:w-88 md:w-96 flex-col rounded-xl border border-ink-200/90 bg-surface/95 shadow-2xl backdrop-blur-md overflow-hidden transition-all animate-in fade-in slide-in-from-right-3 duration-200">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b border-ink-100 bg-surface px-4 py-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="inline-flex items-center rounded-md bg-brand-50 border border-brand-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-brand-700">
              Transaction Transfer
            </span>
            <span className="rounded-md bg-ink-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-ink-600">
              Hop {edge.hop}
            </span>
          </div>
          <p className="mt-1.5 text-base font-extrabold text-ink-900 tracking-tight">
            {formatAmount(edge.value)} <span className="text-xs font-semibold text-ink-500 uppercase">{chain}</span>
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
      <div className="flex-1 overflow-y-auto px-4 py-3.5 space-y-3.5 text-xs">
        {/* Transfer Path (From -> To) */}
        <div className="rounded-lg border border-ink-100 bg-surface-sunk p-3 space-y-2.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-ink-500 block">
            Money Movement Path
          </span>

          {/* Sender */}
          <div>
            <span className="text-[10px] text-ink-400 block mb-0.5 font-medium">Sender (From)</span>
            <div className="flex items-center justify-between gap-1 bg-surface p-1.5 rounded border border-ink-100">
              <span className="break-all font-mono text-[11px] text-ink-800 select-all">
                {cleanSource}
              </span>
              <button
                onClick={() => copyText(cleanSource, 'Sender address')}
                className="shrink-0 p-1 text-ink-400 hover:text-ink-700"
                title="Copy sender address"
              >
                <Copy size={12} />
              </button>
            </div>
          </div>

          <div className="flex justify-center text-brand-600">
            <ArrowDown size={14} className="animate-bounce" />
          </div>

          {/* Recipient */}
          <div>
            <span className="text-[10px] text-ink-400 block mb-0.5 font-medium">Recipient (To)</span>
            <div className="flex items-center justify-between gap-1 bg-surface p-1.5 rounded border border-ink-100">
              <span className="break-all font-mono text-[11px] text-ink-800 select-all">
                {cleanTarget}
              </span>
              <button
                onClick={() => copyText(cleanTarget, 'Recipient address')}
                className="shrink-0 p-1 text-ink-400 hover:text-ink-700"
                title="Copy recipient address"
              >
                <Copy size={12} />
              </button>
            </div>
          </div>
        </div>

        {/* Transaction Hash */}
        <div className="rounded-lg border border-ink-100 bg-ink-50/60 p-3 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1 font-semibold text-ink-500 text-[10px] uppercase tracking-wider">
              <Hash size={11} /> Transaction Hash (TxID)
            </span>
            <button
              onClick={() => copyText(edge.tx_hash, 'Transaction Hash')}
              className="text-[11px] font-medium text-brand-600 hover:underline flex items-center gap-1"
            >
              <Copy size={11} /> Copy
            </button>
          </div>
          <p className="break-all font-mono text-[11px] text-ink-700 select-all bg-surface p-1.5 rounded border border-ink-100">
            {edge.tx_hash}
          </p>
        </div>

        {/* Taint & Timeline Details */}
        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <div className="rounded-lg border border-ink-100 bg-surface-sunk p-2.5">
            <span className="text-[10px] font-bold text-ink-400 uppercase tracking-wider block">Timestamp</span>
            <p className="mt-1 font-medium text-ink-800 text-[11px]">{formattedDate}</p>
          </div>
          <div className="rounded-lg border border-ink-100 bg-surface-sunk p-2.5">
            <span className="text-[10px] font-bold text-ink-400 uppercase tracking-wider block">Victim Taint</span>
            <p className="mt-1 font-medium text-ink-800 text-[11px]">
              {edge.tainted_value !== undefined
                ? `${formatAmount(edge.tainted_value)} ${chain}`
                : '100% of transfer'}
            </p>
          </div>
        </div>
      </div>

      {/* Action Footer */}
      <div className="border-t border-ink-100 bg-surface px-4 py-2.5 flex items-center justify-between gap-2">
        <button
          onClick={() => copyText(edge.tx_hash, 'Transaction Hash')}
          className="inline-flex items-center gap-1.5 rounded-md border border-ink-200 bg-surface px-3 py-1.5 text-xs font-semibold text-ink-700 shadow-2xs hover:bg-ink-50 hover:text-ink-900 transition-colors"
        >
          <Copy size={13} />
          Copy TxID
        </button>
        {txUrl && (
          <a
            href={txUrl}
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
