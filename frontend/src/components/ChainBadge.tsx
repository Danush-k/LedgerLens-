const CHAIN_META: Record<string, { label: string; className: string }> = {
  ethereum: { label: 'Ethereum', className: 'bg-ink-100 text-ink-700' },
  bsc: { label: 'BSC', className: 'bg-warning-soft text-warning' },
  polygon: { label: 'Polygon', className: 'bg-ink-100 text-ink-700' },
  bitcoin: { label: 'Bitcoin', className: 'bg-orange-500/10 text-orange-600' },
}

export function ChainBadge({ chain }: { chain: string }) {
  const meta = CHAIN_META[chain] ?? { label: chain, className: 'bg-ink-500/10 text-ink-600' }
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ${meta.className}`}>
      {meta.label}
    </span>
  )
}
