import { ArrowRight, Clock } from 'lucide-react'
import type { GraphEdge, GraphNode } from '../types'
import { formatAmount } from '../utils/format'

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  chain: string
}

export function CaseTimeline({ nodes, edges, chain }: Props) {
  if (!edges || edges.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-ink-200 bg-surface p-8 text-center text-xs text-ink-400">
        No outgoing fund transfers recorded for chronological timeline analysis.
      </div>
    )
  }

  // Sort transfers by hop ASC then timestamp ASC
  const sortedEdges = [...edges].sort((a, b) => {
    if (a.hop !== b.hop) return a.hop - b.hop
    return a.timestamp - b.timestamp
  })

  const nodeMap = new Map(nodes.map((n) => [n.id, n]))

  return (
    <div className="rounded-xl border border-ink-100 bg-surface p-6 shadow-2xs">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-ink-900">Chronological Fund Movement Timeline</h3>
          <p className="text-xs text-ink-500">
            Step-by-step sequential breakdown of fund transfers from victim outflow to final cashout target.
          </p>
        </div>
        <div className="flex items-center gap-1 text-xs font-semibold text-brand-600 bg-brand-50 px-2.5 py-1 rounded-md">
          <Clock size={14} />
          <span>{edges.length} Hops Recorded</span>
        </div>
      </div>

      <div className="relative border-l-2 border-brand-200 ml-4 pl-6 space-y-6">
        {sortedEdges.map((edge, idx) => {
          const sourceNode = nodeMap.get(edge.source)
          const targetNode = nodeMap.get(edge.target)

          const sourceAddr = sourceNode?.address || edge.source.split(':').pop()
          const targetAddr = targetNode?.address || edge.target.split(':').pop()
          const targetLabel = targetNode?.label_name
          const targetType = targetNode?.node_type || 'unresolved'

          const dateStr = edge.timestamp
            ? new Date(edge.timestamp * 1000).toUTCString()
            : 'Timestamp N/A'

          return (
            <div key={idx} className="relative group">
              {/* Timeline Marker Dot */}
              <div
                className={`absolute -left-[31px] top-1.5 h-4 w-4 rounded-full border-2 border-white shadow-2xs ${
                  targetType === 'exchange'
                    ? 'bg-emerald-500 ring-4 ring-emerald-100'
                    : targetType === 'mixer' || targetType === 'bridge'
                    ? 'bg-purple-500 ring-4 ring-purple-100'
                    : 'bg-brand-500'
                }`}
              />

              <div className="rounded-lg border border-ink-100 bg-ink-50/40 p-4 transition-all hover:border-brand-300 hover:bg-surface">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink-100 pb-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-brand-500/10 px-2 py-0.5 text-[10px] font-bold text-brand-600">
                      HOP {edge.hop}
                    </span>
                    <span className="text-xs font-mono font-bold text-ink-900">
                      {formatAmount(edge.value)} {chain.toUpperCase()}
                    </span>
                  </div>

                  <span className="text-[11px] text-ink-400 font-mono">{dateStr}</span>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
                  <div className="space-y-1">
                    <span className="text-[10px] uppercase font-semibold text-ink-400">From</span>
                    <p className="font-mono text-ink-800">{sourceAddr}</p>
                  </div>

                  <ArrowRight size={14} className="text-ink-400 shrink-0" />

                  <div className="space-y-1 text-right">
                    <span className="text-[10px] uppercase font-semibold text-ink-400">To Target</span>
                    <p className="font-mono text-ink-900 font-semibold">{targetAddr}</p>
                    {targetLabel && (
                      <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                        {targetLabel} ({targetType.toUpperCase()})
                      </span>
                    )}
                  </div>
                </div>

                {edge.tx_hash && (
                  <div className="mt-2 pt-2 border-t border-ink-100/60 flex items-center justify-between text-[11px] text-ink-400">
                    <span>Tx Hash:</span>
                    <span className="font-mono break-all text-ink-600">{edge.tx_hash}</span>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
