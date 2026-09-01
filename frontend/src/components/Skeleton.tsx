export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-skeleton rounded-md bg-ink-200 ${className}`} />
}

export function StatTileSkeleton() {
  return (
    <div className="rounded-xl border border-ink-100 bg-surface p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-4 w-4" />
      </div>
      <Skeleton className="mt-3 h-7 w-16" />
    </div>
  )
}

export function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="rounded-xl border border-ink-100 bg-surface p-6 shadow-sm">
      <Skeleton className="mb-4 h-4 w-32" />
      <div className="space-y-2.5">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} className="h-3 w-full" />
        ))}
      </div>
    </div>
  )
}

export function TableRowSkeleton({ columns = 6 }: { columns?: number }) {
  return (
    <tr>
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-5 py-3.5">
          <Skeleton className="h-3.5 w-full max-w-24" />
        </td>
      ))}
    </tr>
  )
}
