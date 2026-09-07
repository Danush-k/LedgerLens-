interface BarItem {
  label: string
  value: number
  /** Optional. A single-measure chart needs no per-category colour, so the
   *  caller is not asked to invent one; pass a colour only when the hue
   *  itself carries meaning (risk bands, for instance). */
  color?: string
}

// One measure, one hue. Categorical colour would imply the categories differ
// in kind, which in these charts they do not.
const DEFAULT_BAR = 'var(--color-brand-500)'

/** A small horizontal bar chart - one measure, direct-labeled, no axis
 * needed since there are only ever a handful of categories here. */
export function HorizontalBars({ items }: { items: BarItem[] }) {
  const max = Math.max(1, ...items.map((i) => i.value))

  if (items.every((i) => i.value === 0)) {
    return <p className="py-6 text-center text-sm text-ink-400">No data yet.</p>
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-3">
          <span className="w-28 shrink-0 text-xs font-medium text-ink-600">{item.label}</span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink-100">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${(item.value / max) * 100}%`, background: item.color ?? DEFAULT_BAR }}
            />
          </div>
          <span className="w-8 shrink-0 text-right text-xs font-semibold tabular-nums text-ink-800">
            {item.value}
          </span>
        </div>
      ))}
    </div>
  )
}
