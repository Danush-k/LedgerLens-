import { Radio } from 'lucide-react'
import type { AuditEvent } from '../types'

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function IntegrationLog({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-ink-500">No integration activity yet.</p>
  }

  return (
    <ul className="space-y-2.5">
      {events.map((e, i) => (
        <li key={i} className="flex items-start gap-2.5 text-sm">
          <span className="mt-0.5 text-ink-300">
            <Radio size={14} />
          </span>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium text-ink-800">{e.event.replace(/_/g, ' ')}</span>
              {e.simulated && (
                <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                  Simulated
                </span>
              )}
              <span className="text-xs text-ink-400">{formatTime(e.created_at)}</span>
            </div>
            {e.detail && <p className="mt-0.5 text-ink-500">{e.detail}</p>}
          </div>
        </li>
      ))}
    </ul>
  )
}
