import { useState } from 'react'
import { CheckCircle2, Fingerprint, Loader2, ShieldAlert, ShieldCheck, X } from 'lucide-react'
import { toast } from 'sonner'
import { verifyEvidenceHash } from '../api/client'
import type { HashVerificationResult } from '../types'

interface Props {
  open: boolean
  onClose: () => void
  initialHash?: string
  initialCaseId?: string
}

export function HashVerifierModal({ open, onClose, initialHash = '', initialCaseId }: Props) {
  const [hash, setHash] = useState(initialHash)
  const [caseId, setCaseId] = useState(initialCaseId || '')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<HashVerificationResult | null>(null)

  if (!open) return null

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!hash.trim()) {
      toast.error('Please enter a SHA-256 hash to verify')
      return
    }
    setLoading(true)
    try {
      const data = await verifyEvidenceHash(hash.trim(), caseId.trim() || undefined)
      setResult(data)
      if (data.verified) {
        toast.success('Cryptographic verification successful: Authentic record!')
      } else {
        toast.error('Verification failed: Hash mismatch or unrecognized record.')
      }
    } catch {
      toast.error('Failed to verify hash with server')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-lg rounded-2xl border border-ink-100 bg-surface p-6 shadow-2xl">
        <div className="flex items-start justify-between pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-950/40">
              <Fingerprint className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-ink-900">Chain-of-Custody Hash Verifier</h2>
              <p className="text-xs text-ink-500">Cryptographically verify report integrity against immutable ledger record</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleVerify} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-ink-700">SHA-256 Evidence Snapshot Hash</label>
            <input
              type="text"
              required
              value={hash}
              onChange={(e) => setHash(e.target.value)}
              placeholder="e.g. 8a3f5b2c9d1e4f7a6b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0"
              className="mt-1.5 w-full rounded-lg border border-ink-200 bg-surface p-2.5 font-mono text-xs text-ink-900 focus:border-brand-500 focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-ink-700">Case ID (Optional)</label>
            <input
              type="text"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              placeholder="Leave blank to search across all cases"
              className="mt-1.5 w-full rounded-lg border border-ink-200 bg-surface p-2.5 font-mono text-xs text-ink-900 focus:border-brand-500 focus:outline-hidden"
            />
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-xs font-medium text-ink-600 hover:bg-ink-100"
            >
              Close
            </button>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-xs font-medium text-white shadow-xs hover:bg-brand-700 disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
              Verify Cryptographic Integrity
            </button>
          </div>
        </form>

        {result && (
          <div className="mt-5 border-t border-ink-100 pt-4">
            {result.verified ? (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4 dark:border-emerald-900/40 dark:bg-emerald-950/20">
                <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                  <span className="text-sm font-semibold">Authentic &amp; Tamper-Evident Record</span>
                </div>
                <p className="mt-1 text-xs text-emerald-700 dark:text-emerald-400">
                  The SHA-256 hash matches the exact mathematical snapshot recorded at the time of investigation.
                </p>

                <div className="mt-3 space-y-1.5 rounded-lg bg-surface/80 p-3 text-xs">
                  <div className="flex justify-between">
                    <span className="text-ink-500">Case ID:</span>
                    <span className="font-mono font-medium text-ink-900">{result.case_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-ink-500">Reported Wallet:</span>
                    <span className="font-mono font-medium text-ink-900">{result.reported_address}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-ink-500">Blockchain:</span>
                    <span className="font-medium uppercase text-ink-900">{result.chain}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-ink-500">Calculated Risk Score:</span>
                    <span className="font-semibold text-ink-900">{result.risk_score} / 100</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-red-200 bg-red-50/60 p-4 dark:border-red-900/40 dark:bg-red-950/20">
                <div className="flex items-center gap-2 text-red-800 dark:text-red-300">
                  <ShieldAlert className="h-5 w-5 text-red-600" />
                  <span className="text-sm font-semibold">Verification Failed / Unrecognized</span>
                </div>
                <p className="mt-1 text-xs text-red-700 dark:text-red-400">
                  {result.message || 'The submitted SHA-256 hash does not match any authentic case snapshot in the database. The evidence may have been modified or originates from an external system.'}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
