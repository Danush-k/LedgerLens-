import { AlertTriangle, FileText, Fingerprint, Radio, SearchX } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { describeDownloadError, downloadSuspectReport, getSuspects } from '../api/client'
import { AuditChainPanel } from '../components/AuditChainPanel'
import { CaseBriefing } from '../components/CaseBriefing'
import { LiveActivityPanel } from '../components/LiveActivityPanel'
import { SuspectsPanel, type SuspectFilter } from '../components/SuspectsPanel'
import { useLiveCase } from '../hooks/useLiveCase'
import { ChainBadge } from '../components/ChainMark'
import { LoadingRing } from '../components/Logo'
import { ClusterPanel } from '../components/ClusterPanel'
import { FindingsPanel } from '../components/FindingsPanel'
import { FlagPill } from '../components/FlagPill'
import { GraphLegend } from '../components/GraphLegend'
import { GraphView } from '../components/GraphView'
import { HashVerifierModal } from '../components/HashVerifierModal'
import { LegalNoticeModal } from '../components/LegalNoticeModal'
import { CaseLinksPanel } from '../components/CaseLinksPanel'
import { Collapsible } from '../components/ui/Collapsible'
import { RiskGauge } from '../components/RiskGauge'
import { CardSkeleton } from '../components/Skeleton'
import { StatusBadge } from '../components/StatusBadge'
import { TypologyBadge } from '../components/TypologyBadge'
import type { GraphEdge, GraphNode, NextStepAction, SuspectsResult } from '../types'
import { findPath } from '../utils/findPath'

/**
 * Shown when a running trace has stopped reporting progress.
 *
 * A spinner makes no distinction between working and wedged, so a trace
 * whose worker died looks exactly like one that is merely slow - and the
 * reader waits indefinitely on something that already stopped. The server
 * reaps these after fifteen minutes; this says so before then, so the wait
 * is an informed one rather than an act of faith.
 */
function StalledNotice({ lastProgressAt }: { lastProgressAt?: string | null }) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 15_000)
    return () => clearInterval(timer)
  }, [])

  if (!lastProgressAt) return null
  const silentMs = now - new Date(lastProgressAt).getTime()
  const silentMinutes = Math.floor(silentMs / 60_000)
  // Below this a quiet spell is just a slow hop, and warning about it would
  // train the reader to ignore the warning.
  if (silentMinutes < 3) return null

  return (
    <p className="max-w-sm rounded border border-warning/40 bg-warning-soft px-3 py-2 text-xs leading-relaxed text-ink-700">
      <span className="font-medium">No progress for {silentMinutes} minutes.</span>{' '}
      A hop against a rate-limited explorer can take this long. If it stays
      silent, the trace is marked failed automatically after 15 minutes — it
      will not spin here indefinitely.
    </p>
  )
}

/**
 * The complainant's account, available but not in the way.
 *
 * An FIR narrative runs to several hundred words, and rendering it whole as
 * an italic pull-quote gave the complaint more visual weight than the trace
 * it produced - the graph and the findings, which are the reason the page
 * exists, were pushed below the fold behind text the investigator wrote
 * themselves and already knows.
 *
 * Two lines are enough to confirm this is the right case; the rest is one
 * click away, because the full text does matter when a claim in it needs
 * checking against the chain.
 */
function ComplaintNarrative({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false)
  const isLong = text.length > 240

  return (
    <div className="mt-2 max-w-3xl border-l-2 border-ink-200 pl-3">
      <p className={`text-[13px] leading-relaxed text-ink-600 ${
        expanded || !isLong ? '' : 'line-clamp-2'
      }`}>
        {text}
      </p>
      {isLong && (
        <button
          onClick={() => setExpanded(v => !v)}
          aria-expanded={expanded}
          className="mt-1 cursor-pointer text-[11px] font-medium text-brand-600 hover:underline"
        >
          {expanded ? 'Show less' : 'Read full complaint'}
        </button>
      )}
    </div>
  )
}

/**
 * Returns to wherever the investigator came from - Network Explorer with
 * its filters intact, the Overview convergence list, a linked complaint on
 * another case - rather than always dropping them on the unfiltered case
 * list.
 *
 * `location.key === 'default'` marks a case opened with no in-app history
 * behind it: a bookmark, a shared link, a fresh reload. Only then is there
 * nothing to go back to, so this falls back to the case list instead of
 * calling `navigate(-1)` and leaving the app.
 */
function BackLink() {
  const navigate = useNavigate()
  const location = useLocation()

  if (location.key === 'default') {
    return (
      <Link to="/cases" className="text-xs font-medium text-ink-500 hover:text-brand-600">
        ← All cases
      </Link>
    )
  }

  return (
    <button
      type="button"
      onClick={() => navigate(-1)}
      className="cursor-pointer text-xs font-medium text-ink-500 hover:text-brand-600"
    >
      ← Back
    </button>
  )
}

export function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>()
  const { caseData, mode, lastCheck, pollSeconds, arrivals, version, setWatch } = useLiveCase(caseId)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null)
  const [activeLegendType, setActiveLegendType] = useState<string | null>(null)
  const [noticeModalOpen, setNoticeModalOpen] = useState(false)
  const [hashModalOpen, setHashModalOpen] = useState(false)
  const [suspects, setSuspects] = useState<SuspectsResult | null>(null)
  const [suspectsLoading, setSuspectsLoading] = useState(false)
  const [suspectFilter, setSuspectFilter] = useState<SuspectFilter>('all')
  const [suspectsVersion, setSuspectsVersion] = useState(0)
  const [linksOpen, setLinksOpen] = useState(false)
  const [focusRequest, setFocusRequest] = useState<{ id: string; nonce: number } | null>(null)
  const graphRef = useRef<HTMLDivElement>(null)

  // Clear the previous case before loading the next one.
  useEffect(() => {
    setSelectedNode(null)
    setSelectedEdge(null)
    setSuspects(null)
    setSuspectFilter('all')
    setLinksOpen(false)
    window.scrollTo({ top: 0 })
  }, [caseId])

  // The suspect list is derived on the server from the graph, the linked
  // complaints and the officer's rulings, so it is re-read whenever any of
  // those change: the case reloads, live monitoring adds a transfer, or a
  // decision is saved.
  const status = caseData?.status
  useEffect(() => {
    if (!caseId || status !== 'complete') return
    let active = true
    setSuspectsLoading(true)
    getSuspects(caseId)
      .then(result => active && setSuspects(result))
      .catch(() => active && toast.error('Could not load the suspect list'))
      .finally(() => active && setSuspectsLoading(false))
    return () => { active = false }
  }, [caseId, status, version, suspectsVersion])

  const refreshSuspects = useCallback(() => setSuspectsVersion(v => v + 1), [])

  const confirmedSuspectIds = useMemo(() => new Set(
    (suspects?.suspects ?? []).filter(s => s.decision.status === 'confirmed').map(s => s.id),
  ), [suspects])

  const locateOnGraph = useCallback((address: string) => {
    const node = caseData?.graph?.nodes.find(n => n.address === address)
    if (!node) {
      toast.warning('That wallet is not on the graph')
      return
    }
    setSelectedEdge(null)
    setSelectedNode(node)
    setFocusRequest({ id: node.id, nonce: Date.now() })
    graphRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [caseData])

  const scrollTo = (id: string) =>
    window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)

  const handleStepAction = async (action: Exclude<NextStepAction, null>) => {
    switch (action) {
      case 'legal_notice':
        setNoticeModalOpen(true)
        break
      case 'filter_holding':
        setSuspectFilter('holding')
        scrollTo('suspects')
        break
      case 'review_suspects':
        setSuspectFilter('pending')
        scrollTo('suspects')
        break
      case 'linked_cases':
        setLinksOpen(true)
        scrollTo('linked-complaints')
        break
      case 'suspect_report':
        try {
          await downloadSuspectReport(caseData!.id)
          toast.success('Suspect report downloaded')
          refreshSuspects()
        } catch (err) {
          toast.error(await describeDownloadError(err))
        }
        break
    }
  }

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
  const liveEdgeCount = caseData.graph?.edges.filter(e => e.detected_live).length ?? 0

  return (
    <div className="mx-auto max-w-7xl px-8 py-8">
      <BackLink />

      {/* Case Header */}
      <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="break-all font-mono text-lg font-semibold text-ink-900">
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
          {caseData.narrative && <ComplaintNarrative text={caseData.narrative} />}
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
      <div ref={graphRef} className="mt-6 scroll-mt-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-800">
            Transaction Graph{' '}
            <span className="font-normal text-ink-400">
              ({nodeCount} address{nodeCount === 1 ? '' : 'es'})
            </span>
            {caseData.status === 'complete' && (
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${
                  mode === 'live' ? 'bg-good-soft text-good' : 'bg-warning-soft text-warning'
                }`}
                title={mode === 'live' ? `Re-checked every ${pollSeconds}s while open` : undefined}
              >
                <Radio size={11} aria-hidden="true" />
                {mode === 'live' ? 'Live' : mode === 'connecting' ? 'Reconnecting' : 'Polling'}
              </span>
            )}
            {liveEdgeCount > 0 && (
              <span className="inline-flex items-center gap-1.5 text-[11px] font-normal text-ink-500">
                <span className="inline-block h-0 w-5 border-t-2 border-dashed border-amber-500" aria-hidden="true" />
                {liveEdgeCount} transfer{liveEdgeCount === 1 ? '' : 's'} after the trace
              </span>
            )}
            {confirmedSuspectIds.size > 0 && (
              <span className="inline-flex items-center gap-1.5 text-[11px] font-normal text-ink-500">
                <span className="inline-block h-2.5 w-2.5 rounded-full border-[3px] border-double border-critical" aria-hidden="true" />
                confirmed suspect
              </span>
            )}
          </h2>
          <GraphLegend
            nodes={caseData.graph?.nodes ?? []}
            activeType={activeLegendType}
            onToggleType={(type) => setActiveLegendType((prev) => (prev === type ? null : type))}
          />
        </div>
        <div className="relative h-[560px] w-full">
          {caseData.graph && caseData.graph.nodes && caseData.graph.nodes.length > 0 ? (
            <GraphView
              nodes={caseData.graph.nodes}
              edges={caseData.graph.edges || []}
              highlightPath={highlightPath}
              clusters={caseData.clusters ?? []}
              activeTypeFilter={activeLegendType}
              selectedNode={selectedNode}
              onNodeClick={(node) => {
                setSelectedNode(node)
                setSelectedEdge(null)
              }}
              onCloseNode={() => setSelectedNode(null)}
              selectedEdge={selectedEdge}
              onEdgeClick={(edge) => {
                setSelectedEdge(edge)
                setSelectedNode(null)
              }}
              onCloseEdge={() => setSelectedEdge(null)}
              liveArrivals={arrivals}
              suspectNodeIds={confirmedSuspectIds}
              focusRequest={focusRequest}
            />
          ) : caseData.status === 'queued' || caseData.status === 'tracing' ? (
            /* Still working. Saying "no activity found" here would assert a
               finding the trace has not reached yet - the same conflation of
               "we could not look" with "we looked and found nothing" that the
               backend takes care to avoid. */
            <div className="flex h-full flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-ink-200 bg-surface px-8 text-center">
              <LoadingRing
                size={46}
                label={
                  caseData.status === 'queued'
                    ? 'Queued — waiting for a worker'
                    /* The worker's own words where it has reported them. A
                       generic label cannot say how wide the current hop is,
                       and that is the difference between a trace that looks
                       stalled and one visibly doing something. */
                    : caseData.status_message
                      ?? `Walking the chain — hop ${caseData.hop_progress} of ${caseData.hop_limit}`
                }
              />

              {/* Hops completed, as a shape rather than a sentence. A reader
                  glancing at this needs to know it is advancing, which a
                  changing number alone does not convey. */}
              {caseData.status === 'tracing' && caseData.hop_limit > 0 && (
                <div className="flex items-center gap-1.5" aria-hidden="true">
                  {Array.from({ length: caseData.hop_limit }, (_, i) => (
                    <span
                      key={i}
                      className={`h-1 w-7 rounded-full transition-colors duration-500 ${
                        i < caseData.hop_progress ? 'bg-brand-500' : 'bg-ink-200'
                      }`}
                    />
                  ))}
                </div>
              )}

              <p className="max-w-sm text-xs leading-relaxed text-ink-500">
                Each hop is a live call to a public block explorer, so a deep trace on a busy
                wallet can take a few minutes. This page updates on its own.
              </p>

              <StalledNotice lastProgressAt={caseData.last_progress_at} />
            </div>
          ) : caseData.status === 'failed' ? (
            /* A failed fetch is a statement about the data provider, not about
               the wallet. Reporting it as "no activity" would turn an outage
               into an investigative conclusion. */
            <div className="flex h-full flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-critical/40 bg-critical-soft px-8 text-center">
              <AlertTriangle size={22} className="text-critical" />
              <p className="text-sm font-medium text-critical">Trace could not be completed</p>
              <p className="max-w-lg text-xs leading-relaxed text-ink-600">
                {caseData.error ?? 'The trace failed before it produced a result.'}
              </p>
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-ink-200 bg-surface px-8 text-center">
              <SearchX size={22} className="text-ink-400" />
              <p className="text-sm font-medium text-ink-700">No outgoing on-chain activity found</p>
              <p className="max-w-sm text-xs leading-relaxed text-ink-500">
                The trace completed and this wallet has not sent funds anywhere. It may only have
                received them, or its funds may still be unspent.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* 2. WHAT THE GRAPH MEANS
          The graph is the evidence; this is the reading of it. An officer
          should be able to act on the case from here without interpreting
          a single node: what happened, who the suspects are, what is
          still moving, and what to do next. The raw analysis stays
          available underneath for anyone who needs to check the working. */}
      {caseData.status === 'complete' && (
        <div className="mt-8 space-y-6">
          {suspects?.ready && suspects.summary && (
            <CaseBriefing
              summary={suspects.summary}
              riskScore={caseData.risk_score}
              onAction={handleStepAction}
            />
          )}

          <SuspectsPanel
            caseId={caseData.id}
            result={suspects}
            loading={suspectsLoading}
            filter={suspectFilter}
            onFilterChange={setSuspectFilter}
            onChanged={refreshSuspects}
            onLocate={locateOnGraph}
          />

          <LiveActivityPanel
            caseId={caseData.id}
            status={caseData.status}
            mode={mode}
            pollSeconds={pollSeconds}
            lastCheck={lastCheck}
            checkedAt={caseData.live_checked_at}
            liveWatch={Boolean(caseData.live_watch)}
            version={version}
            arrivals={arrivals}
            onToggleWatch={setWatch}
            onLocate={locateOnGraph}
          />

          {/* 3. SUPPORTING EVIDENCE - the working behind the conclusions above. */}
          <div className="space-y-3 pt-2">
            <div>
              <h2 className="text-sm font-semibold text-ink-900">Supporting evidence</h2>
              <p className="mt-0.5 text-xs text-ink-500">
                The analysis behind the briefing and suspect list, for checking the working or
                answering a challenge.
              </p>
            </div>

            <Collapsible title="Risk assessment" hint="How the case risk score was reached">
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <div className="flex flex-col items-center">
                  {caseData.risk_score !== null ? (
                    <RiskGauge score={caseData.risk_score} />
                  ) : (
                    <p className="text-xs text-ink-400">No score recorded.</p>
                  )}
                  {caseData.flags && caseData.flags.length > 0 && (
                    <div className="mt-4 flex w-full flex-wrap justify-center gap-1.5 border-t border-ink-100 pt-3">
                      {caseData.flags.map((f) => <FlagPill key={f} flag={f} />)}
                    </div>
                  )}
                </div>
                <div className="space-y-3 text-xs leading-relaxed text-ink-600">
                  {caseData.nearest_exchange ? (
                    <p>
                      <span className="font-semibold text-ink-800">Nearest exchange: </span>
                      {caseData.nearest_exchange.name}, {caseData.nearest_exchange.hops} hop
                      {caseData.nearest_exchange.hops === 1 ? '' : 's'} from the reported wallet.
                      {' '}Attribution basis: {caseData.nearest_exchange.source || 'seed label set; source not recorded'}.
                      Deposit-address attribution identifies the exchange, not the person — that
                      requires a legal request.
                    </p>
                  ) : (
                    <p>No exchange was identified within the hop limit.</p>
                  )}
                  {caseData.recommended_action && (
                    <p>
                      <span className="font-semibold text-ink-800">System recommendation: </span>
                      {caseData.recommended_action}
                    </p>
                  )}
                </div>
              </div>
            </Collapsible>

            <Collapsible title="Detailed findings" hint="Every pattern the detectors found, with transactions">
              <FindingsPanel patterns={caseData.patterns} chain={caseData.chain} />
            </Collapsible>

            <Collapsible
              id="linked-complaints"
              title="Linked complaints"
              hint="Other cases that share wallets with this one"
              open={linksOpen}
              onOpenChange={setLinksOpen}
            >
              <CaseLinksPanel caseId={caseData.id} chain={caseData.chain} />
            </Collapsible>

            <Collapsible title="Wallet clusters" hint="Addresses that share an owner">
              <ClusterPanel clusters={caseData.clusters ?? []} />
            </Collapsible>

            <Collapsible title="Chain of custody" hint="Tamper-evident record of every action">
              <AuditChainPanel caseId={caseData.id} version={version + suspectsVersion} />
            </Collapsible>
          </div>
        </div>
      )}

      {caseData.status !== 'complete' && (
        <div className="mt-8">
          <Collapsible title="Chain of custody" hint="Tamper-evident record of every action">
            <AuditChainPanel caseId={caseData.id} />
          </Collapsible>
        </div>
      )}

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
