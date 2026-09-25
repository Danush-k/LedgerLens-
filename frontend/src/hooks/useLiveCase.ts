/**
 * A case that keeps itself current.
 *
 * Loads the case once, then listens on the server's event stream for
 * everything that changes afterwards: a running trace's progress, the moment
 * it finishes, and - once it has - any new transaction on the wallets it
 * found. New transfers are merged into the graph in place rather than by
 * re-fetching the case, so the page updates without flicker or losing the
 * investigator's selection.
 *
 * If the stream cannot be held open (a buffering proxy, an old browser) the
 * hook falls back to polling. Polling still reaches the live monitor - every
 * case read counts as someone looking at it - so the page degrades to slower
 * updates, never to a frozen one.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { getCase, liveStreamUrl, setLiveWatch } from '../api/client'
import type { CaseDetail, GraphEdge, GraphNode, LiveCheck } from '../types'
import { formatAmount } from '../utils/format'

export type LiveMode = 'connecting' | 'live' | 'polling'

const POLL_FALLBACK_MS = 5_000

const UNITS: Record<string, string> = {
  bitcoin: 'BTC', ethereum: 'ETH', bsc: 'BNB', polygon: 'MATIC', tron: 'USDT',
}

export function edgeKey(edge: Pick<GraphEdge, 'tx_hash' | 'source' | 'target'>) {
  return `${edge.tx_hash}|${edge.source}|${edge.target}`
}

function short(address: string) {
  return address.length > 16 ? `${address.slice(0, 8)}…${address.slice(-4)}` : address
}

export function useLiveCase(caseId: string | undefined) {
  const [caseData, setCaseData] = useState<CaseDetail | null>(null)
  const [mode, setMode] = useState<LiveMode>('connecting')
  const [lastCheck, setLastCheck] = useState<LiveCheck | null>(null)
  const [pollSeconds, setPollSeconds] = useState(30)
  // Edge keys and node ids that arrived while this page was open. Kept apart
  // from `detected_live` on the data, which marks everything found after the
  // trace - including movement seen by someone else, yesterday.
  const [arrivals, setArrivals] = useState<Set<string>>(() => new Set())
  // Bumped whenever the case's content changes, so dependent views (the
  // suspect list, the live feed) know to refresh.
  const [version, setVersion] = useState(0)

  const caseRef = useRef<CaseDetail | null>(null)
  const commit = useCallback((next: CaseDetail | null) => {
    caseRef.current = next
    setCaseData(next)
  }, [])

  const noteArrivals = useCallback((edges: GraphEdge[], nodes: GraphNode[]) => {
    if (!edges.length && !nodes.length) return
    setArrivals(prev => {
      const next = new Set(prev)
      edges.forEach(e => next.add(edgeKey(e)))
      nodes.forEach(n => next.add(n.id))
      return next
    })
  }, [])

  const announce = useCallback((edges: GraphEdge[], nodes: GraphNode[], chain: string) => {
    if (!edges.length) return
    const byId = new Map((caseRef.current?.graph?.nodes ?? []).map(n => [n.id, n]))
    nodes.forEach(n => byId.set(n.id, n))
    const unit = UNITS[chain] ?? ''
    const first = edges[0]
    const to = byId.get(first.target)
    const destination = to?.label_name ?? short(to?.address ?? first.target.split(':')[1] ?? '')
    const total = edges.reduce((sum, e) => sum + e.value, 0)
    toast.warning(
      edges.length === 1 ? 'New transaction on this case' : `${edges.length} new transactions on this case`,
      {
        description: edges.length === 1
          ? `${formatAmount(first.value)} ${unit} moved to ${destination}`
          : `${formatAmount(total)} ${unit} moved, including to ${destination}`,
        duration: 8_000,
      },
    )
  }, [])

  const load = useCallback(async () => {
    if (!caseId) return
    try {
      const next = await getCase(caseId)
      const prev = caseRef.current
      if (prev && prev.id === next.id && prev.graph && next.graph) {
        // Polling path: work out what arrived since the last read.
        const known = new Set(prev.graph.edges.map(edgeKey))
        const knownNodes = new Set(prev.graph.nodes.map(n => n.id))
        const edges = next.graph.edges.filter(e => e.detected_live && !known.has(edgeKey(e)))
        const nodes = next.graph.nodes.filter(n => n.detected_live && !knownNodes.has(n.id))
        noteArrivals(edges, nodes)
        announce(edges, nodes, next.chain)
      }
      commit(next)
      setVersion(v => v + 1)
    } catch {
      // A 401 is handled by the API client; anything else leaves the last
      // good copy on screen rather than blanking the page.
    }
  }, [caseId, commit, noteArrivals, announce])

  useEffect(() => {
    if (!caseId) return
    let active = true
    let source: EventSource | null = null
    let pollTimer: number | undefined

    commit(null)
    setArrivals(new Set())
    setLastCheck(null)
    setMode('connecting')

    const startPolling = () => {
      if (pollTimer !== undefined || !active) return
      setMode('polling')
      pollTimer = window.setInterval(load, POLL_FALLBACK_MS)
    }

    const parse = (event: MessageEvent) => {
      try {
        return JSON.parse(event.data)
      } catch {
        return null
      }
    }

    load().then(() => {
      if (!active) return
      if (typeof EventSource === 'undefined') {
        startPolling()
        return
      }
      source = new EventSource(liveStreamUrl(caseId))

      source.onopen = () => active && setMode('live')

      source.addEventListener('hello', (event) => {
        const data = parse(event as MessageEvent)
        if (!data) return
        setMode('live')
        setPollSeconds(data.poll_seconds ?? 30)
      })

      source.addEventListener('status', (event) => {
        const data = parse(event as MessageEvent)
        const current = caseRef.current
        if (!data || !current) return
        commit({
          ...current,
          status: data.status,
          hop_progress: data.hop_progress,
          hop_limit: data.hop_limit,
          status_message: data.status_message,
          last_progress_at: data.last_progress_at,
          risk_score: data.risk_score,
          live_watch: data.live_watch,
          live_event_count: data.live_event_count,
          live_checked_at: data.live_checked_at,
          live_last_event_at: data.live_last_event_at,
        })
      })

      // The trace has just finished (or failed): the graph arrived all at
      // once, so fetch the case rather than stream it.
      source.addEventListener('refresh', () => load())

      source.addEventListener('check', (event) => {
        const data = parse(event as MessageEvent)
        if (data) setLastCheck(data)
      })

      source.addEventListener('transactions', (event) => {
        const data = parse(event as MessageEvent)
        const current = caseRef.current
        if (!data) return
        if (!current?.graph) {
          load()
          return
        }
        const knownNodes = new Set(current.graph.nodes.map(n => n.id))
        const knownEdges = new Set(current.graph.edges.map(edgeKey))
        const nodes: GraphNode[] = (data.nodes ?? []).filter((n: GraphNode) => !knownNodes.has(n.id))
        const edges: GraphEdge[] = (data.edges ?? []).filter((e: GraphEdge) => !knownEdges.has(edgeKey(e)))
        if (!nodes.length && !edges.length) return

        commit({
          ...current,
          ...(data.case ?? {}),
          graph: {
            ...current.graph,
            nodes: [...current.graph.nodes, ...nodes],
            edges: [...current.graph.edges, ...edges],
          },
        })
        noteArrivals(edges, nodes)
        announce(edges, nodes, current.chain)
        setVersion(v => v + 1)
      })

      source.addEventListener('gone', () => {
        source?.close()
        source = null
      })

      source.onerror = () => {
        if (!active || !source) return
        if (source.readyState === EventSource.CLOSED) {
          // The server refused the stream outright - fall back for good.
          source.close()
          source = null
          startPolling()
        } else {
          // EventSource is already retrying on its own.
          setMode('connecting')
        }
      }
    })

    return () => {
      active = false
      source?.close()
      if (pollTimer !== undefined) window.clearInterval(pollTimer)
    }
  }, [caseId, commit, load, noteArrivals, announce])

  const setWatch = useCallback(async (enabled: boolean) => {
    if (!caseId) return
    try {
      const result = await setLiveWatch(caseId, enabled)
      const current = caseRef.current
      if (current) commit({ ...current, live_watch: result.live_watch })
      toast.success(enabled
        ? 'This case will keep being watched after you close it'
        : 'Background watching turned off')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      toast.error(detail ?? 'Could not change background watching')
    }
  }, [caseId, commit])

  const clearArrivals = useCallback(() => setArrivals(new Set()), [])

  return { caseData, mode, lastCheck, pollSeconds, arrivals, version, reload: load, setWatch, clearArrivals }
}
