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
    className: 'bg-good-soft text-good',
    icon: <CheckCircle2 size={13} />,
  },
  failed: {
    label: 'Failed',
    className: 'bg-critical-soft text-critical',
    icon: <XCircle size={13} />,
  },
}

/**
 * A running trace shows how far it has got.
 *
 * "Tracing" on its own is the same badge whether the trace started two
 * seconds or two hours ago, so a stalled case is indistinguishable from a
 * healthy one in the list - which is exactly how a dead worker goes
 * unnoticed. The hop count costs one line and removes that ambiguity.
 */
export function StatusBadge({ status, hop, hopLimit }: {
  status: CaseStatus
  hop?: number
  hopLimit?: number
}) {
  const config = CONFIG[status]
  const showProgress = status === 'tracing' && typeof hop === 'number' && !!hopLimit

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${config.className}`}
      title={showProgress ? `Completed ${hop} of ${hopLimit} hops` : undefined}
    >
      {config.icon}
      {config.label}
      {showProgress && (
        <span className="tabular font-normal opacity-70">{hop}/{hopLimit}</span>
      )}
    </span>
  )
}
