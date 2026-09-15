import axios from 'axios'
import { clearStoredAuth, getStoredToken } from '../auth/AuthContext'
import type {
  AddressFootprint,
  CaseLink,
  AuditChain,
  AnalyticsOverview,
  AuditEvent,
  BulkUploadResult,
  CaseDetail,
  CaseFilters,
  CaseSummary,
  Chain,
  ConvergenceResult,
  EntityResult,
  HashVerificationResult,
  LegalNoticeParams,
  MlStatus,
  ParsedComplaintResult,
} from '../types'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Bound every request so an unreachable/hung API fails predictably instead of
// spinning for however long the OS takes to give up on the TCP connection.
export const api = axios.create({ baseURL, timeout: 15_000 })

api.interceptors.request.use((config) => {
  const token = getStoredToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLoginCall = error.config?.url?.includes('/auth/login')
    if (error.response?.status === 401 && !isLoginCall) {
      clearStoredAuth()
      if (window.location.pathname !== '/login') window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export interface TraceRequestBody {
  address: string
  chain: Chain
  complaint_ref?: string
  narrative?: string
}

export async function submitTrace(body: TraceRequestBody) {
  const { data } = await api.post<{ case_id: string; status: string }>('/trace', body)
  return data
}

export async function submitBulkTrace(file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<BulkUploadResult>('/trace/bulk', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function parseComplaintDocument(file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<ParsedComplaintResult & {
    source_filename?: string
    extracted_text?: string
  }>('/trace/parse-document', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    // Reading a large PDF takes longer than a JSON round trip.
    timeout: 60_000,
  })
  return data
}

export async function parseComplaintText(text: string) {
  const { data } = await api.post<ParsedComplaintResult>('/trace/parse-complaint', { text })
  return data
}

export async function listCases(filters: CaseFilters = {}) {
  const { data } = await api.get<CaseSummary[]>('/cases', { params: filters })
  return data
}

export async function getCaseLinks(caseId: string) {
  const { data } = await api.get<CaseLink[]>(`/cases/${caseId}/links`)
  return data
}

export async function getRelatedCases(caseId: string) {
  const { data } = await api.get<CaseSummary[]>(`/cases/${caseId}/related`)
  return data
}

export async function getAnalyticsOverview() {
  const { data } = await api.get<AnalyticsOverview>('/analytics/overview')
  return data
}

export async function getMlStatus() {
  const { data } = await api.get<MlStatus>('/analytics/ml-status')
  return data
}

export async function getCase(caseId: string) {
  const { data } = await api.get<CaseDetail>(`/cases/${caseId}`)
  return data
}

export async function getIntegrationLog(caseId: string) {
  const { data } = await api.get<AuditEvent[]>(`/integrations/log/${caseId}`)
  return data
}

/** Plain <a href> can't carry the Authorization header, so the PDF report
 * is fetched as a blob and handed to the browser as a download instead. */
export async function downloadReport(caseId: string) {
  const { data } = await api.get(`/cases/${caseId}/report`, { responseType: 'blob' })
  const url = window.URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = `case-${caseId}.pdf`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

/**
 * Turn a failed file download into a sentence worth reading.
 *
 * These endpoints answer with a Blob, so an error body arrives as a Blob
 * too and never reaches the usual `error.response.data.detail` path. Left
 * alone the caller can only say "it failed", which is what sent us auditing
 * a perfectly healthy endpoint while the real cause was the API not running
 * at all.
 */
export async function describeDownloadError(err: unknown): Promise<string> {
  const e = err as { response?: { status?: number; data?: unknown }; code?: string }

  if (e.code === 'ERR_NETWORK') {
    return 'Cannot reach the API. Check that the backend is running.'
  }
  if (e.code === 'ECONNABORTED') {
    return 'The request timed out before the document was ready.'
  }

  const data = e.response?.data
  if (data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text())
      if (parsed?.detail) return String(parsed.detail)
    } catch {
      // Not JSON - fall through to the status-based message below.
    }
  }
  if (e.response?.status) return `Server returned ${e.response.status}.`
  return 'Could not generate the document.'
}

export async function downloadLegalNotice(caseId: string, params: LegalNoticeParams) {
  const { data } = await api.get(`/cases/${caseId}/legal-notice`, {
    params,
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = `legal-notice-case-${caseId}.pdf`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export async function verifyEvidenceHash(hash: string, caseId?: string) {
  const { data } = await api.post<HashVerificationResult>('/cases/verify-hash', {
    hash,
    case_id: caseId || undefined,
  })
  return data
}


// ── Cross-case intelligence ───────────────────────────────────────────────

export async function getConvergence(minCases = 2, chain?: string) {
  const { data } = await api.get<ConvergenceResult>('/intel/convergence', {
    params: { min_cases: minCases, chain },
  })
  return data
}

export async function getEntities(chain?: string) {
  const { data } = await api.get<EntityResult>('/intel/entities', { params: { chain } })
  return data
}

export async function getAddressFootprint(chain: string, address: string) {
  const { data } = await api.get<AddressFootprint>(`/intel/address/${chain}/${address}`)
  return data
}

export async function getAuditChain(caseId: string) {
  const { data } = await api.get<AuditChain>(`/cases/${caseId}/audit`)
  return data
}
