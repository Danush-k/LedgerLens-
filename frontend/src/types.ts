export type Chain = 'ethereum' | 'bsc' | 'polygon' | 'bitcoin'

export type CaseStatus = 'queued' | 'tracing' | 'complete' | 'failed'

export type NodeType =
  | 'reported'
  | 'intermediate'
  | 'exchange'
  | 'mixer'
  | 'bridge'
  | 'unresolved'

export interface GraphNode {
  id: string
  address: string
  chain: string
  node_type: NodeType
  label_name: string | null
}

export interface GraphEdge {
  source: string
  target: string
  tx_hash: string
  value: number
  timestamp: number
  hop: number
}

export interface NearestExchange {
  name: string
  address: string
  chain: string
  hops: number
}

export interface CaseSummary {
  id: string
  reported_address: string
  chain: Chain
  status: CaseStatus
  risk_score: number | null
  nearest_exchange: NearestExchange | null
  created_at: string
}

export interface CaseDetail extends CaseSummary {
  complaint_ref: string | null
  hop_progress: number
  hop_limit: number
  risk_score_ml: number | null
  risk_breakdown: Record<string, number> | null
  flags: string[] | null
  recommended_action: string | null
  graph: { nodes: GraphNode[]; edges: GraphEdge[] } | null
  completed_at: string | null
}

export interface AuditEvent {
  event: string
  detail: string | null
  simulated: boolean
  created_at: string
}

export interface AnalyticsOverview {
  total_cases: number
  by_status: Record<string, number>
  by_chain: Record<string, number>
  risk_buckets: { low: number; medium: number; high: number }
  avg_risk_score: number | null
  exchange_found_count: number
  exchange_found_rate: number
  flag_counts: Record<string, number>
  top_exchanges: { name: string; count: number }[]
  recent_high_risk: CaseSummary[]
}

export interface CaseFilters {
  chain?: string
  status?: string
  min_risk?: number
  search?: string
}
