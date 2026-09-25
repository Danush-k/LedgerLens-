import type { GraphNode } from '../types'

interface Props {
  nodes?: GraphNode[]
  activeType?: string | null
  onToggleType?: (type: string) => void
}

const ITEMS = [
  { type: 'reported', label: 'Reported wallet', color: '#3b6bf0' },
  { type: 'exchange', label: 'Exchange / VASP', color: '#16a34a' },
  { type: 'funder', label: 'Seed Funder (Gas)', color: '#9333ea' },
  { type: 'dex', label: 'DEX Swap', color: '#ec4899' },
  { type: 'mixer', label: 'Mixer', color: '#dc2626' },
  { type: 'bridge', label: 'Bridge', color: '#a855f7' },
  { type: 'unresolved', label: 'Unresolved', color: '#94a3b8' },
]

export function GraphLegend({ nodes = [], activeType = null, onToggleType }: Props) {
  // Count nodes by type
  const counts = nodes.reduce((acc, n) => {
    acc[n.node_type] = (acc[n.node_type] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 text-xs text-ink-600">
      <span className="text-[11px] font-semibold text-ink-400 uppercase tracking-wider mr-1">
        Legend & Filter:
      </span>

      {ITEMS.map((item) => {
        const count = counts[item.type] ?? 0
        const isActive = activeType === item.type
        const isDimmed = activeType !== null && !isActive

        return (
          <button
            key={item.type}
            type="button"
            onClick={() => onToggleType?.(item.type)}
            disabled={!onToggleType}
            className={`group inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-all ${
              isActive
                ? 'bg-surface shadow-xs ring-2 ring-brand-500 font-semibold text-ink-900 scale-105'
                : isDimmed
                ? 'opacity-40 hover:opacity-80 bg-surface/40 hover:bg-surface'
                : 'bg-surface/80 hover:bg-surface hover:shadow-2xs text-ink-700'
            } ${onToggleType ? 'cursor-pointer' : 'cursor-default'}`}
            title={
              onToggleType
                ? isActive
                  ? `Click to clear ${item.label} filter`
                  : `Click to highlight only ${item.label} nodes on graph`
                : undefined
            }
          >
            <span
              className={`h-2.5 w-2.5 rounded-full transition-transform ${
                isActive ? 'scale-125 ring-2 ring-brand-400/40' : ''
              }`}
              style={{ background: item.color }}
            />
            <span>{item.label}</span>
            {nodes.length > 0 && count > 0 && (
              <span
                className={`ml-0.5 rounded-full px-1.5 py-0.2 text-[10px] font-mono ${
                  isActive
                    ? 'bg-brand-100 text-brand-800 font-bold'
                    : 'bg-ink-100 text-ink-600'
                }`}
              >
                {count}
              </span>
            )}
          </button>
        )
      })}

      {activeType && onToggleType && (
        <button
          type="button"
          onClick={() => onToggleType(activeType)}
          className="ml-1 rounded-md px-2 py-0.5 text-[11px] font-semibold text-brand-600 hover:bg-brand-50 hover:text-brand-700 transition-colors"
          title="Reset graph filter to show all nodes"
        >
          Reset filter
        </button>
      )}
    </div>
  )
}
