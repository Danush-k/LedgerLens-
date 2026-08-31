const CHAIN_META: Record<string, { label: string; className: string }> = {
  ethereum: { label: 'Ethereum', className: 'bg-indigo-50 text-indigo-700' },
  bsc: { label: 'BSC', className: 'bg-amber-50 text-amber-700' },
  polygon: { label: 'Polygon', className: 'bg-purple-50 text-purple-700' },
  bitcoin: { label: 'Bitcoin', className: 'bg-orange-50 text-orange-700' },
}

export function ChainBadge({ chain }: { chain: string }) {
  const meta = CHAIN_META[chain] ?? { label: chain, className: 'bg-ink-100 text-ink-700' }
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ${meta.className}`}>
      {meta.label}
    </span>
  )
}
