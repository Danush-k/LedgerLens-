/**
 * Chain identity.
 *
 * Each network is drawn as its own mark in its own brand colour. This is the
 * one place non-semantic colour earns its keep: an investigator recognises
 * Bitcoin orange faster than they read the word "bitcoin", and chain is a
 * fact about the address rather than a judgement about it, so it never
 * competes with the red/amber/green that carry severity.
 *
 * The marks are the real network logos rather than a letter on a disc. A
 * letter has to be read; a logo is recognised, which is the whole point of
 * an icon at 16px in a dense table. They are drawn as paths rather than
 * loaded as images so they inherit size cleanly, need no network request,
 * and stay crisp at any zoom.
 *
 * Logos are used nominatively - to identify the network each address is on.
 */

interface ChainDef {
  label: string
  color: string
  /** Drawn white-on-brand inside a 24x24 box. */
  path: (props: { className?: string }) => React.ReactElement
}

/** Bitcoin's B with its two vertical strokes, as on the official mark. */
const BitcoinGlyph = () => (
  <path
    fill="currentColor"
    d="M17.06 10.43c.24-1.6-.98-2.46-2.64-3.03l.54-2.16-1.32-.33-.52 2.1c-.35-.09-.7-.17-1.06-.25l.53-2.11-1.32-.33-.54 2.16c-.29-.07-.57-.13-.85-.2l-1.82-.45-.35 1.41s.98.22.96.24c.53.13.63.49.61.77l-.62 2.46.14.04-.14-.03-.86 3.45c-.07.16-.23.41-.61.31.01.02-.96-.24-.96-.24l-.66 1.51 1.72.43c.32.08.63.16.94.24l-.55 2.19 1.32.33.54-2.16c.36.1.71.19 1.05.27l-.54 2.15 1.32.33.55-2.18c2.25.43 3.94.25 4.66-1.78.58-1.64-.03-2.58-1.21-3.2.86-.2 1.51-.76 1.68-1.93Zm-3.01 4.22c-.41 1.64-3.18.75-4.08.53l.72-2.9c.9.22 3.79.67 3.36 2.37Zm.41-4.24c-.37 1.49-2.68.73-3.43.55l.65-2.62c.75.19 3.17.53 2.78 2.07Z"
  />
)

/** Ethereum's octahedron, faceted with opacity as in the original. */
const EthereumGlyph = () => (
  <g fill="currentColor">
    <path d="M12 2.5 5.9 12.6 12 9.85Z" fillOpacity="0.6" />
    <path d="M12 2.5 18.1 12.6 12 9.85Z" fillOpacity="0.85" />
    <path d="M12 16.05 5.9 13.28 12 21.5Z" fillOpacity="0.6" />
    <path d="M12 21.5 18.1 13.28 12 16.05Z" fillOpacity="0.85" />
    <path d="M5.9 12.6 12 9.85v5.4Z" fillOpacity="0.35" />
    <path d="M18.1 12.6 12 9.85v5.4Z" fillOpacity="0.5" />
  </g>
)

/** BNB Chain: a diamond of four diamonds around a centre. */
const BnbGlyph = () => (
  <g fill="currentColor">
    <path d="m12 3.6 2.28 2.34L9.6 10.62 7.32 8.28Z" />
    <path d="M12 3.6 15.72 7.32 12 11.04 8.28 7.32Z" />
    <path d="M6.12 9.48 8.4 11.82 6.12 14.16 3.84 11.82Z" />
    <path d="M17.88 9.48 20.16 11.82 17.88 14.16 15.6 11.82Z" />
    <path d="M12 12.96 15.72 16.68 12 20.4 8.28 16.68Z" />
    <path d="M12 9.48 14.34 11.82 12 14.16 9.66 11.82Z" />
  </g>
)

/** Polygon's linked hexagon mark. */
const PolygonGlyph = () => (
  <path
    fill="currentColor"
    d="M16.4 9.02a1.1 1.1 0 0 0-1.04 0l-2.38 1.4-1.62.92-2.37 1.4a1.1 1.1 0 0 1-1.04 0l-1.88-1.1a1.05 1.05 0 0 1-.52-.9V8.58c0-.36.18-.7.52-.9l1.85-1.07a1.1 1.1 0 0 1 1.04 0l1.85 1.08c.32.19.52.53.52.9v1.4l1.62-.95v-1.4a1.05 1.05 0 0 0-.52-.9l-3.44-2a1.1 1.1 0 0 0-1.04 0l-3.5 2a1.05 1.05 0 0 0-.52.9v4.03c0 .36.19.7.52.9l3.5 2.01a1.1 1.1 0 0 0 1.04 0l2.37-1.37 1.62-.95 2.38-1.37a1.1 1.1 0 0 1 1.04 0l1.85 1.07c.32.19.52.53.52.9v2.15c0 .36-.19.7-.52.9l-1.85 1.08a1.1 1.1 0 0 1-1.04 0l-1.85-1.05a1.05 1.05 0 0 1-.52-.9v-1.4l-1.62.95v1.4c0 .36.19.7.52.9l3.5 2.01a1.1 1.1 0 0 0 1.04 0l3.5-2.01c.32-.19.52-.53.52-.9v-4.04a1.05 1.05 0 0 0-.52-.9l-3.53-2.02Z"
  />
)

/** Tron's angular mark. */
const TronGlyph = () => (
  <path
    fill="currentColor"
    d="M18.9 7.35 5.4 4.86l7.1 15.9 8.1-11.06-1.7-2.35Zm-.55 1.28.98 1.36-3.6.65 2.62-2.01Zm-4.06 1.62-4.9-4.1 8.06 1.49-3.16 2.61Zm-.6 1.15-.5 6.35-4.05-9.07 4.55 2.72Zm1.16.34 4.02-.73-5.05 6.9.51-6.17-.02-.01Z"
  />
)

const CHAINS: Record<string, ChainDef> = {
  bitcoin: { label: 'Bitcoin', color: '#f7931a', path: BitcoinGlyph },
  ethereum: { label: 'Ethereum', color: '#627eea', path: EthereumGlyph },
  bsc: { label: 'BNB Chain', color: '#f0b90b', path: BnbGlyph },
  polygon: { label: 'Polygon', color: '#8247e5', path: PolygonGlyph },
  tron: { label: 'Tron', color: '#eb0029', path: TronGlyph },
}

const FALLBACK: ChainDef = {
  label: 'Unknown chain',
  color: '#8593a5',
  path: () => (
    <text
      x="12" y="16.5" textAnchor="middle"
      fontSize="12" fontWeight="600" fill="currentColor"
    >
      ?
    </text>
  ),
}

export function chainMeta(chain: string) {
  const def = CHAINS[chain] ?? { ...FALLBACK, label: chain || FALLBACK.label }
  return { label: def.label, color: def.color }
}

/** The network's logo on its brand-coloured disc. */
export function ChainMark({ chain, size = 18 }: { chain: string; size?: number }) {
  const def = CHAINS[chain] ?? { ...FALLBACK, label: chain || FALLBACK.label }
  const Glyph = def.path

  return (
    <span
      title={def.label}
      aria-label={def.label}
      role="img"
      className="inline-flex shrink-0 items-center justify-center rounded-full"
      style={{ background: def.color, width: size, height: size }}
    >
      <svg
        viewBox="0 0 24 24"
        width={size}
        height={size}
        className="text-white"
        aria-hidden="true"
      >
        <Glyph />
      </svg>
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
