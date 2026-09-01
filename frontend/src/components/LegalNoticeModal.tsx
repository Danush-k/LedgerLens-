import { useState } from 'react'
import { Archive, CheckCircle2, Download, FileText, Loader2, ShieldCheck, X } from 'lucide-react'
import { toast } from 'sonner'
import { downloadEvidencePackage, downloadLegalNotice } from '../api/client'
import type { CaseDetail, LegalNoticeParams } from '../types'

interface Props {
  caseDetail: CaseDetail
  open: boolean
  onClose: () => void
}

export function LegalNoticeModal({ caseDetail, open, onClose }: Props) {
  const [loading, setLoading] = useState(false)

  // Empty initial state so the investigator can type their own details
  const [params, setParams] = useState<LegalNoticeParams>({
    officer_name: '',
    officer_designation: '',
    police_station: '',
    fir_number: caseDetail.complaint_ref || '',
    fir_date: new Date().toISOString().split('T')[0],
    victim_name: '',
    act_section: 'bnss_94',
  })

  if (!open) return null

  const handleDownload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!params.officer_name.trim()) {
      toast.error('Please enter the Investigating Officer Name')
      return
    }
    if (!params.police_station.trim()) {
      toast.error('Please enter the Police Station / Unit')
      return
    }
    setLoading(true)
    try {
      await downloadLegalNotice(caseDetail.id, params)
      toast.success('Legal Preservation Notice generated & downloaded!')
      onClose()
    } catch {
      toast.error('Failed to generate legal notice')
    } finally {
      setLoading(false)
    }
  }

  const nearestVasp = caseDetail.nearest_exchange?.name || 'Identified VASP / Cryptocurrency Exchange'
  const targetWallet = caseDetail.nearest_exchange?.address || caseDetail.reported_address

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-lg rounded-2xl border border-ink-200 bg-surface p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between pb-4 border-b border-ink-100">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 font-bold">
              <FileText className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-base font-bold text-ink-900">
                Generate LEA Legal Preservation Notice
              </h2>
              <p className="text-xs text-ink-500">
                Official statutory order for account freeze &amp; KYC preservation
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Clean Brand Slate Target Addressee Banner */}
        <div className="my-4 rounded-xl border border-brand-200 bg-brand-50/50 p-4 shadow-2xs">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 shrink-0 text-brand-600" />
            <span className="text-xs font-bold tracking-tight text-brand-950">
              TARGET ADDRESSEE: {nearestVasp.toUpperCase()}
            </span>
          </div>

          <p className="mt-1 text-xs text-ink-600">
            Directs immediate administrative debit freeze on suspect beneficiary wallet:
          </p>

          <div className="mt-2 flex items-center justify-between rounded-lg border border-ink-200 bg-surface px-3 py-2 font-mono text-xs font-semibold text-ink-900 shadow-2xs">
            <span className="break-all">{targetWallet}</span>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleDownload} className="space-y-4">
          {/* Statutory Selector */}
          <div>
            <label className="block text-xs font-bold text-ink-800">
              Statutory Legal Framework
            </label>
            <div className="mt-1.5 grid grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={() => setParams({ ...params, act_section: 'bnss_94' })}
                className={`flex items-center justify-between rounded-xl p-3 text-left transition-all border-2 ${
                  params.act_section === 'bnss_94'
                    ? 'border-brand-600 bg-brand-50/70 shadow-2xs'
                    : 'border-ink-200 bg-surface hover:border-ink-300'
                }`}
              >
                <div>
                  <p
                    className={`text-xs font-bold ${
                      params.act_section === 'bnss_94' ? 'text-brand-900' : 'text-ink-800'
                    }`}
                  >
                    Section 94 BNSS (2023)
                  </p>
                  <p className="text-[10px] text-ink-500">Bharatiya Nagarik Suraksha</p>
                </div>
                {params.act_section === 'bnss_94' && (
                  <CheckCircle2 className="h-4 w-4 text-brand-600 shrink-0" />
                )}
              </button>

              <button
                type="button"
                onClick={() => setParams({ ...params, act_section: 'crpc_91' })}
                className={`flex items-center justify-between rounded-xl p-3 text-left transition-all border-2 ${
                  params.act_section === 'crpc_91'
                    ? 'border-brand-600 bg-brand-50/70 shadow-2xs'
                    : 'border-ink-200 bg-surface hover:border-ink-300'
                }`}
              >
                <div>
                  <p
                    className={`text-xs font-bold ${
                      params.act_section === 'crpc_91' ? 'text-brand-900' : 'text-ink-800'
                    }`}
                  >
                    Section 91 Cr.P.C. (1973)
                  </p>
                  <p className="text-[10px] text-ink-500">Code of Criminal Procedure</p>
                </div>
                {params.act_section === 'crpc_91' && (
                  <CheckCircle2 className="h-4 w-4 text-brand-600 shrink-0" />
                )}
              </button>
            </div>
          </div>

          {/* Officer Details */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-ink-800">
                Investigating Officer Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={params.officer_name}
                onChange={(e) => setParams({ ...params, officer_name: e.target.value })}
                placeholder="Enter officer name..."
                className="mt-1 w-full rounded-lg border border-ink-300 bg-surface p-2.5 text-xs text-ink-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-ink-800">
                Rank / Designation <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={params.officer_designation}
                onChange={(e) => setParams({ ...params, officer_designation: e.target.value })}
                placeholder="e.g. Inspector of Police / IO"
                className="mt-1 w-full rounded-lg border border-ink-300 bg-surface p-2.5 text-xs text-ink-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-ink-800">
              Police Station / LEA Unit <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              value={params.police_station}
              onChange={(e) => setParams({ ...params, police_station: e.target.value })}
              placeholder="e.g. Cyber Crime Police Station, Cyberabad"
              className="mt-1 w-full rounded-lg border border-ink-300 bg-surface p-2.5 text-xs text-ink-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-ink-800">
                FIR / Crime / NCRP Number
              </label>
              <input
                type="text"
                value={params.fir_number}
                onChange={(e) => setParams({ ...params, fir_number: e.target.value })}
                placeholder="e.g. FIR No. 104/2026"
                className="mt-1 w-full rounded-lg border border-ink-300 bg-surface p-2.5 text-xs text-ink-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-ink-800">
                Complainant / Victim Name
              </label>
              <input
                type="text"
                value={params.victim_name}
                onChange={(e) => setParams({ ...params, victim_name: e.target.value })}
                placeholder="Optional / Confidential"
                className="mt-1 w-full rounded-lg border border-ink-300 bg-surface p-2.5 text-xs text-ink-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center justify-end gap-2 pt-3 border-t border-ink-100">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-3.5 py-2 text-xs font-bold text-ink-600 hover:bg-ink-100 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={async () => {
                if (!params.officer_name.trim() || !params.police_station.trim()) {
                  toast.error('Please fill in Officer Name and Police Station')
                  return
                }
                setLoading(true)
                try {
                  await downloadEvidencePackage(caseDetail.id, params)
                  toast.success('Complete Evidence Package (.ZIP) downloaded!')
                  onClose()
                } catch {
                  toast.error('Failed to generate ZIP package')
                } finally {
                  setLoading(false)
                }
              }}
              className="inline-flex items-center gap-1.5 rounded-xl border border-brand-200 bg-brand-50 px-4 py-2 text-xs font-bold text-brand-700 shadow-2xs hover:bg-brand-100 disabled:opacity-50 transition-all cursor-pointer"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Archive className="h-4 w-4 text-brand-600" />}
              Evidence Package (.ZIP)
            </button>

            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-brand-700 disabled:opacity-50 transition-all cursor-pointer"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              Legal Notice (PDF)
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
