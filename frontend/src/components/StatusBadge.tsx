import { CheckCircle2, Loader2, XCircle, Clock } from 'lucide-react'
import type { CaseStatus } from '../types'

const CONFIG: Record<CaseStatus, { label: string; className: string; icon: React.ReactNode }> = {
  queued: {
    label: 'Queued',
    className: 'bg-ink-500/10 text-ink-600',
    icon: <Clock size={13} />,
  },
  tracing: {
    label: 'Tracing',
    className: 'bg-brand-500/10 text-brand-600',
    icon: <Loader2 size={13} className="animate-spin" />,
  },
  complete: {
    label: 'Complete',
    className: 'bg-emerald-500/10 text-emerald-600',
    icon: <CheckCircle2 size={13} />,
  },
  failed: {
    label: 'Failed',
    className: 'bg-red-500/10 text-red-600',
    icon: <XCircle size={13} />,
  },
}

export function StatusBadge({ status }: { status: CaseStatus }) {
  const config = CONFIG[status]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${config.className}`}
    >
      {config.icon}
      {config.label}
    </span>
  )
}
