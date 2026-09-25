import { AlertTriangle, ExternalLink, Loader2, Send } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { findExistingTraces, submitTrace, type ExistingTrace } from '../api/client'
import { SmartComplaintParser } from '../components/SmartComplaintParser'
import { ChainMark, chainMeta } from '../components/ChainMark'
import { RiskBadge, StatusPill } from '../components/ui/Primitives'
import type { Chain } from '../types'

const CHAINS: { value: Chain; label: string; placeholder: string }[] = [
  { value: 'ethereum', label: 'Ethereum', placeholder: '0xeb2d2f1b8c558a40207669291fda468e50c8a0bb' },
  { value: 'polygon', label: 'Polygon', placeholder: '0xeb2d2f1b8c558a40207669291fda468e50c8a0bb' },
  { value: 'tron', label: 'Tron (USDT)', placeholder: 'T… (34-char Base58)' },
  { value: 'bitcoin', label: 'Bitcoin', placeholder: 'bc1… / 1… / 3…' },
  { value: 'bsc', label: 'BSC', placeholder: '0xeb2d2f1b8c558a40207669291fda468e50c8a0bb' },
]

function validateAddressFormat(addr: string, ch: Chain): string | null {
  const trimmed = addr.trim()
  if (!trimmed) return null
  if (['ethereum', 'bsc', 'polygon'].includes(ch)) {
    if (!trimmed.startsWith('0x') && !trimmed.startsWith('0X')) {
      return `Invalid ${ch.toUpperCase()} address: Must start with prefix '0x'.`
    }
    if (trimmed.length !== 42) {
      return `Invalid ${ch.toUpperCase()} address length (${trimmed.length} chars). Must be exactly 42 characters (0x + 40 hex characters).`
    }
    if (!/^0x[a-fA-F0-9]{40}$/.test(trimmed)) {
      return `Invalid ${ch.toUpperCase()} address: Contains non-hexadecimal characters.`
    }
  } else if (ch === 'tron') {
    if (!trimmed.startsWith('T')) {
      return `Invalid TRON address: Must start with prefix 'T'.`
    }
    if (trimmed.length !== 34) {
      return `Invalid TRON address length (${trimmed.length} chars). Must be exactly 34 characters.`
    }
    if (!/^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(trimmed)) {
      return `Invalid TRON address format (Base58check).`
    }
  } else if (ch === 'bitcoin') {
    if (!/^(1|3|bc1)/i.test(trimmed)) {
      return `Invalid Bitcoin address prefix. Must start with '1' (Legacy), '3' (Script), or 'bc1' (SegWit).`
    }
    if (trimmed.length < 26 || trimmed.length > 62) {
      return `Invalid Bitcoin address length (${trimmed.length} chars). Must be between 26 and 62 characters.`
    }
    // Base58 excludes four glyphs easy to confuse by eye: 0, O, I and l.
    // Written as [1-9A-HJ-NP-Za-km-z] - NOT "...Za-k-z", which parses as
    // the range a-k, a literal hyphen, then z, silently rejecting every
    // real address containing a letter from m to y. That typo lived in
    // this file (and, until recently, in the backend's own copy of this
    // pattern) and rejected the majority of real Bitcoin addresses before
    // the request ever left the browser - most base58 addresses contain at
    // least one letter in that dropped range.
    if (!/^(1[1-9A-HJ-NP-Za-km-z]{25,34}|3[1-9A-HJ-NP-Za-km-z]{25,34}|bc1[0-9a-zA-Z]{38,59})$/.test(trimmed)) {
      return `Invalid Bitcoin address format.`
    }
  }
  return null
}

// EVM chains share one address format (0x + 40 hex), so a bare address
// can't tell Ethereum, Polygon and BSC apart - only the family. Bitcoin and
// Tron each have a distinct, unambiguous format, so those can be detected
// outright. This is what "auto-selects the chain" means in practice below:
// jump to the specific chain when the format is unambiguous, and jump to
// the EVM family's default (Ethereum) only when the currently selected
// chain isn't already an EVM chain - so picking Polygon or BSC by hand is
// never silently overridden while typing a matching address.
const EVM_CHAINS: Chain[] = ['ethereum', 'bsc', 'polygon']

function detectChainFamily(addr: string): Chain | 'evm' | null {
  const trimmed = addr.trim()
  if (!trimmed) return null
  if (/^0x[a-fA-F0-9]{40}$/.test(trimmed)) return 'evm'
  if (/^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(trimmed)) return 'tron'
  if (/^(1[1-9A-HJ-NP-Za-km-z]{25,34}|3[1-9A-HJ-NP-Za-km-z]{25,34}|bc1[0-9a-zA-Z]{38,59})$/.test(trimmed)) return 'bitcoin'
  return null
}

export function NewCase() {
  const navigate = useNavigate()
  const [address, setAddress] = useState('')
  const [chain, setChain] = useState<Chain>('ethereum')
  const [complaintRef, setComplaintRef] = useState('')
  const [narrative, setNarrative] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [existing, setExisting] = useState<ExistingTrace[]>([])
  const [checkingExisting, setCheckingExisting] = useState(false)

  const activeChain = CHAINS.find((c) => c.value === chain)!

  // Auto-detect the chain from the address as it's typed, so pasting a
  // Bitcoin address while Ethereum is still selected (the default) doesn't
  // produce a false "invalid address" - the exact failure this was added
  // to fix.
  useEffect(() => {
    const family = detectChainFamily(address)
    if (family === 'bitcoin' && chain !== 'bitcoin') setChain('bitcoin')
    else if (family === 'tron' && chain !== 'tron') setChain('tron')
    else if (family === 'evm' && !EVM_CHAINS.includes(chain)) setChain('ethereum')
  }, [address])

  const validationError = useMemo(() => {
    return validateAddressFormat(address, chain)
  }, [address, chain])

  // Before anyone submits a trace, check whether this exact wallet has
  // already been traced. Submitting the same wallet twice isn't wrong in
  // itself - a second, independent complaint naming it is exactly the
  // prior-report signal this system exists to catch - but doing it by
  // accident produces a confusing duplicate: a near-empty new case sitting
  // next to a rich, already-completed one for the same address. Better to
  // show what's already on file before a trace starts than to explain the
  // mismatch afterwards.
  useEffect(() => {
    if (validationError || !address.trim()) {
      setExisting([])
      return
    }
    let active = true
    setCheckingExisting(true)
    const timer = window.setTimeout(() => {
      findExistingTraces(chain, address.trim())
        .then((rows) => active && setExisting(rows))
        .catch(() => active && setExisting([]))
        .finally(() => active && setCheckingExisting(false))
    }, 500)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [address, chain, validationError])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    const valErr = validateAddressFormat(address, chain)
    if (valErr) {
      setError(valErr)
      toast.error('Invalid Wallet Address', { description: valErr })
      return
    }

    setSubmitting(true)
    try {
      const { case_id } = await submitTrace({
        address: address.trim(),
        chain,
        complaint_ref: complaintRef.trim() || undefined,
        narrative: narrative.trim() || undefined,
      })
      toast.success('Trace started', { description: 'Tracing runs in the background — this page updates live.' })
      navigate(`/cases/${case_id}`)
    } catch (err: any) {
      const message = err?.response?.data?.detail || 'Could not submit this trace. Verify the wallet address and backend status.'
      setError(message)
      toast.error('Submission failed', { description: message })
      setSubmitting(false)
    }
  }

  const handleWalletExtracted = (extracted: {
    address: string
    chain: Chain
    complaintRef?: string
    narrative: string
  }) => {
    setAddress(extracted.address)
    setChain(extracted.chain)
    if (extracted.complaintRef) setComplaintRef(extracted.complaintRef)
    if (extracted.narrative) setNarrative(extracted.narrative)
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-8">
      <div className="space-y-6">
        {/* Smart Complaint Extractor */}
        <SmartComplaintParser onSelectWallet={handleWalletExtracted} />

        {/* Manual Intake Form */}
        <form onSubmit={handleSubmit} className="space-y-4 rounded-md border border-ink-100 bg-surface p-6 shadow-xs">
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-ink-800">Target Blockchain</label>
            {/* The selected chain's own brand colour carries the border, so
                the control identifies the network at a glance rather than
                relying on the label alone. */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              {CHAINS.map((c) => {
                const active = chain === c.value
                const { color } = chainMeta(c.value)
                return (
                  <button
                    type="button"
                    key={c.value}
                    onClick={() => setChain(c.value)}
                    aria-pressed={active}
                    className={`flex cursor-pointer items-center gap-2 rounded border px-2.5 py-2 text-[13px] font-medium transition-colors ${active
                        ? 'bg-surface text-ink-900'
                        : 'border-ink-200 text-ink-600 hover:border-ink-300 hover:text-ink-900'
                      }`}
                    style={active ? { borderColor: color } : undefined}
                  >
                    <ChainMark chain={c.value} size={17} />
                    {c.label}
                  </button>
                )
              })}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold text-ink-800" htmlFor="address">
              Suspect Wallet Address
            </label>
            <input
              id="address"
              required
              value={address}
              onChange={(e) => {
                setAddress(e.target.value)
                setError(null)
              }}
              placeholder={activeChain.placeholder}
              className={`w-full rounded-lg border bg-surface px-3.5 py-2 font-mono text-xs text-ink-900 outline-hidden transition-colors ${validationError
                  ? 'border-critical focus:border-critical'
                  : 'border-ink-200 focus:border-brand-500 focus:ring-1 focus:ring-brand-500'
                }`}
            />
            {address.toLowerCase() === '0xa5e0829caced8ffdd4de3c43696c57f7d7a678ff' && chain === 'ethereum' && (
              <div className="mt-2 rounded-md border border-brand-300 bg-brand-50/70 p-2.5 text-xs text-brand-900 flex items-center justify-between">
                <span>⚠️ <strong>Note:</strong> This address is the QuickSwap Router on <strong>Polygon</strong>. On Ethereum it has 0 transfers.</span>
                <button
                  type="button"
                  onClick={() => setChain('polygon')}
                  className="ml-2 underline font-semibold text-brand-700 hover:text-brand-900 cursor-pointer"
                >
                  Switch to Polygon
                </button>
              </div>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-ink-500">
              <span className="text-[11px] font-medium text-ink-400">Quick Test Examples:</span>
              <button
                type="button"
                onClick={() => {
                  setChain('polygon')
                  setAddress('0xa5e0829caced8ffdd4de3c43696c57f7d7a678ff')
                  setError(null)
                }}
                className="cursor-pointer rounded border border-ink-200 bg-surface px-2 py-0.5 text-[11px] font-mono hover:border-brand-500 hover:text-ink-900 transition-colors"
              >
                Polygon QuickSwap (120+ nodes)
              </button>
              <button
                type="button"
                onClick={() => {
                  setChain('ethereum')
                  setAddress('0xa84c1fa017fe678bcd1380715ba8398cbc517821')
                  setError(null)
                }}
                className="cursor-pointer rounded border border-ink-200 bg-surface px-2 py-0.5 text-[11px] font-mono hover:border-brand-500 hover:text-ink-900 transition-colors"
              >
                Ethereum Binance (22+ nodes)
              </button>
              <button
                type="button"
                onClick={() => {
                  setChain('bitcoin')
                  setAddress('1Kr6QSydW9bFQG1mXiPNNu6WpJGmUa9i1g')
                  setError(null)
                }}
                className="cursor-pointer rounded border border-ink-200 bg-surface px-2 py-0.5 text-[11px] font-mono hover:border-brand-500 hover:text-ink-900 transition-colors"
              >
                Bitcoin Mempool (Active UTXO)
              </button>
            </div>
            {validationError && (
              <p className="mt-1.5 text-xs text-critical font-medium">{validationError}</p>
            )}
            {!validationError && checkingExisting && (
              <p className="mt-1.5 flex items-center gap-1.5 text-[11px] text-ink-400">
                <Loader2 size={11} className="animate-spin" /> Checking whether this wallet has been traced before…
              </p>
            )}
            {existing.length > 0 && (
              <div className="mt-2 rounded-lg border border-warning/40 bg-warning-soft p-3">
                <p className="flex items-center gap-1.5 text-xs font-semibold text-ink-800">
                  <AlertTriangle size={13} className="shrink-0 text-warning" />
                  This wallet has already been traced
                  {existing.length > 1 ? ` — ${existing.length} existing cases` : ''}
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-ink-600">
                  Submitting again starts a brand-new, independent trace — useful if this is a
                  genuinely separate complaint, but if you're looking for the earlier result, open
                  it directly below rather than re-tracing.
                </p>
                <ul className="mt-2 space-y-1.5">
                  {existing.slice(0, 3).map((c) => (
                    <li key={c.case_id}>
                      <Link
                        to={`/cases/${c.case_id}`}
                        className="flex flex-wrap items-center gap-2 rounded-md border border-ink-200 bg-surface px-2.5 py-1.5 text-[11px] transition-colors hover:border-brand-500"
                      >
                        <StatusPill status={c.status} />
                        {c.risk_score !== null && <RiskBadge score={c.risk_score} />}
                        <span className="text-ink-600">{c.complaint_ref || 'no reference'}</span>
                        <span className="text-ink-400">
                          {new Date(c.created_at).toLocaleDateString()}
                        </span>
                        {c.nearest_exchange && (
                          <span className="text-good">→ {c.nearest_exchange.name}</span>
                        )}
                        <ExternalLink size={11} className="ml-auto shrink-0 text-ink-400" />
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold text-ink-800" htmlFor="complaint-ref">
              Complaint / NCRP Reference <span className="font-normal text-ink-400">(optional)</span>
            </label>
            <input
              id="complaint-ref"
              value={complaintRef}
              onChange={(e) => setComplaintRef(e.target.value)}
              placeholder="e.g. NCRP/2026/000123 or FIR No. 45/2026"
              className="w-full rounded-lg border border-ink-200 bg-surface px-3.5 py-2 text-xs text-ink-900 outline-hidden focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold text-ink-800" htmlFor="narrative">
              Complaint Narrative / Description <span className="font-normal text-ink-400">(optional)</span>
            </label>
            <textarea
              id="narrative"
              value={narrative}
              onChange={(e) => setNarrative(e.target.value)}
              rows={3}
              placeholder="e.g. Victim reported being promised 50% returns on a crypto trading app. Sent funds from private wallet..."
              className="w-full resize-none rounded-lg border border-ink-200 bg-surface px-3.5 py-2 text-xs text-ink-900 outline-hidden focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
            />
            <p className="mt-1 text-[11px] text-ink-400">
              The narrative is automatically analyzed by the rule-based NLP classifier to determine the fraud typology.
            </p>
          </div>

          {error && <p className="text-xs text-critical font-medium">{error}</p>}

          <button
            type="submit"
            disabled={submitting || !!validationError}
            className={`flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-xs font-semibold shadow-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
              existing.length > 0
                ? 'border border-ink-200 bg-surface text-ink-700 hover:border-ink-400'
                : 'bg-brand-600 text-white hover:bg-brand-700'
            }`}
          >
            {submitting ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
            {submitting ? 'Initiating Trace…' : existing.length > 0 ? 'Trace Again Anyway' : 'Start Multi-Hop Trace'}
          </button>
        </form>
      </div>
    </div>
  )
}
