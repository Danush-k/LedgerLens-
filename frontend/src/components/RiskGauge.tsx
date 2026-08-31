function riskColor(score: number) {
  if (score >= 70) return 'var(--color-risk-high)'
  if (score >= 35) return 'var(--color-risk-medium)'
  return 'var(--color-risk-low)'
}

function riskLabel(score: number) {
  if (score >= 70) return 'High risk'
  if (score >= 35) return 'Medium risk'
  return 'Low risk'
}

export function RiskGauge({ score, size = 128 }: { score: number; size?: number }) {
  const radius = (size - 14) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - Math.min(100, Math.max(0, score)) / 100)
  const color = riskColor(score)

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="var(--color-ink-100)"
            strokeWidth={10}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={10}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 600ms ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-ink-900">{Math.round(score)}</span>
          <span className="text-[11px] text-ink-500">/ 100</span>
        </div>
      </div>
      <span className="text-sm font-semibold" style={{ color }}>
        {riskLabel(score)}
      </span>
    </div>
  )
}
