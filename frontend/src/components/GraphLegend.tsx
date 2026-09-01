const ITEMS = [
  { type: 'reported', label: 'Reported wallet', color: '#3b6bf0' },
  { type: 'exchange', label: 'Exchange / VASP', color: '#16a34a' },
  { type: 'funder', label: 'Seed Funder (Gas)', color: '#9333ea' },
  { type: 'dex', label: 'DEX Swap', color: '#ec4899' },
  { type: 'mixer', label: 'Mixer', color: '#dc2626' },
  { type: 'bridge', label: 'Bridge', color: '#a855f7' },
  { type: 'unresolved', label: 'Unresolved', color: '#94a3b8' },
]

export function GraphLegend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-ink-500">
      {ITEMS.map((item) => (
        <div key={item.type} className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: item.color }} />
          {item.label}
        </div>
      ))}
    </div>
  )
}
