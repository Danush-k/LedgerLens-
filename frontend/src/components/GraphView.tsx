import type { Core } from 'cytoscape'
import {
  Camera,
  Coins,
  Focus,
  Maximize2,
  Minimize2,
  MousePointer,
  RefreshCw,
  Search,
  Sparkles,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'
import { toast } from 'sonner'
import type { GraphEdge, GraphNode, WalletCluster } from '../types'
import { formatAmount } from '../utils/format'
import { NodeInspector } from './NodeInspector'
import { EdgeInspector } from './EdgeInspector'
import { ClusterInspector } from './ClusterInspector'

const NODE_COLORS: Record<string, string> = {
  reported: '#3b82f6',
  exchange: '#22c55e',
  mixer: '#ef4444',
  bridge: '#a855f7',
  unresolved: '#94a3b8',
  intermediate: '#64748b',
}

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  highlightPath?: string[] // node ids on the path to the nearest exchange
  onNodeClick?: (node: GraphNode) => void
  clusters?: WalletCluster[]
  activeTypeFilter?: string | null
  selectedNode?: GraphNode | null
  onCloseNode?: () => void
  selectedEdge?: GraphEdge | null
  onEdgeClick?: (edge: GraphEdge) => void
  onCloseEdge?: () => void
  /** Edge keys (tx|source|target) and node ids that arrived while the page was open. */
  liveArrivals?: Set<string>
  /** Node ids an officer has confirmed as suspects. */
  suspectNodeIds?: Set<string>
  /** Centre the canvas on a node; the nonce lets the same node be requested twice. */
  focusRequest?: { id: string; nonce: number } | null
}

const EMPTY_SET: Set<string> = new Set()

type LayoutType = 'hops' | 'breadthfirst' | 'concentric' | 'circle' | 'grid' | 'cose'

export function GraphView({
  nodes,
  edges,
  highlightPath = [],
  onNodeClick,
  clusters = [],
  activeTypeFilter = null,
  selectedNode = null,
  onCloseNode,
  selectedEdge = null,
  onEdgeClick,
  onCloseEdge,
  liveArrivals = EMPTY_SET,
  suspectNodeIds = EMPTY_SET,
  focusRequest = null,
}: Props) {
  const cyRef = useRef<Core | null>(null)

  // Money flows left to right by hop. A reader should never have to work
  // out which direction the funds moved.
  const [layoutName, setLayoutName] = useState<LayoutType>('hops')
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [pathOnly, setPathOnly] = useState(false)
  const [showValues, setShowValues] = useState(true)
  const [wheelZoomEnabled, setWheelZoomEnabled] = useState(false)
  const [selectedCluster, setSelectedCluster] = useState<WalletCluster | null>(null)
  const [isClusterHighlighted, setIsClusterHighlighted] = useState(false)
  const [verifiedNodeAddress, setVerifiedNodeAddress] = useState<string | null>(null)
  const [declutterDust, setDeclutterDust] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearchOpen, setIsSearchOpen] = useState(false)
  const searchInputRef = useRef<HTMLInputElement>(null)

  // Autocomplete matching nodes for quick address finder
  const searchMatches = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    if (!q) return []
    return nodes
      .filter(
        (n) =>
          n.address.toLowerCase().includes(q) ||
          (n.label_name && n.label_name.toLowerCase().includes(q))
      )
      .slice(0, 8)
  }, [nodes, searchQuery])

  // Keyboard shortcut '/' or 'Cmd+K' to quick-focus the search bar
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        (e.key === '/' || (e.key === 'k' && (e.metaKey || e.ctrlKey))) &&
        document.activeElement?.tagName !== 'INPUT' &&
        document.activeElement?.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault()
        setIsSearchOpen(true)
        setTimeout(() => searchInputRef.current?.focus(), 40)
      }
      if (e.key === 'Escape') {
        setIsSearchOpen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  /**
   * Addresses proven to share a key holder are drawn inside one box.
   */
  const clusterParents = useMemo(() => {
    const parentOf = new Map<string, string>()
    const parents: { id: string; label: string }[] = []
    const clusterById = new Map<string, WalletCluster>()

    clusters
      .filter((c) => c.type === 'common_input' && c.addresses.length > 1)
      .forEach((cluster, index) => {
        const parentId = `cluster-${index}`
        let claimed = 0
        cluster.addresses.forEach((address) => {
          const node = nodes.find((n) => n.address === address)
          if (node && !parentOf.has(node.id)) {
            parentOf.set(node.id, parentId)
            claimed += 1
          }
        })
        // A box around a single visible wallet says nothing.
        if (claimed > 1) {
          parents.push({ id: parentId, label: `Same owner · ${claimed} wallets` })
          clusterById.set(parentId, cluster)
        } else {
          cluster.addresses.forEach((address) => {
            const node = nodes.find((n) => n.address === address)
            if (node && parentOf.get(node.id) === parentId) parentOf.delete(node.id)
          })
        }
      })

    return { parentOf, parents, clusterById }
  }, [clusters, nodes])

  // Dynamically toggle prominent highlight classes on the selected node/edge/cluster/filter/verified
  useEffect(() => {
    if (!cyRef.current) return
    const cy = cyRef.current
    cy.batch(() => {
      // 1. Reset dynamic classes
      cy.nodes().removeClass(
        'selected-node type-highlighted type-dimmed target-verified declutter-dimmed cluster-highlighted cluster-dimmed selected-cluster'
      )
      cy.edges().removeClass(
        'connected-to-selected selected-edge type-dimmed cluster-highlighted cluster-dimmed'
      )

      // 2. Selected Node
      if (selectedNode) {
        const ele = cy.getElementById(selectedNode.id)
        if (ele.length > 0) {
          ele.addClass('selected-node')
          ele.connectedEdges().addClass('connected-to-selected')
        }
      }

      // 3. Selected Edge
      if (selectedEdge) {
        const matching = cy.edges().filter((ele: any) => {
          const d = ele.data()
          return (
            d.tx_hash === selectedEdge.tx_hash &&
            d.source === selectedEdge.source &&
            d.target === selectedEdge.target
          )
        })
        matching.addClass('selected-edge')
      }

      // 4. Cluster Selection & Highlights
      if (selectedCluster) {
        const parentId = Array.from(clusterParents.clusterById.entries()).find(
          ([_, c]) => c === selectedCluster
        )?.[0]
        if (parentId) {
          cy.getElementById(parentId).addClass('selected-cluster')
        }

        if (isClusterHighlighted) {
          const addrs = new Set(selectedCluster.addresses)
          cy.nodes().forEach((n: any) => {
            if (n.hasClass('cluster-parent')) return
            const fullAddr = n.data('fullAddress')
            if (addrs.has(fullAddr)) {
              n.addClass('cluster-highlighted')
            } else {
              n.addClass('cluster-dimmed')
            }
          })

          cy.edges().forEach((e: any) => {
            const rawSrc = e.data('source') ?? ''
            const rawTgt = e.data('target') ?? ''
            const cleanSrc = rawSrc.includes(':') ? rawSrc.split(':', 2)[1] : rawSrc
            const cleanTgt = rawTgt.includes(':') ? rawTgt.split(':', 2)[1] : rawTgt
            if (addrs.has(cleanSrc) || addrs.has(cleanTgt)) {
              e.addClass('cluster-highlighted')
            } else {
              e.addClass('cluster-dimmed')
            }
          })
        }
      }

      // 5. Verified Node from Cluster Inspector (Target Pulse)
      if (verifiedNodeAddress) {
        const verifiedEle = cy.nodes().filter((n: any) => n.data('fullAddress') === verifiedNodeAddress)
        verifiedEle.addClass('target-verified')
      }

      // 6. Interactive Legend Type Filter
      if (activeTypeFilter) {
        cy.nodes().forEach((n: any) => {
          if (n.hasClass('cluster-parent')) return
          if (n.data('type') === activeTypeFilter) {
            n.addClass('type-highlighted')
          } else {
            n.addClass('type-dimmed')
          }
        })
        cy.edges().addClass('type-dimmed')
      }

      // 7. Declutter Dust Mode
      if (declutterDust) {
        cy.nodes().forEach((n: any) => {
          if (n.hasClass('cluster-parent')) return
          const outDegree = n.outgoers('edge').length
          const taintVal = n.data('taint') ?? 0
          if (outDegree === 0 && taintVal < 0.0005 && n.data('type') === 'unresolved') {
            n.addClass('declutter-dimmed')
          }
        })
      }
    })
  }, [
    selectedNode,
    selectedEdge,
    selectedCluster,
    isClusterHighlighted,
    clusterParents,
    verifiedNodeAddress,
    activeTypeFilter,
    declutterDust,
  ])


  const elements = useMemo(() => {
    const pathSet = new Set(highlightPath)
    const nodeEls = nodes.map((n) => {
      const onPath = pathSet.has(n.id)
      return {
        data: {
          id: n.id,
          label: n.label_name ?? `${n.address.slice(0, 6)}…${n.address.slice(-4)}`,
          type: n.node_type,
          fullAddress: n.address,
          hop: n.hop ?? 0,
          taint: n.taint_ratio ?? 0,
          parent: clusterParents.parentOf.get(n.id),
        },
        classes: [
          onPath ? 'on-path' : '',
          pathOnly && !onPath ? 'dimmed' : '',
          n.detected_live ? 'live-detected' : '',
          liveArrivals.has(n.id) ? 'live-new' : '',
          suspectNodeIds.has(n.id) ? 'suspect-confirmed' : '',
          selectedNode?.id === n.id ? 'selected-node' : '',
        ].filter(Boolean).join(' '),
      }
    })

    const edgeEls = edges.map((e, i) => {
      const onPath = pathSet.has(e.source) && pathSet.has(e.target)
      const isSelected =
        selectedEdge &&
        selectedEdge.tx_hash === e.tx_hash &&
        selectedEdge.source === e.source &&
        selectedEdge.target === e.target
      return {
        data: {
          id: `${e.tx_hash}-${i}`,
          source: e.source,
          target: e.target,
          value: showValues ? formatAmount(e.value) : '',
          amount: e.value,
          tx_hash: e.tx_hash,
          hop: e.hop,
          timestamp: e.timestamp,
          tainted_value: e.tainted_value,
        },
        classes: [
          onPath ? 'on-path' : '',
          pathOnly && !onPath ? 'dimmed' : '',
          e.detected_live ? 'live-detected' : '',
          liveArrivals.has(`${e.tx_hash}|${e.source}|${e.target}`) ? 'live-new' : '',
          isSelected ? 'selected-edge' : '',
        ].filter(Boolean).join(' '),
      }
    })

    const parentEls = clusterParents.parents.map((p) => ({
      data: { id: p.id, label: p.label, type: 'cluster' },
      classes: 'cluster-parent',
    }))

    // Parents must precede their children or Cytoscape drops the parent.
    return [...parentEls, ...nodeEls, ...edgeEls]
  }, [nodes, edges, highlightPath, pathOnly, showValues, clusterParents, selectedNode, selectedEdge,
      liveArrivals, suspectNodeIds])

  // New arrivals pulse so the eye finds them on a busy canvas; everything
  // else found after the trace keeps a steady amber mark.
  useEffect(() => {
    const cy = cyRef.current
    if (!cy || liveArrivals.size === 0) return
    let on = false
    const timer = window.setInterval(() => {
      on = !on
      cy.elements('.live-new').toggleClass('live-pulse', on)
    }, 700)
    return () => {
      window.clearInterval(timer)
      cy.elements('.live-pulse').removeClass('live-pulse')
    }
  }, [liveArrivals, elements])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy || !focusRequest) return
    const target = cy.getElementById(focusRequest.id)
    if (target.length === 0) return
    cy.animate({
      center: { eles: target },
      zoom: Math.max(cy.zoom(), 1.6),
      duration: 450,
      easing: 'ease-in-out',
    })
  }, [focusRequest])

  // Edge thickness is proportional to amount, so the main flow is visually
  // obvious and dust transactions recede instead of competing with it.
  // Scaled against the largest transfer in this graph rather than an
  // absolute scale, since a graph may span eight orders of magnitude.
  const maxAmount = useMemo(
    () => Math.max(...edges.map((e) => e.value), Number.EPSILON),
    [edges],
  )

  const surface = '#ffffff'
  const labelColor = '#1f2328'
  const nodeRing = '#ffffff'
  const onPathRing = '#0b1120'
  const edgeLine = '#cbd5e1'
  const edgeLabelColor = '#64748b'
  const brandLine = '#0969da'

  const stylesheet = [
    {
      selector: 'node',
      style: {
        // Known services keep their categorical colour; unlabeled wallets are
        // shaded by taint, turning the graph into a heat map of where the
        // victim's money actually went rather than a uniform blob of grey.
        'background-color': (ele: any) => {
          const type = ele.data('type')
          if (type !== 'unresolved' && type !== 'intermediate') {
            return NODE_COLORS[type] ?? '#64748b'
          }
          const t = ele.data('taint') ?? 0
          if (t >= 0.75) return '#a83e14'
          if (t >= 0.5) return '#cf7331'
          if (t >= 0.25) return '#e0a154'
          if (t > 0) return '#f0c98a'
          return '#94a3b8'
        },
        label: 'data(label)',
        color: labelColor,
        'font-size': 10,
        'font-family': 'Inter, sans-serif',
        'text-valign': 'bottom',
        'text-margin-y': 6,
        width: 28,
        height: 28,
        'border-width': 2,
        'border-color': nodeRing,
      },
    },
    {
      selector: 'node.cluster-parent',
      style: {
        'background-color': brandLine,
        'background-opacity': 0.06,
        'border-width': 1.5,
        'border-style': 'dashed',
        'border-color': brandLine,
        'border-opacity': 0.6,
        label: 'data(label)',
        color: edgeLabelColor,
        'font-size': 9,
        'text-valign': 'top',
        'text-halign': 'center',
        'text-margin-y': -4,
        padding: 14,
        'corner-radius': 6,
        shape: 'round-rectangle',
      },
    },
    {
      selector: 'node.cluster-parent.selected-cluster',
      style: {
        'border-width': 2.5,
        'border-color': '#f59e0b',
        'border-opacity': 0.9,
        'background-color': '#f59e0b',
        'background-opacity': 0.12,
      },
    },
    {
      selector: 'node.cluster-highlighted',
      style: {
        'border-width': 4.5,
        'border-color': '#f59e0b',
        'border-opacity': 1,
        width: 38,
        height: 38,
        'underlay-color': '#fbbf24',
        'underlay-padding': 10,
        'underlay-opacity': 0.5,
        'underlay-shape': 'ellipse',
        'font-weight': 'bold',
        'font-size': 11,
        'z-index': 999,
      },
    },
    {
      selector: 'edge.cluster-highlighted',
      style: {
        width: 4,
        'line-color': '#f59e0b',
        'target-arrow-color': '#f59e0b',
        'target-arrow-shape': 'triangle',
        'arrow-scale': 1.35,
        opacity: 1,
        'z-index': 999,
        color: '#d97706',
        'font-weight': 'bold',
        'font-size': 9.5,
      },
    },
    {
      selector: 'node.cluster-dimmed',
      style: {
        opacity: 0.2,
      },
    },
    {
      selector: 'edge.cluster-dimmed',
      style: {
        opacity: 0.1,
      },
    },
    {
      selector: 'node.target-verified',
      style: {
        'border-width': 5,
        'border-color': '#06b6d4',
        'border-opacity': 1,
        width: 44,
        height: 44,
        'underlay-color': '#22d3ee',
        'underlay-padding': 16,
        'underlay-opacity': 0.65,
        'underlay-shape': 'ellipse',
        'font-weight': 'bold',
        'font-size': 12,
        'z-index': 1000,
      },
    },
    {
      selector: 'node.type-highlighted',
      style: {
        'border-width': 4.5,
        'border-color': '#0284c7',
        'underlay-color': '#38bdf8',
        'underlay-padding': 8,
        'underlay-opacity': 0.45,
        'font-weight': 'bold',
        'z-index': 999,
      },
    },
    {
      selector: 'node.type-dimmed',
      style: {
        opacity: 0.18,
      },
    },
    {
      selector: 'edge.type-dimmed',
      style: {
        opacity: 0.08,
      },
    },
    {
      selector: 'node.declutter-dimmed',
      style: {
        opacity: 0.12,
      },
    },
    {
      selector: 'node.suspect-confirmed',
      style: {
        'border-width': 4,
        'border-color': '#b3261e',
        'border-style': 'double',
        'font-weight': 'bold',
      },
    },
    {
      selector: 'node.live-detected',
      style: {
        'underlay-color': '#f59e0b',
        'underlay-padding': 6,
        'underlay-opacity': 0.35,
        'underlay-shape': 'ellipse',
      },
    },
    {
      selector: 'node.live-new',
      style: {
        'underlay-padding': 12,
        'underlay-opacity': 0.55,
      },
    },
    {
      selector: 'node.live-new.live-pulse',
      style: {
        'underlay-padding': 18,
        'underlay-opacity': 0.2,
      },
    },
    {
      selector: 'node.on-path',
      style: {
        'border-width': 3.5,
        'border-color': onPathRing,
        width: 34,
        height: 34,
      },
    },
    {
      selector: 'node.selected-node',
      style: {
        'border-width': 4.5,
        'border-color': '#0284c7',
        'border-opacity': 1,
        width: 38,
        height: 38,
        'underlay-color': '#38bdf8',
        'underlay-padding': 10,
        'underlay-opacity': 0.45,
        'underlay-shape': 'ellipse',
        'font-weight': 'bold',
        'font-size': 11,
        'z-index': 999,
      },
    },
    {
      selector: 'edge.connected-to-selected',
      style: {
        'line-color': '#0284c7',
        'target-arrow-color': '#0284c7',
        width: 2.5,
        opacity: 0.95,
        'z-index': 998,
      },
    },
    {
      selector: 'edge.selected-edge',
      style: {
        width: 4.5,
        'line-color': '#0284c7',
        'target-arrow-color': '#0284c7',
        'target-arrow-shape': 'triangle',
        'arrow-scale': 1.35,
        opacity: 1,
        'z-index': 999,
        color: '#0284c7',
        'font-weight': 'bold',
        'font-size': 9.5,
      },
    },
    {
      selector: 'node.dimmed',
      style: {
        opacity: 0.25,
      },
    },
    {
      selector: 'edge',
      style: {
        width: (ele: any) => {
          const amount = ele.data('amount') ?? 0
          // Square root keeps a 1000x value difference from becoming a 1000x
          // stroke; the thinnest edge stays visible at 1px.
          return 1 + 4 * Math.sqrt(Math.min(1, amount / maxAmount))
        },
        'line-color': edgeLine,
        'target-arrow-color': edgeLine,
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        label: 'data(value)',
        'font-size': 8.5,
        color: edgeLabelColor,
        'text-background-color': surface,
        'text-background-opacity': 0.9,
        'text-background-padding': '2px',
      },
    },
    {
      selector: 'edge.on-path',
      style: {
        width: 3.5,
        'line-color': brandLine,
        'target-arrow-color': brandLine,
        'z-index': 10,
      },
    },
    {
      selector: 'edge.dimmed',
      style: {
        opacity: 0.15,
      },
    },
    {
      selector: 'edge.live-detected',
      style: {
        'line-color': '#f59e0b',
        'target-arrow-color': '#f59e0b',
        'line-style': 'dashed',
        'line-dash-pattern': [7, 4],
        color: '#b45309',
        'z-index': 20,
      },
    },
    {
      selector: 'edge.live-new',
      style: {
        width: 4,
        'line-style': 'solid',
        'font-weight': 'bold',
      },
    },
    {
      selector: 'edge.live-new.live-pulse',
      style: {
        'line-color': '#fbbf24',
        'target-arrow-color': '#fbbf24',
      },
    },
  ]

  // Graph control handlers
  const handleZoomIn = () => {
    if (cyRef.current) {
      cyRef.current.zoom({
        level: cyRef.current.zoom() * 1.3,
        renderedPosition: { x: cyRef.current.width() / 2, y: cyRef.current.height() / 2 },
      })
    }
  }

  const handleZoomOut = () => {
    if (cyRef.current) {
      cyRef.current.zoom({
        level: cyRef.current.zoom() * 0.75,
        renderedPosition: { x: cyRef.current.width() / 2, y: cyRef.current.height() / 2 },
      })
    }
  }

  const handleFit = () => {
    if (cyRef.current) {
      cyRef.current.fit(undefined, 40)
      if (cyRef.current.zoom() > 1.8) cyRef.current.zoom(1.8)
      cyRef.current.center()
    }
  }

  /**
   * Adaptive Hop Matrix Layout:
   * Dynamically groups nodes within a hop into 2-4 staggered sub-columns
   * when density exceeds 8 nodes. This avoids extreme 3000px vertical pillars,
   * balances widescreen aspect ratios, and prevents overlapping diagonal edge blobs.
   */
  const resolveLayout = (name: LayoutType) => {
    if (name !== 'hops') {
      return { name, directed: true, padding: 36, spacingFactor: 1.4 }
    }
    const ROW_HEIGHT = 68
    const SUB_COL_WIDTH = 125
    const MIN_HOP_GAP = 220

    const byHop = new Map<number, GraphNode[]>()
    for (const n of nodes) {
      const hop = n.hop ?? 0
      byHop.set(hop, [...(byHop.get(hop) ?? []), n])
    }

    const sortedHops = Array.from(byHop.keys()).sort((a, b) => a - b)
    const hopStartPositions: Record<number, number> = {}
    let currentX = 0

    for (const hop of sortedHops) {
      const group = byHop.get(hop) ?? []
      const numSubCols = Math.min(4, Math.max(1, Math.ceil(group.length / 8)))
      const hopWidth = (numSubCols - 1) * SUB_COL_WIDTH
      hopStartPositions[hop] = currentX
      currentX += hopWidth + MIN_HOP_GAP
    }

    const positions: Record<string, { x: number; y: number }> = {}
    for (const hop of sortedHops) {
      const group = byHop.get(hop) ?? []
      const numSubCols = Math.min(4, Math.max(1, Math.ceil(group.length / 8)))
      const numRows = Math.ceil(group.length / numSubCols)
      const startX = hopStartPositions[hop] ?? (hop * MIN_HOP_GAP)

      group.forEach((n, i) => {
        const subCol = i % numSubCols
        const subRow = Math.floor(i / numSubCols)
        positions[n.id] = {
          x: startX + subCol * SUB_COL_WIDTH,
          y: (subRow - (numRows - 1) / 2) * ROW_HEIGHT + (subCol % 2 === 1 ? 18 : 0),
        }
      })
    }
    return {
      name: 'preset',
      positions: (node: any) => positions[node.id()] ?? { x: 0, y: 0 },
      padding: 40,
      fit: true,
    }
  }

  const handleLayoutChange = (newLayout: LayoutType) => {
    setLayoutName(newLayout)
    if (cyRef.current) {
      const layout = cyRef.current.layout({
        ...resolveLayout(newLayout),
        animate: true,
        animationDuration: 400,
      } as any)
      layout.run()
    }
  }

  const handleFocusCluster = () => {
    if (!cyRef.current || !selectedCluster) return
    const cy = cyRef.current
    const addrs = new Set(selectedCluster.addresses)
    const clusterNodes = cy.nodes().filter((ele: any) => {
      return !ele.hasClass('cluster-parent') && addrs.has(ele.data('fullAddress'))
    })
    if (clusterNodes.length > 0) {
      cy.animate({
        fit: {
          eles: clusterNodes,
          padding: 70,
        },
        duration: 500,
        easing: 'ease-in-out',
      })
    }
  }

  const handleSelectNodeFromCluster = (node: GraphNode) => {
    setSelectedCluster(null)
    setIsClusterHighlighted(false)
    setVerifiedNodeAddress(null)
    if (onNodeClick) onNodeClick(node)
  }

  const handleLocateNode = (address: string) => {
    setVerifiedNodeAddress(address)
    if (!cyRef.current) return
    const cy = cyRef.current
    const targetNode = cy.nodes().filter((n: any) => n.data('fullAddress') === address)
    if (targetNode.length > 0) {
      cy.animate({
        center: { eles: targetNode },
        zoom: Math.max(cy.zoom(), 1.9),
        duration: 500,
        easing: 'ease-in-out',
      })
      toast.info(`Located ${address.slice(0, 8)}… on canvas`)
    } else {
      toast.warning('Address node is beyond current visible graph frontier')
    }
  }

  const handleSelectSearchedNode = (node: GraphNode) => {
    setSearchQuery('')
    setIsSearchOpen(false)
    setVerifiedNodeAddress(node.address)
    if (cyRef.current) {
      const cy = cyRef.current
      const targetEle = cy.nodes().filter((n: any) => n.data('fullAddress') === node.address)
      if (targetEle.length > 0) {
        cy.animate({
          center: { eles: targetEle },
          zoom: Math.max(cy.zoom(), 2.1),
          duration: 500,
          easing: 'ease-in-out',
        })
      }
    }
    if (onNodeClick) onNodeClick(node)
    if (onCloseEdge) onCloseEdge()
    setSelectedCluster(null)
    setIsClusterHighlighted(false)
    toast.success('Located wallet on canvas', {
      description: `${node.address.slice(0, 12)}… (Hop ${node.hop ?? 0})`,
    })
  }

  const handleExportPNG = () => {
    if (cyRef.current) {
      const png64 = cyRef.current.png({ full: true, scale: 2, bg: surface })
      const link = document.createElement('a')
      link.href = png64
      link.download = `forensic-graph-${Date.now()}.png`
      document.body.appendChild(link)
      link.click()
      link.remove()
      toast.success('Forensic graph exported as PNG')
    }
  }

  return (
    <div
      className={`relative overflow-hidden rounded-md border border-ink-100 bg-surface shadow-xs transition-all ${
        isFullscreen ? 'fixed inset-4 z-50 shadow-md ring-1 ring-ink-200' : 'h-full w-full'
      }`}
    >
      {/* Floating Node Search / Address Finder (Top-Left) */}
      <div className="absolute top-3 left-3 z-20 w-64 sm:w-84">
        <div className="relative flex items-center">
          <Search size={14} className="absolute left-2.5 text-ink-400 pointer-events-none" />
          <input
            ref={searchInputRef}
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value)
              setIsSearchOpen(true)
            }}
            onFocus={() => setIsSearchOpen(true)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && searchMatches.length > 0) {
                handleSelectSearchedNode(searchMatches[0])
              }
            }}
            placeholder="Find address or scammer node... (/)"
            className="w-full rounded-lg border border-ink-200/90 bg-surface/95 pl-8 pr-7 py-1.5 text-xs font-mono text-ink-800 placeholder:font-sans placeholder:text-ink-400 shadow-md backdrop-blur-md focus:border-brand-500 focus:outline-hidden focus:ring-1 focus:ring-brand-500"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => {
                setSearchQuery('')
                setIsSearchOpen(false)
              }}
              className="absolute right-2 text-ink-400 hover:text-ink-700 p-0.5"
              title="Clear search"
            >
              <X size={13} />
            </button>
          )}
        </div>

        {/* Live Search Results Dropdown */}
        {isSearchOpen && searchQuery.trim().length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 max-h-64 overflow-y-auto rounded-lg border border-ink-200 bg-surface shadow-xl z-30 p-1 divide-y divide-ink-100">
            {searchMatches.length > 0 ? (
              searchMatches.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleSelectSearchedNode(n)}
                  className="w-full text-left px-2.5 py-2 hover:bg-brand-50/70 rounded-md flex flex-col gap-0.5 transition-colors cursor-pointer"
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-mono text-xs font-semibold text-ink-900 truncate">
                      {n.address}
                    </span>
                    <span className="shrink-0 text-[10px] px-1.5 py-0.2 rounded bg-ink-100 font-bold uppercase text-ink-600">
                      Hop {n.hop ?? 0}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-ink-500">
                    <span className="capitalize font-medium text-brand-700">
                      {n.label_name || n.node_type}
                    </span>
                    {n.tainted_value !== undefined && (
                      <span>· Taint: {formatAmount(n.tainted_value)}</span>
                    )}
                  </div>
                </button>
              ))
            ) : (
              <div className="px-3 py-3 text-center text-xs text-ink-400 italic">
                No node matching "{searchQuery}" found on canvas
              </div>
            )}
          </div>
        )}
      </div>

      {/* Floating Graph Controls Toolbar */}
      <div className="absolute top-3 right-3 z-10 flex flex-wrap items-center gap-1.5 rounded-lg border border-ink-200/80 bg-surface/95 p-1.5 shadow-md">
        {/* Zoom Controls */}
        <button
          type="button"
          onClick={handleZoomIn}
          title="Zoom In"
          className="rounded p-1.5 text-ink-600 hover:bg-ink-100 hover:text-ink-900"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={handleZoomOut}
          title="Zoom Out"
          className="rounded p-1.5 text-ink-600 hover:bg-ink-100 hover:text-ink-900"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={handleFit}
          title="Fit to Center"
          className="rounded p-1.5 text-ink-600 hover:bg-ink-100 hover:text-ink-900"
        >
          <RefreshCw className="h-4 w-4" />
        </button>

        <div className="h-4 w-px bg-ink-200" />

        {/* Toggle Wheel Scroll Zoom (Off by default so page scrolling never gets trapped) */}
        <button
          type="button"
          onClick={() => {
            const next = !wheelZoomEnabled
            setWheelZoomEnabled(next)
            if (cyRef.current) {
              cyRef.current.userZoomingEnabled(next)
            }
            toast.info(next ? 'Mouse wheel zoom enabled on graph canvas' : 'Mouse wheel zoom disabled (smooth page scroll)')
          }}
          title={wheelZoomEnabled ? 'Disable Mouse Wheel Canvas Zoom' : 'Enable Mouse Wheel Canvas Zoom'}
          className={`flex items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-colors ${
            wheelZoomEnabled
              ? 'bg-brand-50 text-brand-600 font-semibold border border-brand-200'
              : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900'
          }`}
        >
          <MousePointer className="h-3.5 w-3.5" />
          <span>{wheelZoomEnabled ? 'Wheel Zoom: On' : 'Wheel Zoom: Off'}</span>
        </button>

        <div className="h-4 w-px bg-ink-200" />

        {/* Declutter Dust Button for large graphs */}
        <button
          type="button"
          onClick={() => {
            const next = !declutterDust
            setDeclutterDust(next)
            toast.info(next ? 'Declutter on: Dimming dust leaves' : 'Declutter off: Showing all transfers')
          }}
          title={declutterDust ? 'Show all transfers including dust' : 'Declutter: Dim dust & focus main money paths'}
          className={`flex items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-colors ${
            declutterDust
              ? 'bg-brand-50 text-brand-600 font-semibold border border-brand-200 shadow-2xs'
              : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900'
          }`}
        >
          <Sparkles className="h-3.5 w-3.5" />
          <span>{declutterDust ? 'Declutter: On' : 'Declutter: Off'}</span>
        </button>

        {/* Layout Switcher */}
        <select
          value={layoutName}
          onChange={(e) => handleLayoutChange(e.target.value as LayoutType)}
          className="rounded border-none bg-transparent px-2 py-1 text-xs font-medium text-ink-700 outline-hidden hover:bg-ink-100"
          title="Select Graph Layout"
        >
          <option value="hops">Hop columns (flow left to right)</option>
          <option value="breadthfirst">Breadth-First (Hierarchical)</option>
          <option value="concentric">Concentric (Hops)</option>
          <option value="circle">Circular</option>
          <option value="cose">Force-Directed (Organic)</option>
          <option value="grid">Grid</option>
        </select>

        <div className="h-4 w-px bg-ink-200" />

        {/* Focus Path Toggle */}
        <button
          type="button"
          onClick={() => setPathOnly(!pathOnly)}
          title={pathOnly ? 'Show Full Graph' : 'Highlight Critical Cashout Path'}
          className={`rounded p-1.5 transition-colors ${
            pathOnly
              ? 'bg-brand-50 text-brand-600'
              : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900'
          }`}
        >
          <Focus className="h-4 w-4" />
        </button>

        {/* Toggle Amounts on Edges */}
        <button
          type="button"
          onClick={() => setShowValues(!showValues)}
          title={showValues ? 'Hide Transfer Values' : 'Show Transfer Values'}
          className={`rounded p-1.5 transition-colors ${
            showValues
              ? 'bg-brand-50 text-brand-600'
              : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900'
          }`}
        >
          <Coins className="h-4 w-4" />
        </button>

        {/* Export Image */}
        <button
          type="button"
          onClick={handleExportPNG}
          title="Export Graph as PNG Image"
          className="rounded p-1.5 text-ink-600 hover:bg-ink-100 hover:text-ink-900"
        >
          <Camera className="h-4 w-4" />
        </button>

        {/* Fullscreen Toggle */}
        <button
          type="button"
          onClick={() => setIsFullscreen(!isFullscreen)}
          title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen View'}
          className="rounded p-1.5 text-ink-600 hover:bg-ink-100 hover:text-ink-900"
        >
          {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </button>
      </div>

      {/* Floating Status & Interaction Hint */}
      <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2 rounded-md bg-surface/90 px-2.5 py-1 text-[11px] text-ink-500 shadow-xs">
        <span className="flex h-2 w-2 rounded-full bg-brand-500 animate-pulse" />
        <span>{nodes.length} Wallets • {edges.length} Transfers</span>
        {edges.length === 0 && <span className="text-warning font-medium">(Single wallet / Target deposit address)</span>}
      </div>

      {/* Canvas - userZoomingEnabled is false by default so page scrolling works smoothly */}
      <CytoscapeComponent
        elements={CytoscapeComponent.normalizeElements(elements)}
        style={{ width: '100%', height: '100%' }}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        stylesheet={stylesheet as any}
        userZoomingEnabled={wheelZoomEnabled}
        layout={resolveLayout(layoutName) as any}
        cy={(cy: Core) => {
          cyRef.current = cy
          cy.userZoomingEnabled(wheelZoomEnabled)
          cy.removeAllListeners()
          cy.on('layoutstop', () => {
            cy.fit(undefined, 36)
            if (cy.zoom() > 1.8) cy.zoom(1.8)
            cy.center()
            if (selectedNode) {
              const ele = cy.getElementById(selectedNode.id)
              if (ele.length > 0) {
                ele.addClass('selected-node')
                ele.connectedEdges().addClass('connected-to-selected')
              }
            }
          })
          cy.on('tap', 'node', (evt) => {
            const id = evt.target.id() as string
            if (id.startsWith('cluster-') || evt.target.hasClass('cluster-parent')) {
              const cluster = clusterParents.clusterById.get(id)
              if (cluster) {
                setSelectedCluster(cluster)
                setIsClusterHighlighted(true) // auto-highlight transactions on selection
                if (onCloseNode) onCloseNode()
                if (onCloseEdge) onCloseEdge()
              }
              return
            }
            setSelectedCluster(null)
            setIsClusterHighlighted(false)
            const node = nodes.find((n) => n.id === id)
            if (node && onNodeClick) onNodeClick(node)
          })
          if (onEdgeClick) {
            cy.on('tap', 'edge', (evt) => {
              setSelectedCluster(null)
              setIsClusterHighlighted(false)
              const data = evt.target.data()
              const edge = edges.find(
                (e) =>
                  e.tx_hash === data.tx_hash &&
                  e.source === data.source &&
                  e.target === data.target
              ) || {
                source: data.source,
                target: data.target,
                tx_hash: data.tx_hash,
                value: data.amount ?? 0,
                hop: data.hop ?? 1,
                timestamp: data.timestamp,
                tainted_value: data.tainted_value,
              }
              onEdgeClick(edge)
            })
          }
          cy.on('tap', (evt) => {
            if (evt.target === cy) {
              setSelectedCluster(null)
              setIsClusterHighlighted(false)
              if (onCloseNode) onCloseNode()
              if (onCloseEdge) onCloseEdge()
            }
          })
        }}
      />

      {/* Floating Right-Side Node Inspector */}
      {selectedNode && (
        <NodeInspector node={selectedNode} onClose={onCloseNode ?? (() => {})} />
      )}

      {/* Floating Right-Side Edge / Transfer Inspector */}
      {selectedEdge && (
        <EdgeInspector
          edge={selectedEdge}
          chain={nodes[0]?.chain || 'bitcoin'}
          onClose={onCloseEdge ?? (() => {})}
        />
      )}

      {/* Floating Right-Side Cluster Inspector */}
      {selectedCluster && (
        <ClusterInspector
          cluster={selectedCluster}
          nodes={nodes}
          edges={edges}
          chain={nodes[0]?.chain || 'bitcoin'}
          isHighlighted={isClusterHighlighted}
          verifiedAddress={verifiedNodeAddress}
          onToggleHighlight={() => setIsClusterHighlighted((prev) => !prev)}
          onFocusCluster={handleFocusCluster}
          onSelectNode={handleSelectNodeFromCluster}
          onLocateNode={handleLocateNode}
          onClose={() => {
            setSelectedCluster(null)
            setIsClusterHighlighted(false)
            setVerifiedNodeAddress(null)
          }}
        />
      )}
    </div>
  )
}
