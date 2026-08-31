interface Props {
  label: string
  value: string
  hint?: string
  icon: React.ReactNode
}

export function StatTile({ label, value, hint, icon }: Props) {
  return (
    <div className="rounded-xl border border-ink-100 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-500">{label}</span>
        <span className="text-ink-300">{icon}</span>
      </div>
      <p className="mt-2 text-2xl font-bold text-ink-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-ink-500">{hint}</p>}
    </div>
  )
}
