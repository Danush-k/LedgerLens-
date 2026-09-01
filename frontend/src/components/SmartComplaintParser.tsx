import { useState } from 'react'
import { ArrowRight, FileSearch, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { parseComplaintText } from '../api/client'
import type { Chain, ParsedComplaintResult, ParsedWallet } from '../types'

interface Props {
  onSelectWallet: (wallet: { address: string; chain: Chain; complaintRef?: string; narrative: string }) => void
}

export function SmartComplaintParser({ onSelectWallet }: Props) {
  const [rawText, setRawText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ParsedComplaintResult | null>(null)

  const handleParse = async () => {
    if (!rawText.trim()) {
      toast.error('Please paste a complaint text or FIR first')
      return
    }
    setLoading(true)
    try {
      const data = await parseComplaintText(rawText)
      setResult(data)
      if (data.extracted_count === 0) {
        toast.info('No cryptocurrency wallet addresses detected in the text.')
      } else {
        toast.success(`Found ${data.extracted_count} suspect wallet address(es)!`)
      }
    } catch {
      toast.error('Failed to parse complaint narrative')
    } finally {
      setLoading(false)
    }
  }

  const handleUseWallet = (wallet: ParsedWallet) => {
    const chain = (wallet.chain === 'tron' ? 'ethereum' : wallet.chain) as Chain
    onSelectWallet({
      address: wallet.address,
      chain,
      complaintRef: result?.complaint_refs[0] || '',
      narrative: rawText.slice(0, 500),
    })
    toast.success(`Populated form with ${wallet.address.slice(0, 10)}...`)
  }

  return (
    <div className="rounded-xl border border-ink-100 bg-surface p-5 shadow-xs">
      <div className="pb-3">
        <h3 className="text-sm font-semibold text-ink-900">Smart Intake — Extract from FIR / Complaint Narrative</h3>
        <p className="text-xs text-ink-500">Paste unformatted victim emails, NCRP reports, or FIR transcripts to auto-detect wallets &amp; entities.</p>
      </div>

      <div className="space-y-3">
        <textarea
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          placeholder="Paste complaint text or FIR narrative..."
          rows={3}
          className="w-full rounded-lg border border-ink-200 bg-ink-50/50 p-3 text-xs text-ink-900 placeholder:text-ink-400 focus:border-brand-500 focus:bg-surface focus:outline-hidden"
        />

        <div className="flex justify-end gap-2">
          {rawText && (
            <button
              type="button"
              onClick={() => {
                setRawText('')
                setResult(null)
              }}
              className="rounded-lg px-3 py-1.5 text-xs text-ink-500 hover:bg-ink-100 hover:text-ink-700"
            >
              Clear
            </button>
          )}
          <button
            type="button"
            onClick={handleParse}
            disabled={loading || !rawText.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-xs font-medium text-white shadow-xs hover:bg-brand-700 disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileSearch className="h-3.5 w-3.5" />}
            Extract
          </button>
        </div>

        {result && result.extracted_count > 0 && (
          <div className="mt-4 space-y-3 rounded-lg border border-brand-100 bg-brand-50/40 p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-brand-900">
                Detected Suspect Wallets ({result.wallets.length})
              </span>
              <span className="text-[11px] text-ink-500">Click &quot;Auto-Fill&quot; to populate form</span>
            </div>

            <div className="space-y-2">
              {result.wallets.map((w, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between rounded-md border border-ink-200 bg-surface p-2.5 text-xs shadow-2xs"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-medium text-ink-900">{w.address}</span>
                      <span className="rounded-full bg-ink-100 px-2 py-0.5 text-[10px] font-medium uppercase text-ink-700">
                        {w.chain}
                      </span>
                    </div>
                    <p className="text-[10px] text-ink-500">{w.format}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleUseWallet(w)}
                    className="inline-flex items-center gap-1 rounded-md bg-brand-600 px-2.5 py-1 text-[11px] font-medium text-white hover:bg-brand-700"
                  >
                    Auto-Fill <ArrowRight className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>

            {(result.upi_ids.length > 0 || result.tx_hashes.length > 0 || result.amounts.length > 0) && (
              <div className="grid grid-cols-1 gap-2 pt-2 sm:grid-cols-3">
                {result.upi_ids.length > 0 && (
                  <div className="rounded-md bg-surface p-2 text-[11px]">
                    <span className="font-medium text-ink-500">UPI Handles:</span>
                    <p className="font-mono text-ink-900">{result.upi_ids.join(', ')}</p>
                  </div>
                )}
                {result.amounts.length > 0 && (
                  <div className="rounded-md bg-surface p-2 text-[11px]">
                    <span className="font-medium text-ink-500">Amounts Mentioned:</span>
                    <p className="font-mono text-ink-900">{result.amounts.join(', ')}</p>
                  </div>
                )}
                {result.complaint_refs.length > 0 && (
                  <div className="rounded-md bg-surface p-2 text-[11px]">
                    <span className="font-medium text-ink-500">Complaint Refs:</span>
                    <p className="font-mono text-ink-900">{result.complaint_refs.join(', ')}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
