import type { Core } from 'cytoscape'
import { useMemo } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'
import { useTheme } from '../theme/ThemeContext'
import type { GraphEdge, GraphNode } from '../types'
import { formatAmount } from '../utils/format'

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
}

export function GraphView({ nodes, edges, highlightPath = [], onNodeClick }: Props) {
  const { resolved } = useTheme()
  const dark = resolved === 'dark'

  const elements = useMemo(() => {
    const pathSet = new Set(highlightPath)
    const nodeEls = nodes.map((n) => ({
      data: {
        id: n.id,
        label: n.label_name ?? `${n.address.slice(0, 6)}…${n.address.slice(-4)}`,
        type: n.node_type,
      },
      classes: pathSet.has(n.id) ? 'on-path' : '',
    }))
    const edgeEls = edges.map((e, i) => ({
      data: {
        id: `${e.tx_hash}-${i}`,
        source: e.source,
        target: e.target,
        value: formatAmount(e.value),
      },
      classes: pathSet.has(e.source) && pathSet.has(e.target) ? 'on-path' : '',
    }))
    return [...nodeEls, ...edgeEls]
  }, [nodes, edges, highlightPath])

  // Cytoscape renders to a <canvas>, so it can't read our CSS custom
  // properties - these mirror the light/dark token values from index.css
  // by hand and are recomputed whenever the resolved theme changes.
  const surface = dark ? '#161b22' : '#ffffff'
  const labelColor = dark ? '#e6edf3' : '#1f2328'
  const nodeRing = dark ? '#161b22' : '#ffffff'
  const onPathRing = dark ? '#f0f3f6' : '#0b1120'
  const edgeLine = dark ? '#3d444d' : '#cbd5e1'
  const edgeLabelColor = dark ? '#9198a1' : '#64748b'
  const brandLine = dark ? '#4493f8' : '#0969da'

  // cytoscape's own Stylesheet union type isn't reliably importable across
  // versions of @types/cytoscape, so this is typed loosely and validated
  // instead by cytoscape itself at runtime (it throws on a bad stylesheet).
  const stylesheet = [
    {
      selector: 'node',
      style: {
        'background-color': (ele: any) => NODE_COLORS[ele.data('type')] ?? '#64748b',
        label: 'data(label)',
        color: labelColor,
        'font-size': 10,
        'font-family': 'Inter, sans-serif',
        'text-valign': 'bottom',
        'text-margin-y': 6,
        width: 26,
        height: 26,
        'border-width': 2,
        'border-color': nodeRing,
      },
    },
    {
      selector: 'node.on-path',
      style: {
        'border-width': 3,
        'border-color': onPathRing,
        width: 32,
        height: 32,
      },
    },
    {
      selector: 'edge',
      style: {
        width: 1.5,
        'line-color': edgeLine,
        'target-arrow-color': edgeLine,
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        label: 'data(value)',
        'font-size': 8,
        color: edgeLabelColor,
        'text-background-color': surface,
        'text-background-opacity': 1,
      },
    },
    {
      selector: 'edge.on-path',
      style: {
        width: 3,
        'line-color': brandLine,
        'target-arrow-color': brandLine,
      },
    },
  ]

  return (
    <div className="h-full w-full rounded-lg border border-ink-100 bg-surface">
      <CytoscapeComponent
        elements={CytoscapeComponent.normalizeElements(elements)}
        style={{ width: '100%', height: '100%' }}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        stylesheet={stylesheet as any}
        layout={{ name: 'breadthfirst', directed: true, padding: 24, spacingFactor: 1.4 }}
        cy={(cy: Core) => {
          cy.removeAllListeners()
          cy.on('layoutstop', () => {
            cy.fit(undefined, 30)
            // A sparse graph (1-2 nodes) would otherwise fit-to-fill the
            // canvas and render one giant circle - cap the zoom instead.
            if (cy.zoom() > 1.8) cy.zoom(1.8)
            cy.center()
          })
          if (onNodeClick) {
            cy.on('tap', 'node', (evt) => {
              const id = evt.target.id() as string
              const node = nodes.find((n) => n.id === id)
              if (node) onNodeClick(node)
            })
          }
        }}
      />
    </div>
  )
}
