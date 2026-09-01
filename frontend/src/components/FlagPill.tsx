import { AlertTriangle, ArrowLeftRight, GitBranch, Repeat, ShieldAlert, Zap } from 'lucide-react'

const FLAG_META: Record<string, { label: string; icon: React.ReactNode; className: string }> = {
  mixer_detected: {
    label: 'Mixer detected',
    icon: <ShieldAlert size={13} />,
    className: 'bg-red-500/10 text-red-600 border-red-500/20',
  },
  cross_chain_bridge: {
    label: 'Cross-chain bridge',
    icon: <ArrowLeftRight size={13} />,
    className: 'bg-purple-500/10 text-purple-600 border-purple-500/20',
  },
  no_exchange_found: {
    label: 'No exchange found',
    icon: <AlertTriangle size={13} />,
    className: 'bg-ink-500/10 text-ink-600 border-ink-200',
  },
  high_fan_out: {
    label: 'High fan-out',
    icon: <GitBranch size={13} />,
    className: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
  },
  rapid_layering: {
    label: 'Rapid layering',
    icon: <Zap size={13} />,
    className: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
  },
  prior_report: {
    label: 'Seen in prior case',
    icon: <Repeat size={13} />,
    className: 'bg-brand-500/10 text-brand-600 border-brand-500/20',
  },
}

export function FlagPill({ flag }: { flag: string }) {
  const meta = FLAG_META[flag] ?? {
    label: flag.replace(/_/g, ' '),
    icon: <AlertTriangle size={13} />,
    className: 'bg-ink-500/10 text-ink-600 border-ink-200',
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${meta.className}`}
    >
      {meta.icon}
      {meta.label}
    </span>
  )
}
