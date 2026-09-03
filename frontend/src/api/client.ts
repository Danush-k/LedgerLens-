import axios from 'axios'
import { clearStoredAuth, getStoredToken } from '../auth/AuthContext'
import type {
  AnalyticsOverview,
  AuditEvent,
  BulkUploadResult,
  CaseDetail,
  CaseFilters,
  CaseSummary,
  Chain,
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

export async function parseComplaintText(text: string) {
  const { data } = await api.post<ParsedComplaintResult>('/trace/parse-complaint', { text })
  return data
}

export async function listCases(filters: CaseFilters = {}) {
  const { data } = await api.get<CaseSummary[]>('/cases', { params: filters })
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

