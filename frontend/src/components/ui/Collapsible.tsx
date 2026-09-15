/**
 * A section that opens on demand.
 *
 * Reference material — how the wallets cluster, what the audit record holds —
 * is worth having and worth keeping out of the way. Left expanded it competes
 * with the findings for a first read, and an investigator scanning a case has
 * to scroll past it every time to reach what they came for. Closed, it costs
 * one line and stays one click away.
 *
 * The heading says what is inside rather than only naming it, so the decision
 * to open is informed rather than exploratory.
 */
import { ChevronDown } from 'lucide-react'
import { useState, type ReactNode } from 'react'

export function Collapsible({ title, hint, children, defaultOpen = false, open: controlledOpen, onOpenChange, id }: {
  title: string
  hint?: string
  children: ReactNode
  defaultOpen?: boolean
  /** Pass to control the section from outside, e.g. to open it from a link elsewhere. */
  open?: boolean
  onOpenChange?: (open: boolean) => void
  id?: string
}) {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen)
  const open = controlledOpen ?? uncontrolledOpen
  const setOpen = (update: (o: boolean) => boolean) => {
    const next = update(open)
    if (controlledOpen === undefined) setUncontrolledOpen(next)
    onOpenChange?.(next)
  }

  return (
    <section id={id} className="scroll-mt-6 rounded-md border border-ink-200 bg-surface">
      <button
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-center gap-2.5 px-4 py-3 text-left transition-colors hover:bg-ink-50"
      >
        <ChevronDown
          size={14}
          className={`shrink-0 text-ink-500 transition-transform ${open ? 'rotate-180' : ''}`}
        />
        <span className="text-[13px] font-semibold text-ink-900">{title}</span>
        {hint && <span className="truncate text-[11px] text-ink-500">{hint}</span>}
      </button>
      {open && <div className="border-t border-ink-200 p-4">{children}</div>}
    </section>
  )
}
