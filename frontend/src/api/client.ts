import axios from 'axios'
import type { AnalyticsOverview, AuditEvent, CaseDetail, CaseFilters, CaseSummary, Chain } from '../types'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const api = axios.create({ baseURL })

export interface TraceRequestBody {
  address: string
  chain: Chain
  complaint_ref?: string
}

export async function submitTrace(body: TraceRequestBody) {
  const { data } = await api.post<{ case_id: string; status: string }>('/trace', body)
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

export async function getCase(caseId: string) {
  const { data } = await api.get<CaseDetail>(`/cases/${caseId}`)
  return data
}

export async function getIntegrationLog(caseId: string) {
  const { data } = await api.get<AuditEvent[]>(`/integrations/log/${caseId}`)
  return data
}

export function reportUrl(caseId: string) {
  return `${baseURL}/cases/${caseId}/report`
}
