/**
 * Chain identity.
 *
 * Each network is drawn in its own brand colour with its own mark. This is
 * the one place non-semantic colour earns its keep: an investigator
 * recognises Bitcoin orange faster than they read the word "bitcoin", and
 * chain is a fact about the address rather than a judgement about it, so it
 * never competes with the red/amber/green that carry severity.
 */

const CHAINS: Record<string, { label: string; color: string; symbol: string }> = {
  bitcoin: { label: 'Bitcoin', color: '#f7931a', symbol: '₿' },
  ethereum: { label: 'Ethereum', color: '#627eea', symbol: 'Ξ' },
  bsc: { label: 'BNB Chain', color: '#f0b90b', symbol: 'B' },
  polygon: { label: 'Polygon', color: '#8247e5', symbol: 'P' },
}

export function chainMeta(chain: string) {
  return CHAINS[chain] ?? { label: chain, color: '#8593a5', symbol: '?' }
}

/** The coin glyph on its brand-coloured disc. */
export function ChainMark({ chain, size = 18 }: { chain: string; size?: number }) {
  const { label, color, symbol } = chainMeta(chain)
  return (
    <span
      title={label}
      aria-label={label}
      className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
      style={{
        background: color,
        width: size,
        height: size,
        fontSize: size * 0.58,
        lineHeight: 1,
      }}
    >
      {symbol}
    </span>
  )
}

/** Mark plus name, for table cells and headers. */
export function ChainBadge({ chain, size = 16 }: { chain: string; size?: number }) {
  const { label } = chainMeta(chain)
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <ChainMark chain={chain} size={size} />
      <span className="text-[13px] text-ink-700">{label}</span>
    </span>
  )
}

/**
 * A chain selector styled as a real form control rather than a row of
 * coloured pills - the brand colour identifies the option, the border
 * carries focus state.
 */
export function ChainSelect({ value, onChange, chains, id }: {
  value: string
  onChange: (chain: string) => void
  chains: string[]
  id?: string
}) {
  const { color } = chainMeta(value)
  return (
    <div className="relative">
      <span
        className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2"
        aria-hidden="true"
      >
        <ChainMark chain={value} size={18} />
      </span>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full cursor-pointer appearance-none rounded border bg-surface py-2 pl-10 pr-9 text-[13px] font-medium text-ink-900 outline-none transition-colors"
        style={{ borderColor: color }}
      >
        {chains.map((c) => (
          <option key={c} value={c}>{chainMeta(c).label}</option>
        ))}
      </select>
      <svg
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-400"
        width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"
      >
        <path d="M2.5 4.5L6 8l3.5-3.5" stroke="currentColor" strokeWidth="1.5"
              strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  )
}
