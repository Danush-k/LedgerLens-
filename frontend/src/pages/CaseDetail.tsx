import { Download, ExternalLink, Loader2, SearchX } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { downloadReport, getCase, getIntegrationLog, getMlStatus, getRelatedCases } from '../api/client'
import { ChainBadge } from '../components/ChainBadge'
import { ClusterPanel } from '../components/ClusterPanel'
import { FlagPill } from '../components/FlagPill'
import { GraphLegend } from '../components/GraphLegend'
import { GraphView } from '../components/GraphView'
import { IntegrationLog } from '../components/IntegrationLog'
import { NodeInspector } from '../components/NodeInspector'
import { RelatedCases } from '../components/RelatedCases'
import { CardSkeleton } from '../components/Skeleton'
import { RiskGauge } from '../components/RiskGauge'
import { StatusBadge } from '../components/StatusBadge'
import { TypologyBadge } from '../components/TypologyBadge'
import type { AuditEvent, CaseDetail as CaseDetailType, CaseSummary, GraphNode, MlStatus } from '../types'
import { findPath } from '../utils/findPath'

export function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>()
  const [caseData, setCaseData] = useState<CaseDetailType | null>(null)
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [related, setRelated] = useState<CaseSummary[]>([])
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [mlStatus, setMlStatus] = useState<MlStatus | null>(null)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    if (!caseId) return
    let active = true
    setSelectedNode(null)

    const load = async () => {
      const [c, log] = await Promise.all([getCase(caseId), getIntegrationLog(caseId)])
      if (!active) return
      setCaseData(c)
      setEvents(log)
      if (c.status === 'complete') {
        getRelatedCases(caseId).then((r) => active && setRelated(r))
        if (c.risk_score_ml === null) {
          getMlStatus().then((s) => active && setMlStatus(s))
        }
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
    // The backend already normalizes addresses consistently (lowercase for
    // EVM, untouched for case-sensitive Bitcoin base58) - use its values
    // verbatim rather than re-lowercasing, which would break Bitcoin ids.
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
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="h-[420px] animate-skeleton rounded-lg bg-ink-200 lg:col-span-2" />
          <div className="space-y-6">
            <CardSkeleton lines={4} />
            <CardSkeleton lines={2} />
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
            <p className="mt-2 max-w-xl text-sm italic text-ink-500">"{caseData.narrative}"</p>
          )}
        </div>

        <button
          disabled={caseData.status !== 'complete' || downloading}
          onClick={async () => {
            setDownloading(true)
            try {
              await downloadReport(caseData.id)
              toast.success('Report downloaded')
            } catch {
              toast.error('Could not generate the report', { description: 'Try again in a moment.' })
            } finally {
              setDownloading(false)
            }
          }}
          className={`flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-semibold transition-colors ${
            caseData.status === 'complete'
              ? 'border-ink-200 text-ink-800 hover:border-brand-500 hover:text-brand-600'
              : 'cursor-not-allowed border-ink-100 text-ink-300'
          }`}
        >
          {downloading ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
          Download evidence report
        </button>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink-800">
              Transaction graph{' '}
              <span className="font-normal text-ink-400">
                ({nodeCount} address{nodeCount === 1 ? '' : 'es'})
              </span>
            </h2>
            <GraphLegend />
          </div>
          <div className="relative h-[420px]">
            {caseData.graph && caseData.graph.edges.length > 0 ? (
              <>
                <GraphView
                  nodes={caseData.graph.nodes}
                  edges={caseData.graph.edges}
                  highlightPath={highlightPath}
                  onNodeClick={setSelectedNode}
                />
                {selectedNode && <NodeInspector node={selectedNode} onClose={() => setSelectedNode(null)} />}
              </>
            ) : caseData.status === 'complete' ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-ink-200 px-8 text-center">
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-ink-100">
                  <SearchX size={20} className="text-ink-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-ink-700">No outgoing on-chain activity found</p>
                  <p className="mt-1 max-w-sm text-xs text-ink-400">
                    This wallet hasn't sent any traceable transfers within the {caseData.hop_limit}-hop limit — it
                    may be a pure deposit address, or currently dormant. A genuine, checked result, not an error.
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-ink-200 px-8 text-center">
                <Loader2 size={22} className="animate-spin text-brand-400" />
                <p className="text-sm text-ink-400">Tracing in progress — the graph will appear here once transfers are found.</p>
              </div>
            )}
          </div>

          <div className="mt-6 rounded-xl border border-ink-100 bg-surface p-6 shadow-sm">
            <div className="mb-3 flex items-center gap-1.5">
              <ExternalLink size={14} className="text-ink-400" />
              <h2 className="text-sm font-semibold text-ink-800">Integration log</h2>
            </div>
            <IntegrationLog events={events} />
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border border-ink-100 bg-surface p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold text-ink-800">Risk assessment</h2>
            {caseData.risk_score !== null ? (
              <div className="flex flex-col items-center">
                <RiskGauge score={caseData.risk_score} />
                <p className="mt-1 text-[11px] text-ink-400">Explainable v1 (rule-based)</p>
                {caseData.risk_breakdown && (
                  <div className="mt-4 w-full space-y-1.5 text-xs">
                    {Object.entries(caseData.risk_breakdown).map(([signal, weight]) => (
                      <div key={signal} className="flex justify-between text-ink-500">
                        <span>{signal.replace(/_/g, ' ')}</span>
                        <span className="font-medium text-ink-700">+{weight}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="mt-4 w-full border-t border-ink-100 pt-3">
                  {caseData.risk_score_ml !== null ? (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-ink-500">ML-assisted score (v2, illustrative)</span>
                      <span className="font-semibold text-ink-800">{Math.round(caseData.risk_score_ml)}</span>
                    </div>
                  ) : mlStatus && !mlStatus.trained ? (
                    <p className="text-[11px] text-ink-400">
                      ML score unavailable: {mlStatus.reason_unavailable} ({mlStatus.trained_on}/
                      {mlStatus.min_required} cases so far)
                    </p>
                  ) : null}
                </div>
              </div>
            ) : (
              <p className="text-sm text-ink-400">Scoring will appear once tracing completes.</p>
            )}
          </div>

          <div className="rounded-xl border border-ink-100 bg-surface p-6 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-ink-800">Nearest exchange / VASP</h2>
            {caseData.nearest_exchange ? (
              <div>
                <p className="text-base font-bold text-emerald-600">{caseData.nearest_exchange.name}</p>
                <p className="mt-1 break-all font-mono text-xs text-ink-500">
                  {caseData.nearest_exchange.address}
                </p>
                <p className="mt-1 text-xs text-ink-500">
                  {caseData.nearest_exchange.hops} hop{caseData.nearest_exchange.hops === 1 ? '' : 's'} away
                </p>
              </div>
            ) : (
              <p className="text-sm text-ink-400">
                {caseData.status === 'complete'
                  ? 'No exchange identified within the hop limit.'
                  : 'Still tracing…'}
              </p>
            )}
          </div>

          {caseData.recommended_action && (
            <div className="rounded-xl border border-brand-500/20 bg-brand-500/[0.06] p-6">
              <h2 className="mb-2 text-sm font-semibold text-brand-600">Recommended action</h2>
              <p className="text-sm leading-relaxed text-ink-700">{caseData.recommended_action}</p>
            </div>
          )}

          {caseData.flags && caseData.flags.length > 0 && (
            <div className="rounded-xl border border-ink-100 bg-surface p-6 shadow-sm">
              <h2 className="mb-3 text-sm font-semibold text-ink-800">Flags</h2>
              <div className="flex flex-wrap gap-2">
                {caseData.flags.map((f) => (
                  <FlagPill key={f} flag={f} />
                ))}
              </div>
            </div>
          )}

          <ClusterPanel clusters={caseData.clusters ?? []} />

          <RelatedCases cases={related} />
        </div>
      </div>
    </div>
  )
}
