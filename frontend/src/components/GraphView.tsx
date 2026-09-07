import type { Core } from 'cytoscape'
import {
  Camera,
  Coins,
  Focus,
  Maximize2,
  Minimize2,
  MousePointer,
  RefreshCw,
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
  selectedNode?: GraphNode | null
  onCloseNode?: () => void
  selectedEdge?: GraphEdge | null
  onEdgeClick?: (edge: GraphEdge) => void
  onCloseEdge?: () => void
}

type LayoutType = 'hops' | 'breadthfirst' | 'concentric' | 'circle' | 'grid' | 'cose'

export function GraphView({
  nodes,
  edges,
  highlightPath = [],
  onNodeClick,
  clusters = [],
  selectedNode = null,
  onCloseNode,
  selectedEdge = null,
  onEdgeClick,
  onCloseEdge,
}: Props) {
  const cyRef = useRef<Core | null>(null)

  // Money flows left to right by hop. A reader should never have to work
  // out which direction the funds moved.
  const [layoutName, setLayoutName] = useState<LayoutType>('hops')
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [pathOnly, setPathOnly] = useState(false)
  const [showValues, setShowValues] = useState(true)
  const [wheelZoomEnabled, setWheelZoomEnabled] = useState(false)

  // Dynamically toggle prominent highlight classes on the selected node/edge
  useEffect(() => {
    if (!cyRef.current) return
    const cy = cyRef.current
    cy.batch(() => {
      cy.nodes().removeClass('selected-node')
      cy.edges().removeClass('connected-to-selected selected-edge')
      if (selectedNode) {
        const ele = cy.getElementById(selectedNode.id)
        if (ele.length > 0) {
          ele.addClass('selected-node')
          ele.connectedEdges().addClass('connected-to-selected')
        }
      }
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
    })
  }, [selectedNode, selectedEdge])

  /**
   * Addresses proven to share a key holder are drawn inside one box.
   *
   * Only common-input-ownership is grouped. Shared-funder is a much weaker
   * signal - an exchange paying out to a thousand customers "shares a
   * funder" with all of them - and drawing a box around that would assert
   * on the canvas exactly the thing the backend refuses to merge.
   *
   * Cytoscape allows a node one parent, so an address appearing in several
   * clusters is placed in the first, and the panel below the graph remains
   * the complete account.
   */
  const clusterParents = useMemo(() => {
    const parentOf = new Map<string, string>()
    const parents: { id: string; label: string }[] = []

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
        } else {
          cluster.addresses.forEach((address) => {
            const node = nodes.find((n) => n.address === address)
            if (node && parentOf.get(node.id) === parentId) parentOf.delete(node.id)
          })
        }
      })

    return { parentOf, parents }
  }, [clusters, nodes])

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
  }, [nodes, edges, highlightPath, pathOnly, showValues, clusterParents, selectedNode, selectedEdge])

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
   * Cytoscape has no hop-column layout, so 'hops' is resolved here into a
   * preset with computed positions: x by hop distance, y stacked within the
   * hop. Money then always reads left to right, which no force-directed
   * layout guarantees - and on a 70-node graph that difference is the
   * difference between a diagram and a hairball.
   */
  const resolveLayout = (name: LayoutType) => {
    if (name !== 'hops') {
      return { name, directed: true, padding: 36, spacingFactor: 1.4 }
    }
    const COLUMN = 190
    const ROW = 74
    const byHop = new Map<number, GraphNode[]>()
    for (const n of nodes) {
      const hop = n.hop ?? 0
      byHop.set(hop, [...(byHop.get(hop) ?? []), n])
    }
    const positions: Record<string, { x: number; y: number }> = {}
    for (const [hop, group] of byHop) {
      group.forEach((n, i) => {
        positions[n.id] = {
          x: hop * COLUMN,
          // Centre each column vertically so the trunk of the flow stays
          // near the middle instead of hanging off the top edge.
          y: (i - (group.length - 1) / 2) * ROW,
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
          if (onNodeClick) {
            cy.on('tap', 'node', (evt) => {
              const id = evt.target.id() as string
              const node = nodes.find((n) => n.id === id)
              if (node) onNodeClick(node)
            })
          }
          if (onEdgeClick) {
            cy.on('tap', 'edge', (evt) => {
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
    </div>
  )
}
