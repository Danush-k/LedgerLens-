/**
 * The LedgerLens mark.
 *
 * Concentric rings built from discrete segments, converging on a solid
 * focal point. The segments are ledger entries - discrete, sequential,
 * immutable - and the concentric arrangement resolves them into an
 * aperture. That is the product in one figure: a ledger, read as a lens.
 *
 * Geometry note: every ring declares pathLength="100", which normalises its
 * circumference so one dash pattern produces the same segment count on any
 * radius. Without it each ring needs its own 2πr arithmetic and the
 * segments drift out of rhythm as the radii change.
 *
 * Each dash+gap must divide 100 exactly or the pattern fails to close and
 * leaves one short segment - a seam, and in a logo that reads as a mistake.
 * The three rings are 10, 8 and 6 segments: 5.6+4.4, 7.2+5.3, 11+5.667.
 *
 * The inner rings carry a half-segment dashoffset. Without it the segments
 * line up across all three radii and the mark resolves into radial spokes -
 * busier, and it stops reading as concentric bands.
 */

interface MarkProps {
  size?: number
  /** Rotates the rings continuously. Used for the loading state. */
  animated?: boolean
  className?: string
  title?: string
}

export function LogoMark({ size = 28, animated = false, className = '', title }: MarkProps) {
  return (
    <svg
      viewBox="0 0 48 48"
      width={size}
      height={size}
      className={className}
      role={title ? 'img' : 'presentation'}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      {title && <title>{title}</title>}
      <g fill="none" strokeLinecap="butt">
        {/* Outer ring - the widest, sparsest band of entries. */}
        <circle
          cx="24" cy="24" r="20.5"
          pathLength="100"
          strokeDasharray="5.6 4.4"
          strokeWidth="3"
          stroke="currentColor"
          opacity="0.55"
          className={animated ? 'll-ring-outer' : undefined}
          style={{ transformOrigin: '24px 24px' }}
        />
        {/* Middle ring - denser, counter-rotating. */}
        <circle
          cx="24" cy="24" r="14.5"
          pathLength="100"
          strokeDasharray="7.2 5.3"
          strokeDashoffset="6.25"
          strokeWidth="3.2"
          stroke="currentColor"
          opacity="0.8"
          className={animated ? 'll-ring-middle' : undefined}
          style={{ transformOrigin: '24px 24px' }}
        />
        {/* Inner ring - fewest, largest segments, closest to the focus. */}
        <circle
          cx="24" cy="24" r="9"
          pathLength="100"
          strokeDasharray="11 5.667"
          strokeDashoffset="8.33"
          strokeWidth="3.4"
          stroke="currentColor"
          className={animated ? 'll-ring-inner' : undefined}
          style={{ transformOrigin: '24px 24px' }}
        />
      </g>
      {/* The focal point. Solid, because it is the one thing resolved. */}
      <circle cx="24" cy="24" r="3.2" fill="currentColor" />
    </svg>
  )
}

/** Mark plus wordmark, for the sidebar and the sign-in screen. */
export function Logo({ size = 28, showSub = true, className = '' }: {
  size?: number
  showSub?: boolean
  className?: string
}) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <LogoMark size={size} className="text-brand-500" title="LedgerLens" />
      <div className="leading-none">
        <p className="text-[15px] font-semibold tracking-[-0.01em] text-current">
          Ledger<span className="font-normal">Lens</span>
        </p>
        {showSub && (
          <p className="mt-1 text-[10px] uppercase tracking-[0.14em] text-chrome-text-muted">
            Fraud attribution
          </p>
        )}
      </div>
    </div>
  )
}

/**
 * Loading state, using the mark itself rather than a generic spinner.
 * The rings turn at different rates and in opposite directions, so the
 * figure reads as resolving rather than merely spinning.
 */
export function LoadingRing({ size = 40, label }: { size?: number; label?: string }) {
  return (
    <div className="flex flex-col items-center gap-3" role="status" aria-live="polite">
      <LogoMark size={size} animated className="text-brand-500" />
      {label && <p className="text-xs text-ink-500">{label}</p>}
      <span className="sr-only">{label ?? 'Loading'}</span>
    </div>
  )
}
