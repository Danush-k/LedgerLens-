import { CheckCircle2, Loader2, Upload, XCircle } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { submitBulkTrace } from '../api/client'
import type { BulkUploadResult } from '../types'

const SAMPLE_CSV = `address,chain,complaint_ref,narrative
34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo,bitcoin,NCRP/2026/000123,Victim paid into a fake trading platform promising guaranteed returns
0xeb2d2f1b8c558a40207669291fda468e50c8a0bb,ethereum,NCRP/2026/000124,`

export function BulkUpload() {
  const fileInput = useRef<HTMLInputElement>(null)
  const [fileName, setFileName] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<BulkUploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleFile(file: File) {
    setFileName(file.name)
    setSubmitting(true)
    setError(null)
    setResult(null)
    try {
      const data = await submitBulkTrace(file)
      setResult(data)
      if (data.accepted.length > 0) {
        toast.success(`${data.accepted.length} trace${data.accepted.length === 1 ? '' : 's'} queued`, {
          description: data.rejected.length > 0 ? `${data.rejected.length} row(s) rejected — see details below.` : undefined,
        })
      } else {
        toast.error('No rows accepted', { description: 'Check the CSV format and try again.' })
      }
    } catch {
      const message = 'Upload failed. Check the CSV has "address" and "chain" columns and try again.'
      setError(message)
      toast.error('Upload failed', { description: message })
    } finally {
      setSubmitting(false)
    }
  }

  function downloadSample() {
    const blob = new Blob([SAMPLE_CSV], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'sample-wallets.csv'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="mx-auto max-w-2xl px-8 py-8">
      <h1 className="text-xl font-bold text-ink-900">Bulk wallet upload</h1>
      <p className="mt-1 text-sm text-ink-500">
        Investigators usually have a spreadsheet of wallets per case, not one address at a time — upload a CSV
        with <code className="rounded bg-ink-100 px-1 py-0.5 text-xs">address</code> and{' '}
        <code className="rounded bg-ink-100 px-1 py-0.5 text-xs">chain</code> columns
        (<code className="rounded bg-ink-100 px-1 py-0.5 text-xs">complaint_ref</code> and{' '}
        <code className="rounded bg-ink-100 px-1 py-0.5 text-xs">narrative</code> are optional). Up to 200 rows.
      </p>

      <div className="mt-6 rounded-xl border border-ink-100 bg-surface p-6 shadow-sm">
        <div
          onClick={() => fileInput.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault()
            const file = e.dataTransfer.files[0]
            if (file) handleFile(file)
          }}
          className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-ink-200 py-10 text-center transition-colors hover:border-brand-400"
        >
          <Upload size={24} className="text-ink-400" />
          <p className="text-sm font-medium text-ink-700">
            {fileName ?? 'Click to choose a CSV, or drag one here'}
          </p>
          <input
            ref={fileInput}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
        </div>

        <button onClick={downloadSample} className="mt-3 text-xs font-semibold text-brand-600 hover:underline">
          Download a sample CSV
        </button>

        {submitting && (
          <p className="mt-4 flex items-center gap-2 text-sm text-ink-500">
            <Loader2 size={14} className="animate-spin" /> Submitting rows…
          </p>
        )}
        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
      </div>

      {result && (
        <div className="mt-6 space-y-4">
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.06] p-5">
            <p className="flex items-center gap-2 text-sm font-semibold text-emerald-600">
              <CheckCircle2 size={16} />
              {result.accepted.length} trace{result.accepted.length === 1 ? '' : 's'} queued
            </p>
            {result.accepted.length > 0 && (
              <ul className="mt-2 space-y-1 text-xs text-ink-600">
                {result.accepted.map((r) => (
                  <li key={r.case_id}>
                    Row {r.row}: {r.address.slice(0, 14)}… →{' '}
                    <Link to={`/cases/${r.case_id}`} className="font-semibold text-emerald-600 hover:underline">
                      view case
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {result.rejected.length > 0 && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/[0.06] p-5">
              <p className="flex items-center gap-2 text-sm font-semibold text-red-600">
                <XCircle size={16} />
                {result.rejected.length} row{result.rejected.length === 1 ? '' : 's'} rejected
              </p>
              <ul className="mt-2 space-y-1 text-xs text-ink-600">
                {result.rejected.map((r, i) => (
                  <li key={i}>
                    Row {r.row}: {r.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
