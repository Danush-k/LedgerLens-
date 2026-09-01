import { Loader2, Send } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { submitTrace } from '../api/client'
import { SmartComplaintParser } from '../components/SmartComplaintParser'
import type { Chain } from '../types'

const CHAINS: { value: Chain; label: string; placeholder: string }[] = [
  { value: 'ethereum', label: 'Ethereum', placeholder: '0xeb2d2f1b8c558a40207669291fda468e50c8a0bb' },
  { value: 'bsc', label: 'BSC', placeholder: '0xeb2d2f1b8c558a40207669291fda468e50c8a0bb' },
  { value: 'polygon', label: 'Polygon', placeholder: '0xeb2d2f1b8c558a40207669291fda468e50c8a0bb' },
  { value: 'bitcoin', label: 'Bitcoin', placeholder: 'bc1… / 1… / 3…' },
  { value: 'tron', label: 'Tron (TRC-20 USDT)', placeholder: 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t' },
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
  } else if (ch === 'bitcoin') {
    if (!/^(1|3|bc1)/i.test(trimmed)) {
      return `Invalid Bitcoin address prefix. Must start with '1' (Legacy), '3' (Script), or 'bc1' (SegWit).`
    }
    if (trimmed.length < 26 || trimmed.length > 62) {
      return `Invalid Bitcoin address length (${trimmed.length} chars). Must be between 26 and 62 characters.`
    }
    if (!/^(1[1-9A-HJ-NP-Za-k-z]{25,34}|3[1-9A-HJ-NP-Za-k-z]{25,34}|bc1[0-9a-zA-Z]{38,59})$/.test(trimmed)) {
      return `Invalid Bitcoin address format.`
    }
  } else if (ch === 'tron') {
    if (!trimmed.startsWith('T')) {
      return `Invalid Tron address: Must start with prefix 'T'.`
    }
    if (trimmed.length !== 34) {
      return `Invalid Tron address length (${trimmed.length} chars). Must be exactly 34 characters.`
    }
    if (!/^T[1-9A-HJ-NP-Za-k-z]{33}$/.test(trimmed)) {
      return `Invalid Tron address format.`
    }
  }
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

  const activeChain = CHAINS.find((c) => c.value === chain)!

  const validationError = useMemo(() => {
    return validateAddressFormat(address, chain)
  }, [address, chain])

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
        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-ink-100 bg-surface p-6 shadow-xs">
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-ink-800">Target Blockchain</label>
            <div className="grid grid-cols-4 gap-2">
              {CHAINS.map((c) => (
                <button
                  type="button"
                  key={c.value}
                  onClick={() => setChain(c.value)}
                  className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                    chain === c.value
                      ? 'border-brand-500 bg-brand-500/10 text-brand-600'
                      : 'border-ink-200 text-ink-600 hover:border-ink-300'
                  }`}
                >
                  {c.label}
                </button>
              ))}
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
              className={`w-full rounded-lg border bg-surface px-3.5 py-2 font-mono text-xs text-ink-900 outline-hidden transition-colors ${
                validationError
                  ? 'border-red-400 focus:border-red-500 focus:ring-1 focus:ring-red-500'
                  : 'border-ink-200 focus:border-brand-500 focus:ring-1 focus:ring-brand-500'
              }`}
            />
            {validationError && (
              <p className="mt-1.5 text-xs text-red-600 font-medium">{validationError}</p>
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

          {error && <p className="text-xs text-red-600 font-medium">{error}</p>}

          <button
            type="submit"
            disabled={submitting || !!validationError}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
            {submitting ? 'Initiating Trace…' : 'Start Multi-Hop Trace'}
          </button>
        </form>
      </div>
    </div>
  )
}
