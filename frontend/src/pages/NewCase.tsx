import { Loader2, Send } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { submitTrace } from '../api/client'
import type { Chain } from '../types'

const CHAINS: { value: Chain; label: string; placeholder: string }[] = [
  { value: 'ethereum', label: 'Ethereum', placeholder: '0x…' },
  { value: 'bsc', label: 'BSC', placeholder: '0x…' },
  { value: 'polygon', label: 'Polygon', placeholder: '0x…' },
  { value: 'bitcoin', label: 'Bitcoin', placeholder: 'bc1… / 1… / 3…' },
]

export function NewCase() {
  const navigate = useNavigate()
  const [address, setAddress] = useState('')
  const [chain, setChain] = useState<Chain>('ethereum')
  const [complaintRef, setComplaintRef] = useState('')
  const [narrative, setNarrative] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeChain = CHAINS.find((c) => c.value === chain)!

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const { case_id } = await submitTrace({
        address: address.trim(),
        chain,
        complaint_ref: complaintRef.trim() || undefined,
        narrative: narrative.trim() || undefined,
      })
      navigate(`/cases/${case_id}`)
    } catch {
      setError('Could not submit this trace. Check the backend is running and try again.')
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-xl px-8 py-8">
      <h1 className="text-xl font-bold text-ink-900">New wallet trace</h1>
      <p className="mt-1 text-sm text-ink-500">
        Submit a victim-reported wallet address. Tracing runs in the background — you'll be
        taken to the case page and it will update live.
      </p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-5 rounded-xl border border-ink-100 bg-white p-6 shadow-sm">
        <div>
          <label className="mb-1.5 block text-sm font-semibold text-ink-800">Chain</label>
          <div className="grid grid-cols-4 gap-2">
            {CHAINS.map((c) => (
              <button
                type="button"
                key={c.value}
                onClick={() => setChain(c.value)}
                className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                  chain === c.value
                    ? 'border-brand-500 bg-brand-50 text-brand-700'
                    : 'border-ink-200 text-ink-600 hover:border-ink-300'
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-semibold text-ink-800" htmlFor="address">
            Suspect wallet address
          </label>
          <input
            id="address"
            required
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder={activeChain.placeholder}
            className="w-full rounded-lg border border-ink-200 px-3.5 py-2.5 font-mono text-sm text-ink-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          />
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-semibold text-ink-800" htmlFor="complaint-ref">
            Complaint reference <span className="font-normal text-ink-400">(optional)</span>
          </label>
          <input
            id="complaint-ref"
            value={complaintRef}
            onChange={(e) => setComplaintRef(e.target.value)}
            placeholder="e.g. NCRP/2026/000123"
            className="w-full rounded-lg border border-ink-200 px-3.5 py-2.5 text-sm text-ink-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          />
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-semibold text-ink-800" htmlFor="narrative">
            Complaint narrative <span className="font-normal text-ink-400">(optional)</span>
          </label>
          <textarea
            id="narrative"
            value={narrative}
            onChange={(e) => setNarrative(e.target.value)}
            rows={3}
            placeholder="e.g. Victim was promised guaranteed returns on a trading investment…"
            className="w-full resize-none rounded-lg border border-ink-200 px-3.5 py-2.5 text-sm text-ink-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          />
          <p className="mt-1 text-xs text-ink-400">
            A short description auto-tags the fraud typology (investment scam, phishing, sextortion, etc).
          </p>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-brand-500/20 transition-colors hover:bg-brand-600 disabled:opacity-60"
        >
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          {submitting ? 'Submitting…' : 'Start trace'}
        </button>
      </form>
    </div>
  )
}
