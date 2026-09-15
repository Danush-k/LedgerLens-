/**
 * Movement on this case since its trace finished, as it happens.
 *
 * The header says whether what is on screen is current - connected, when the
 * wallets were last read, and whether that read succeeded. A live panel that
 * cannot tell "nothing moved" from "we could not look" is worse than none,
 * because it makes staleness look like calm.
 */
import { AlertTriangle, ArrowRight, Crosshair, ExternalLink, Radio } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getLiveTransfers } from '../api/client'
import type { LiveMode } from '../hooks/useLiveCase'
import type { CaseStatus, LiveCheck, LiveTransfer } from '../types'
import { explorerTxUrl } from '../utils/explorer'
import { formatAmount } from '../utils/format'

const UNITS: Record<string, string> = {
  bitcoin: 'BTC', ethereum: 'ETH', bsc: 'BNB', polygon: 'MATIC', tron: 'USDT',
}

interface Props {
  caseId: string
  chain: string
  status: CaseStatus
  mode: LiveMode
  pollSeconds: number
  lastCheck: LiveCheck | null
  checkedAt: string | null | undefined
  liveWatch: boolean
  version: number
  arrivals: Set<string>
  onToggleWatch: (enabled: boolean) => void
  onLocate: (address: string) => void
}

function ago(iso: string | null | undefined, now: number) {
  if (!iso) return null
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)} h ago`
  return new Date(iso).toLocaleDateString()
}

function short(address: string) {
  return address.length > 16 ? `${address.slice(0, 8)}…${address.slice(-5)}` : address
}

export function LiveActivityPanel({
  caseId, chain, status, mode, pollSeconds, lastCheck, checkedAt, liveWatch, version, arrivals,
  onToggleWatch, onLocate,
}: Props) {
  const [transfers, setTransfers] = useState<LiveTransfer[]>([])
  const [now, setNow] = useState(() => Date.now())
  const unit = UNITS[chain] ?? ''

  useEffect(() => {
    let active = true
    getLiveTransfers(caseId).then(rows => active && setTransfers(rows)).catch(() => {})
    return () => { active = false }
  }, [caseId, version])

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 5_000)
    return () => window.clearInterval(timer)
  }, [])

  const complete = status === 'complete'
  const lastRead = ago(lastCheck?.checked_at ?? checkedAt, now)
  const failed = lastCheck?.errors.length ?? 0

  const indicator =
    !complete ? { dot: 'bg-ink-300', text: 'Starts when the trace finishes' }
    : mode === 'live' ? {
        dot: 'bg-good animate-pulse',
        text: `Live · ${lastCheck ? `watching ${lastCheck.addresses_checked} wallet${lastCheck.addresses_checked === 1 ? '' : 's'}` : 'connected'}${lastRead ? ` · checked ${lastRead}` : ''}`,
      }
    : mode === 'connecting' ? { dot: 'bg-warning animate-pulse', text: 'Reconnecting to live updates…' }
    : { dot: 'bg-warning', text: `Live stream unavailable · refreshing every 5s${lastRead ? ` · checked ${lastRead}` : ''}` }

  const sourceId = (t: LiveTransfer) => `${t.chain}:${t.from_address}`

  return (
    <section aria-labelledby="live-title" className="overflow-hidden rounded-md border border-ink-200 bg-surface">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-200 px-4 py-3">
        <div className="min-w-0">
          <h2 id="live-title" className="flex items-center gap-2 text-sm font-semibold text-ink-900">
            <Radio size={15} className="text-ink-500" aria-hidden="true" />
            Live activity
            {transfers.length > 0 && (
              <span className="rounded bg-warning-soft px-1.5 py-0.5 text-[10px] font-semibold text-warning">
                {transfers.length} since trace
              </span>
            )}
          </h2>
          <p className="mt-1 flex items-center gap-1.5 text-xs text-ink-500" aria-live="polite">
            <span className={`inline-block h-2 w-2 rounded-full ${indicator.dot}`} aria-hidden="true" />
            {indicator.text}
          </p>
        </div>

        {complete && (
          <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-600">
            <span className="text-right leading-tight">
              Keep watching when closed
              <span className="block text-[10.5px] text-ink-400">Uses shared explorer quota</span>
            </span>
            <button
              type="button"
              role="switch"
              aria-checked={liveWatch}
              onClick={() => onToggleWatch(!liveWatch)}
              className={`relative h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors ${liveWatch ? 'bg-good' : 'bg-ink-300'}`}
            >
              <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${liveWatch ? 'left-[18px]' : 'left-0.5'}`} />
            </button>
          </label>
        )}
      </header>

      {complete && failed > 0 && (
        <p className="flex items-start gap-2 border-b border-warning/25 bg-warning-soft px-4 py-2 text-xs text-ink-700">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
          Could not read {failed} of {lastCheck!.addresses_checked} wallets on the last check — the block explorer
          did not answer. Those wallets are not assumed to be quiet; they will be retried in {pollSeconds}s.
        </p>
      )}

      {transfers.length === 0 ? (
        <p className="px-4 py-6 text-center text-xs leading-relaxed text-ink-500">
          {complete
            ? <>No new movement since the trace finished. Any new transfer from a traced wallet appears here within about {pollSeconds} seconds while this page is open.</>
            : <>Once the trace finishes, its wallets are re-checked every {pollSeconds} seconds and new transactions appear here and on the graph.</>}
        </p>
      ) : (
        <ol className="max-h-80 divide-y divide-ink-100 overflow-y-auto">
          {transfers.map(t => {
            const isNew = arrivals.has(`${t.tx_hash}|${sourceId(t)}|${t.chain}:${t.to_address}`)
            const url = explorerTxUrl(t.chain, t.tx_hash)
            return (
              <li key={`${t.tx_hash}-${t.to_address}`} className={`flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-xs ${isNew ? 'bg-warning-soft/60' : ''}`}>
                <span className="w-20 shrink-0 text-ink-500" title={new Date(t.detected_at).toLocaleString()}>
                  {isNew && <span className="mr-1 rounded bg-warning px-1 py-px text-[9px] font-bold text-white">NEW</span>}
                  {ago(t.detected_at, now)}
                </span>
                <span className="tabular w-28 shrink-0 font-semibold text-ink-900">{formatAmount(t.value)} {unit}</span>
                <span className="flex min-w-0 flex-1 items-center gap-1.5 font-mono text-[11px] text-ink-700">
                  <span title={t.from_address}>{short(t.from_address)}</span>
                  <ArrowRight size={12} className="shrink-0 text-ink-400" aria-hidden="true" />
                  <span title={t.to_address}>{short(t.to_address)}</span>
                  {t.to_label_name && (
                    <span className={`rounded px-1.5 py-px font-sans text-[10px] font-semibold ${
                      t.to_node_type === 'exchange' ? 'bg-good-soft text-good'
                      : t.to_node_type === 'mixer' ? 'bg-critical-soft text-critical' : 'bg-ink-100 text-ink-600'
                    }`}>
                      {t.to_label_name}
                    </span>
                  )}
                </span>
                <span className="flex shrink-0 items-center gap-3">
                  <button type="button" onClick={() => onLocate(t.to_address)} className="inline-flex cursor-pointer items-center gap-1 text-brand-600 hover:underline">
                    <Crosshair size={12} /> Graph
                  </button>
                  {url && (
                    <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ink-500 hover:text-brand-600">
                      Tx <ExternalLink size={11} />
                    </a>
                  )}
                </span>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
