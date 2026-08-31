import type { Core } from 'cytoscape'
import { useMemo } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'
import type { GraphEdge, GraphNode } from '../types'

const NODE_COLORS: Record<string, string> = {
  reported: '#3b6bf0',
  exchange: '#16a34a',
  mixer: '#dc2626',
  bridge: '#9333ea',
  unresolved: '#94a3b8',
  intermediate: '#64748b',
}

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  highlightPath?: string[] // node ids on the path to the nearest exchange
}

export function GraphView({ nodes, edges, highlightPath = [] }: Props) {
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
        value: e.value.toFixed(4),
      },
      classes: pathSet.has(e.source) && pathSet.has(e.target) ? 'on-path' : '',
    }))
    return [...nodeEls, ...edgeEls]
  }, [nodes, edges, highlightPath])

  // cytoscape's own Stylesheet union type isn't reliably importable across
  // versions of @types/cytoscape, so this is typed loosely and validated
  // instead by cytoscape itself at runtime (it throws on a bad stylesheet).
  const stylesheet = [
    {
      selector: 'node',
      style: {
        'background-color': (ele: any) => NODE_COLORS[ele.data('type')] ?? '#64748b',
        label: 'data(label)',
        color: '#1e293b',
        'font-size': 10,
        'font-family': 'Inter, sans-serif',
        'text-valign': 'bottom',
        'text-margin-y': 6,
        width: 26,
        height: 26,
        'border-width': 2,
        'border-color': '#ffffff',
      },
    },
    {
      selector: 'node.on-path',
      style: {
        'border-width': 3,
        'border-color': '#0b1120',
        width: 32,
        height: 32,
      },
    },
    {
      selector: 'edge',
      style: {
        width: 1.5,
        'line-color': '#cbd5e1',
        'target-arrow-color': '#cbd5e1',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        label: 'data(value)',
        'font-size': 8,
        color: '#64748b',
        'text-background-color': '#f8fafc',
        'text-background-opacity': 1,
      },
    },
    {
      selector: 'edge.on-path',
      style: {
        width: 3,
        'line-color': '#3b6bf0',
        'target-arrow-color': '#3b6bf0',
      },
    },
  ]

  return (
    <div className="h-full w-full rounded-lg border border-ink-100 bg-white">
      <CytoscapeComponent
        elements={CytoscapeComponent.normalizeElements(elements)}
        style={{ width: '100%', height: '100%' }}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        stylesheet={stylesheet as any}
        layout={{ name: 'breadthfirst', directed: true, padding: 24, spacingFactor: 1.4 }}
        cy={(cy: Core) => {
          cy.on('layoutstop', () => cy.fit(undefined, 30))
        }}
      />
    </div>
  )
}
