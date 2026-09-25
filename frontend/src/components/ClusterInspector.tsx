import {
  ArrowDownRight,
  ArrowUpRight,
  Copy,
  Crosshair,
  ExternalLink,
  Eye,
  EyeOff,
  GitMerge,
  Layers,
  Users,
  X,
} from 'lucide-react'
import { useMemo } from 'react'
import { toast } from 'sonner'
import type { GraphEdge, GraphNode, WalletCluster } from '../types'
import { explorerTxUrl, explorerUrl } from '../utils/explorer'
import { formatAmount } from '../utils/format'

interface Props {
  cluster: WalletCluster
  nodes: GraphNode[]
  edges: GraphEdge[]
  chain: string
  isHighlighted: boolean
  verifiedAddress?: string | null
  onToggleHighlight: () => void
  onFocusCluster: () => void
  onSelectNode: (node: GraphNode) => void
  onLocateNode?: (address: string) => void
  onClose: () => void
}

const TYPE_BADGES: Record<string, { label: string; desc: string }> = {
  common_input: {
    label: 'Common-Input Ownership',
    desc: 'Co-spent as joint inputs on the same Bitcoin transaction (proven single key holder)',
  },
  shared_funder: {
    label: 'Shared Funder Cluster',
    desc: 'Wallets activated and funded by the same parent distributor address',
  },
}

export function ClusterInspector({
  cluster,
  nodes,
  edges,
  chain,
  isHighlighted,
  verifiedAddress,
  onToggleHighlight,
  onFocusCluster,
  onSelectNode,
  onLocateNode,
  onClose,
}: Props) {
  const meta = TYPE_BADGES[cluster.type] ?? {
    label: 'Wallet Cluster',
    desc: cluster.note,
  }

  async function copyText(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text)
      toast.success(`${label} copied`)
    } catch {
      toast.error('Could not copy to clipboard')
    }
  }

  // Find member nodes that exist in the active graph
  const memberAddressSet = useMemo(() => new Set(cluster.addresses), [cluster.addresses])

  // Inflow transactions: source is outside cluster, target is inside cluster
  const inflows = useMemo(() => {
    return edges.filter((e) => {
      const cleanSrc = e.source.includes(':') ? e.source.split(':', 2)[1] : e.source
      const cleanTgt = e.target.includes(':') ? e.target.split(':', 2)[1] : e.target
      return !memberAddressSet.has(cleanSrc) && memberAddressSet.has(cleanTgt)
    })
  }, [edges, memberAddressSet])

  // Outflow transactions: source is inside cluster, target is outside cluster
  const outflows = useMemo(() => {
    return edges.filter((e) => {
      const cleanSrc = e.source.includes(':') ? e.source.split(':', 2)[1] : e.source
      const cleanTgt = e.target.includes(':') ? e.target.split(':', 2)[1] : e.target
      return memberAddressSet.has(cleanSrc) && !memberAddressSet.has(cleanTgt)
    })
  }, [edges, memberAddressSet])

  // Internal transfers: both source and target are inside cluster
  const internalTransfers = useMemo(() => {
    return edges.filter((e) => {
      const cleanSrc = e.source.includes(':') ? e.source.split(':', 2)[1] : e.source
      const cleanTgt = e.target.includes(':') ? e.target.split(':', 2)[1] : e.target
      return memberAddressSet.has(cleanSrc) && memberAddressSet.has(cleanTgt)
    })
  }, [edges, memberAddressSet])

  const totalInflow = inflows.reduce((acc, e) => acc + (e.value || 0), 0)
  const totalOutflow = outflows.reduce((acc, e) => acc + (e.value || 0), 0)

  return (
    <div className="absolute top-14 right-3 bottom-3 z-30 flex w-[calc(100%-24px)] sm:w-92 md:w-104 flex-col rounded-xl border border-ink-200/90 bg-surface/95 shadow-2xl backdrop-blur-md overflow-hidden transition-all animate-in fade-in slide-in-from-right-3 duration-200">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b border-ink-100 bg-surface px-4 py-3.5">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="inline-flex items-center gap-1 rounded-md bg-brand-50 border border-brand-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-brand-700">
              <Users size={11} className="shrink-0" />
              {meta.label}
            </span>
            <span className="rounded-md bg-ink-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-ink-600">
              {cluster.addresses.length} Wallets
            </span>
          </div>
          <h2 className="mt-1.5 text-base font-extrabold text-ink-900 tracking-tight flex items-center gap-1.5">
            <GitMerge size={16} className="text-brand-600 shrink-0" />
            Same Owner Group
          </h2>
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-700 transition-colors"
          title="Close cluster inspector"
        >
          <X size={16} />
        </button>
      </div>

      {/* Scrollable Body */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3.5 text-xs">
        {/* Interactive Highlight & Focus Controls */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onToggleHighlight}
            className={`flex-1 flex items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-semibold shadow-xs transition-all ${
              isHighlighted
                ? 'bg-amber-500 border-amber-600 text-white shadow-amber-500/20'
                : 'bg-surface border-ink-200 text-ink-700 hover:bg-ink-50 hover:border-ink-300'
            }`}
          >
            {isHighlighted ? <EyeOff size={14} /> : <Eye size={14} />}
            <span>{isHighlighted ? 'Clear Highlight' : 'Highlight Transactions'}</span>
          </button>

          <button
            type="button"
            onClick={onFocusCluster}
            className="flex items-center justify-center gap-1.5 rounded-lg border border-ink-200 bg-surface px-3 py-2 text-xs font-semibold text-ink-700 shadow-xs hover:bg-ink-50 hover:border-ink-300 transition-all"
            title="Fit canvas viewport to this cluster"
          >
            <Crosshair size={14} className="text-brand-600" />
            <span>Focus in View</span>
          </button>
        </div>

        {/* Forensic Proof Card */}
        <div className="rounded-lg border border-brand-200/80 bg-brand-50/40 p-3 shadow-2xs">
          <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-brand-800">
            <Layers size={12} />
            Forensic Evidence & Heuristic
          </div>
          <p className="mt-1.5 text-xs text-ink-700 leading-relaxed">
            {cluster.note || meta.desc}
          </p>
          <p className="mt-2 text-[11px] text-ink-500 italic">
            Cryptographic guarantee: To spend Bitcoin from multiple inputs in one transaction, the
            signer must hold the private keys for every co-spent input.
          </p>
        </div>

        {/* Volume Summary Tile */}
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg border border-ink-100 bg-surface-sunk p-2.5">
            <div className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-ink-500">
              <ArrowDownRight size={12} className="text-emerald-600" />
              Total Inflows
            </div>
            <p className="mt-1 text-sm font-bold text-ink-900 tabular">
              {formatAmount(totalInflow)}{' '}
              <span className="text-[10px] font-medium uppercase text-ink-500">{chain}</span>
            </p>
            <p className="text-[10px] text-ink-400 mt-0.5">{inflows.length} incoming transfer(s)</p>
          </div>

          <div className="rounded-lg border border-ink-100 bg-surface-sunk p-2.5">
            <div className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-ink-500">
              <ArrowUpRight size={12} className="text-amber-600" />
              Total Outflows
            </div>
            <p className="mt-1 text-sm font-bold text-ink-900 tabular">
              {formatAmount(totalOutflow)}{' '}
              <span className="text-[10px] font-medium uppercase text-ink-500">{chain}</span>
            </p>
            <p className="text-[10px] text-ink-400 mt-0.5">{outflows.length} outgoing transfer(s)</p>
          </div>
        </div>

        {/* Member Wallets */}
        <div className="rounded-lg border border-ink-100 bg-surface-sunk p-3 space-y-2.5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-ink-500">
              Member Wallets ({cluster.addresses.length})
            </span>
            <span className="text-[10px] text-ink-400">Click to view on graph</span>
          </div>

          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-0.5">
            {cluster.addresses.map((addr) => {
              const matchedNode = nodes.find((n) => n.address === addr)
              const url = explorerUrl(chain, addr)
              const isVerified = verifiedAddress === addr

              return (
                <div
                  key={addr}
                  className={`flex items-center justify-between gap-2 p-2 rounded-md border transition-all ${
                    isVerified
                      ? 'border-cyan-400 bg-cyan-50/50 ring-1 ring-cyan-400/40 shadow-xs'
                      : 'border-ink-100 bg-surface hover:border-brand-300 hover:bg-brand-50/30'
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => {
                      if (matchedNode) {
                        onLocateNode ? onLocateNode(addr) : onSelectNode(matchedNode)
                      }
                    }}
                    className="min-w-0 flex-1 text-left cursor-pointer"
                    title="Click to locate on canvas"
                  >
                    <div className="flex items-center gap-1.5 truncate">
                      <p className="font-mono text-[11px] font-semibold text-ink-800 truncate">
                        {addr}
                      </p>
                      {isVerified && (
                        <span className="shrink-0 inline-flex items-center gap-1 rounded bg-cyan-100 px-1 py-0.2 text-[9px] font-bold text-cyan-800">
                          <span className="h-1.5 w-1.5 rounded-full bg-cyan-600 animate-pulse" />
                          On canvas
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      {matchedNode && (
                        <span className="text-[10px] text-ink-500 font-medium">
                          Hop {matchedNode.hop ?? 0} · {matchedNode.node_type}
                        </span>
                      )}
                    </div>
                  </button>

                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        onLocateNode?.(addr)
                      }}
                      className={`p-1 rounded transition-colors ${
                        isVerified
                          ? 'text-cyan-700 bg-cyan-100 font-bold'
                          : 'text-ink-400 hover:text-cyan-600 hover:bg-cyan-50'
                      }`}
                      title="Fly camera to locate this node on graph canvas"
                    >
                      <Crosshair size={13} />
                    </button>
                    <button
                      type="button"
                      onClick={() => copyText(addr, 'Address')}
                      className="p-1 rounded text-ink-400 hover:text-ink-700 hover:bg-ink-100"
                      title="Copy wallet address"
                    >
                      <Copy size={13} />
                    </button>
                    {url && (
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1 rounded text-ink-400 hover:text-ink-700 hover:bg-ink-100"
                        title="View on block explorer"
                      >
                        <ExternalLink size={13} />
                      </a>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Connected Transactions */}
        <div className="rounded-lg border border-ink-100 bg-surface-sunk p-3 space-y-2.5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-ink-500">
              Cluster Transactions ({inflows.length + outflows.length + internalTransfers.length})
            </span>
          </div>

          <div className="space-y-1.5 max-h-56 overflow-y-auto pr-0.5">
            {/* Inflows */}
            {inflows.map((tx) => (
              <TxRow key={`in-${tx.tx_hash}-${tx.source}-${tx.target}`} tx={tx} type="in" chain={chain} onCopy={copyText} />
            ))}

            {/* Internal */}
            {internalTransfers.map((tx) => (
              <TxRow key={`int-${tx.tx_hash}-${tx.source}-${tx.target}`} tx={tx} type="internal" chain={chain} onCopy={copyText} />
            ))}

            {/* Outflows */}
            {outflows.map((tx) => (
              <TxRow key={`out-${tx.tx_hash}-${tx.source}-${tx.target}`} tx={tx} type="out" chain={chain} onCopy={copyText} />
            ))}

            {inflows.length + outflows.length + internalTransfers.length === 0 && (
              <p className="text-center text-xs text-ink-400 py-3 italic">
                No active transfers connecting this cluster in the current hop boundary.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function TxRow({
  tx,
  type,
  chain,
  onCopy,
}: {
  tx: GraphEdge
  type: 'in' | 'out' | 'internal'
  chain: string
  onCopy: (text: string, label: string) => void
}) {
  const url = explorerTxUrl(chain, tx.tx_hash)
  const cleanSrc = tx.source.includes(':') ? tx.source.split(':', 2)[1] : tx.source
  const cleanTgt = tx.target.includes(':') ? tx.target.split(':', 2)[1] : tx.target

  const typeConfig = {
    in: { label: 'Inflow', badge: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
    out: { label: 'Outflow', badge: 'bg-amber-50 text-amber-700 border-amber-200' },
    internal: { label: 'Internal', badge: 'bg-blue-50 text-blue-700 border-blue-200' },
  }[type]

  const formattedDate = tx.timestamp
    ? new Date(tx.timestamp * 1000).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'UTC',
      }) + ' UTC'
    : null

  return (
    <div className="p-2 rounded-md border border-ink-100 bg-surface space-y-1">
      <div className="flex items-center justify-between gap-1">
        <span
          className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border ${typeConfig.badge}`}
        >
          {typeConfig.label} · Hop {tx.hop}
        </span>
        <span className="font-bold text-xs text-ink-900 tabular">
          {formatAmount(tx.value)}{' '}
          <span className="text-[10px] font-normal uppercase text-ink-500">{chain}</span>
        </span>
      </div>

      <div className="flex items-center justify-between text-[11px] font-mono text-ink-600 gap-1 truncate">
        <span className="truncate" title={cleanSrc}>
          {cleanSrc.slice(0, 6)}…{cleanSrc.slice(-4)}
        </span>
        <span className="text-ink-400 font-sans">→</span>
        <span className="truncate" title={cleanTgt}>
          {cleanTgt.slice(0, 6)}…{cleanTgt.slice(-4)}
        </span>
      </div>

      <div className="flex items-center justify-between text-[10px] text-ink-400 pt-0.5 border-t border-ink-50">
        <span>{formattedDate ?? `Tx: ${tx.tx_hash.slice(0, 10)}…`}</span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onCopy(tx.tx_hash, 'TxID')}
            className="hover:text-ink-700 p-0.5"
            title="Copy Tx Hash"
          >
            <Copy size={11} />
          </button>
          {url && (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-ink-700 p-0.5"
              title="View transaction on explorer"
            >
              <ExternalLink size={11} />
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
