import { FileText, Fingerprint, SearchX } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getCase, getRelatedCases } from '../api/client'
import { ChainBadge } from '../components/ChainBadge'
import { ClusterPanel } from '../components/ClusterPanel'
import { FlagPill } from '../components/FlagPill'
import { GraphLegend } from '../components/GraphLegend'
import { GraphView } from '../components/GraphView'
import { HashVerifierModal } from '../components/HashVerifierModal'
import { LegalNoticeModal } from '../components/LegalNoticeModal'
import { NodeInspector } from '../components/NodeInspector'
import { RelatedCases } from '../components/RelatedCases'
import { RiskGauge } from '../components/RiskGauge'
import { CardSkeleton } from '../components/Skeleton'
import { StatusBadge } from '../components/StatusBadge'
import { TypologyBadge } from '../components/TypologyBadge'
import type { CaseDetail as CaseDetailType, CaseSummary, GraphNode } from '../types'
import { findPath } from '../utils/findPath'

export function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>()
  const [caseData, setCaseData] = useState<CaseDetailType | null>(null)
  const [related, setRelated] = useState<CaseSummary[]>([])
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [noticeModalOpen, setNoticeModalOpen] = useState(false)
  const [hashModalOpen, setHashModalOpen] = useState(false)

  useEffect(() => {
    if (!caseId) return
    let active = true
    setSelectedNode(null)

    const load = async () => {
      const c = await getCase(caseId)
      if (!active) return
      setCaseData(c)
      if (c.status === 'complete') {
        getRelatedCases(caseId).then((r) => active && setRelated(r))
      }
    }
    load()

    const interval = setInterval(() => {
      if (caseData && (caseData.status === 'complete' || caseData.status === 'failed')) return
      load()
    }, 2500)

    return () => {
      active = false
      clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, caseData?.status])

  const highlightPath = useMemo(() => {
    if (!caseData?.graph || !caseData.nearest_exchange) return []
    const rootId = `${caseData.chain}:${caseData.reported_address}`
    const targetId = `${caseData.nearest_exchange.chain}:${caseData.nearest_exchange.address}`
    return findPath(caseData.graph.edges, rootId, targetId)
  }, [caseData])

  if (!caseData) {
    return (
      <div className="mx-auto max-w-7xl px-8 py-8">
        <div className="mb-2 h-3 w-16 animate-skeleton rounded bg-ink-200" />
        <div className="mt-2 h-7 w-96 animate-skeleton rounded-md bg-ink-200" />
        <div className="mt-3 h-4 w-56 animate-skeleton rounded-md bg-ink-200" />
        <div className="mt-8 space-y-6">
          <div className="h-[420px] animate-skeleton rounded-lg bg-ink-200" />
          <div className="grid grid-cols-2 gap-6">
            <CardSkeleton lines={4} />
            <CardSkeleton lines={4} />
          </div>
        </div>
      </div>
    )
  }

  const nodeCount = caseData.graph?.nodes.length ?? 0

  return (
    <div className="mx-auto max-w-7xl px-8 py-8">
      <Link to="/cases" className="text-xs font-medium text-ink-500 hover:text-brand-600">
        ← All cases
      </Link>

      {/* Case Header */}
      <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="break-all font-mono text-lg font-bold text-ink-900">
              {caseData.reported_address}
            </h1>
            <ChainBadge chain={caseData.chain} />
            {caseData.fraud_typology && caseData.fraud_typology !== 'unclassified' && (
              <TypologyBadge typology={caseData.fraud_typology} />
            )}
          </div>
          <div className="mt-2 flex items-center gap-3 text-sm text-ink-500">
            <StatusBadge status={caseData.status} />
            {caseData.complaint_ref && <span>Ref: {caseData.complaint_ref}</span>}
            {caseData.created_by && <span>Filed by {caseData.created_by}</span>}
            <span>
              Hop {caseData.hop_progress} / {caseData.hop_limit}
            </span>
          </div>
          {caseData.narrative && (
            <p className="mt-2 max-w-xl text-sm italic text-ink-500">&quot;{caseData.narrative}&quot;</p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Verify Evidence Hash Button */}
          <button
            onClick={() => setHashModalOpen(true)}
            className="flex items-center gap-1.5 rounded-lg border border-ink-200 bg-surface px-3 py-2 text-xs font-medium text-ink-700 shadow-2xs hover:border-brand-500 hover:text-brand-600 transition-colors"
            title="Verify evidence hash integrity"
          >
            <Fingerprint size={14} className="text-brand-600" />
            Verify Hash
          </button>

          {/* Legal Notice Generation Button */}
          <button
            disabled={caseData.status !== 'complete'}
            onClick={() => setNoticeModalOpen(true)}
            className={`flex items-center gap-2 rounded-lg border px-3.5 py-2 text-xs font-semibold shadow-2xs transition-colors ${
              caseData.status === 'complete'
                ? 'border-ink-200 bg-surface text-ink-800 hover:border-brand-500 hover:text-brand-600'
                : 'cursor-not-allowed border-ink-100 text-ink-300'
            }`}
          >
            <FileText size={15} />
            Generate Legal Notice (Sec 91/94)
          </button>
        </div>
      </div>

      {/* 1. FULL WIDTH TRANSACTION GRAPH CANVAS */}
      <div className="mt-6 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink-800">
            Transaction Graph{' '}
            <span className="font-normal text-ink-400">
              ({nodeCount} address{nodeCount === 1 ? '' : 'es'})
            </span>
          </h2>
          <GraphLegend />
        </div>
        <div className="relative h-[520px] w-full">
          {caseData.graph && caseData.graph.nodes && caseData.graph.nodes.length > 0 ? (
            <>
              <GraphView
                nodes={caseData.graph.nodes}
                edges={caseData.graph.edges || []}
                highlightPath={highlightPath}
                onNodeClick={setSelectedNode}
              />
              {selectedNode && <NodeInspector node={selectedNode} onClose={() => setSelectedNode(null)} />}
            </>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-ink-200 px-8 text-center bg-surface">
              <SearchX size={22} className="text-ink-400" />
              <p className="text-sm font-medium text-ink-700">No outgoing on-chain activity found</p>
            </div>
          )}
        </div>
      </div>

      {/* 2. INFORMATION CARDS (PLACED DIRECTLY DOWN BELOW THE GRAPH) */}
      <div className="mt-8 space-y-6">
        {/* Row 1: Target VASP & Risk Assessment Grid */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* Target Exchange & Attribution Card */}
          <div className="rounded-xl border border-ink-100 bg-surface p-5 shadow-2xs">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-500">Target VASP / Nearest Exchange</h2>
            {caseData.nearest_exchange ? (
              <div className="mt-3 space-y-2">
                <p className="text-lg font-extrabold text-emerald-600">{caseData.nearest_exchange.name}</p>
                <p className="break-all font-mono text-xs text-ink-600 bg-ink-50 p-2.5 rounded-lg border border-ink-100">
                  {caseData.nearest_exchange.address}
                </p>
                <p className="text-xs text-ink-500 font-medium">
                  Distance: <span className="text-ink-800 font-bold">{caseData.nearest_exchange.hops} hop{caseData.nearest_exchange.hops === 1 ? '' : 's'}</span> away
                </p>
              </div>
            ) : (
              <p className="mt-2 text-xs text-ink-500">
                {caseData.status === 'complete'
                  ? 'No exchange identified within the hop limit.'
                  : 'Tracing in progress...'}
              </p>
            )}

            {caseData.recommended_action && (
              <div className="mt-4 border-t border-ink-100 pt-3">
                <span className="text-[11px] font-semibold uppercase text-brand-600">Recommended Action</span>
                <p className="mt-1 text-xs text-ink-700 leading-relaxed">{caseData.recommended_action}</p>
              </div>
            )}
          </div>

          {/* Risk Assessment & Forensic Flags Card */}
          <div className="rounded-xl border border-ink-100 bg-surface p-5 shadow-2xs">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-500 mb-3">Risk Assessment &amp; Flags</h2>
            {caseData.risk_score !== null ? (
              <div className="flex flex-col items-center">
                <RiskGauge score={caseData.risk_score} />
                
                {caseData.flags && caseData.flags.length > 0 && (
                  <div className="mt-4 w-full border-t border-ink-100 pt-3">
                    <span className="text-[11px] font-semibold text-ink-500 block mb-2">Detected Flags:</span>
                    <div className="flex flex-wrap gap-1.5">
                      {caseData.flags.map((f) => (
                        <FlagPill key={f} flag={f} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-ink-400">Scoring pending...</p>
            )}
          </div>
        </div>

        {/* Row 2: Clusters & Related Cases */}
        <div className="space-y-6">
          <ClusterPanel clusters={caseData.clusters ?? []} />
          <RelatedCases cases={related} />
        </div>
      </div>

      {/* Modals */}
      <LegalNoticeModal
        caseDetail={caseData}
        open={noticeModalOpen}
        onClose={() => setNoticeModalOpen(false)}
      />

      <HashVerifierModal
        open={hashModalOpen}
        onClose={() => setHashModalOpen(false)}
        initialCaseId={caseData.id}
      />
    </div>
  )
}
