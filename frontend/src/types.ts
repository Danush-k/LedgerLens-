export type Chain = 'ethereum' | 'bsc' | 'polygon' | 'bitcoin' | 'tron'

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
  label_source?: string | null
  hop: number
  /** The specific transfer that pulled this wallet into the investigation. */
  why_included?: string
  provenance?: {
    from_address: string
    tx_hash: string
    value: number
    timestamp: number
    hop: number
  } | null
  /** Victim funds attributable to this wallet (haircut method). */
  tainted_value?: number
  /** Share of value arriving here that is the victim's, 0-1. */
  taint_ratio?: number
  /** Reached by live monitoring after the original trace completed. */
  detected_live?: boolean
  first_seen_at?: string
}

export interface GraphEdge {
  source: string
  target: string
  tx_hash: string
  value: number
  timestamp: number
  hop: number
  tainted_value?: number
  /** Observed by live monitoring after the original trace completed. */
  detected_live?: boolean
  first_seen_at?: string
}

/** Evidence-backed finding from the pattern detectors. */
export interface Pattern {
  pattern: string
  severity: 'high' | 'medium' | 'low'
  title: string
  evidence: string
  transactions: string[]
  addresses: string[]
  flag: string | null
}

export interface NearestExchange {
  name: string
  address: string
  chain: string
  hops: number
  /** Where the attribution comes from, so it can be challenged. */
  source?: string | null
}

export interface WalletCluster {
  type: 'common_input' | 'shared_funder'
  addresses: string[]
  note: string
}

export interface CaseSummary {
  id: string
  reported_address: string
  chain: Chain
  status: CaseStatus
  hop_progress?: number
  hop_limit?: number
  risk_score: number | null
  nearest_exchange: NearestExchange | null
  fraud_typology: string | null
  created_at: string
  live_watch?: boolean
  live_event_count?: number
  live_last_event_at?: string | null
}

export interface CaseDetail extends CaseSummary {
  complaint_ref: string | null
  narrative: string | null
  created_by: string | null
  hop_progress: number
  hop_limit: number
  /** The worker's own description of the current step, e.g. "Reading hop 2 of 5". */
  status_message?: string | null
  /** Heartbeat: when the worker last reported. Absent means it never did. */
  last_progress_at?: string | null
  risk_score_ml: number | null
  risk_breakdown: Record<string, number> | null
  flags: string[] | null
  clusters: WalletCluster[] | null
  patterns: Pattern[] | null
  error: string | null
  typology_confidence: number | null
  recommended_action: string | null
  graph: { nodes: GraphNode[]; edges: GraphEdge[] } | null
  completed_at: string | null
  live_checked_at?: string | null
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
  typology_counts: Record<string, number>
  top_exchanges: { name: string; count: number }[]
  recent_high_risk: CaseSummary[]
}

export interface MlStatus {
  trained: boolean
  trained_on: number
  min_required: number
  reason_unavailable: string | null
}

export interface BulkUploadResult {
  accepted: { row: number; case_id: string; address: string }[]
  rejected: { row: number; reason: string }[]
}

export interface CaseFilters {
  chain?: string
  status?: string
  min_risk?: number
  search?: string
}

export interface ParsedWallet {
  address: string
  chain: Chain | 'tron'
  format: string
  confidence: number
}

export interface ParsedComplaintResult {
  wallets: ParsedWallet[]
  tx_hashes: string[]
  upi_ids: string[]
  amounts: string[]
  complaint_refs: string[]
  suggested_chain: Chain
  extracted_count: number
}

export interface LegalNoticeParams {
  officer_name: string
  officer_designation: string
  police_station: string
  fir_number?: string
  fir_date?: string
  victim_name?: string
  act_section: 'bnss_94' | 'crpc_91'
}

export interface HashVerificationResult {
  verified: boolean
  case_id?: string
  reported_address?: string
  chain?: string
  risk_score?: number
  created_at?: string
  computed_hash?: string
  submitted_hash: string
  status: string
  message?: string
}



// ── Cross-case intelligence ───────────────────────────────────────────────

export interface ConvergenceCase {
  case_id: string
  complaint_ref: string | null
  reported_address: string
  fraud_typology: string | null
  risk_score: number | null
  status: CaseStatus
  created_at: string
  hop: number
  value_in: number
}

export interface ConvergencePoint {
  chain: string
  address: string
  case_count: number
  total_value: number
  min_hop: number
  node_type: string | null
  label_name: string | null
  cases: ConvergenceCase[]
  evidence: string
}

export interface ConvergenceResult {
  min_cases: number
  count: number
  convergence_points: ConvergencePoint[]
  note: string
}

export interface Entity {
  entity_id: string
  chain: string
  address_count: number
  addresses: string[]
  case_count: number
  case_ids: string[]
  complaint_refs: string[]
  tainted_value: number
  labels: string[]
  possible_associates: string[]
  evidence: string
  /** Clusters too large to be one person - almost always an exchange. */
  likely_service: boolean
}

export interface EntityResult {
  count: number
  entities: Entity[]
  note: string
}

export interface AddressFootprint {
  chain: string
  address: string
  case_count: number
  total_value: number
  min_hop: number
  node_type: string | null
  label_name: string | null
  reported_directly: boolean
  cases: ConvergenceCase[]
}


// ── Tamper-evident audit chain ────────────────────────────────────────────

export interface AuditChainEntry {
  sequence: number
  event: string
  detail: string | null
  simulated: boolean
  created_at: string
  entry_hash: string | null
  prev_hash: string | null
}

export interface AuditChainVerification {
  case_id: string
  intact: boolean
  entry_count: number
  chain_head: string | null
  first_broken_sequence: number | null
  reason: string | null
}

export interface AuditChain {
  verification: AuditChainVerification
  entries: AuditChainEntry[]
}


/**
 * One other case connected to this one, and the wallet that connects them.
 *
 * `same_wallet` means the identical address was reported again - the
 * strongest link available. `shared_wallet` means the two traces pass
 * through a wallet in common: corroboration from a separate victim, but not
 * proof that one person controls both.
 */
export interface CaseLink {
  case_id: string
  complaint_ref: string | null
  reported_address: string
  risk_score: number | null
  status: CaseStatus
  created_at: string
  relationship: 'same_wallet' | 'shared_wallet'
  shared_addresses: string[]
}


// ── Suspects ──────────────────────────────────────────────────────────────

export type SuspectPriority = 'high' | 'medium' | 'low'
export type SuspectStatus = 'pending' | 'confirmed' | 'dismissed'
export type SuspectRole =
  | 'reported'
  | 'cashout'
  | 'holding'
  | 'collector'
  | 'distributor'
  | 'relay'
  | 'mixer_user'
  | 'untraced'
  | 'recipient'

export interface EvidenceTx {
  tx_hash: string
  value: number
  timestamp: number | null
  tainted_value?: number | null
}

/** One named reason a wallet is on the list, with the transactions it rests on. */
export interface SuspectReason {
  code: string
  weight: number
  text: string
  /** `caveat` reasons weaken the case and subtract from the score. */
  kind: 'signal' | 'caveat'
  transactions: EvidenceTx[]
}

export interface SuspectDecision {
  status: SuspectStatus
  note: string | null
  decided_by: string | null
  decided_at: string | null
}

export interface Suspect {
  id: string
  rank: number
  address: string
  chain: string
  hop: number
  node_type: string | null
  label_name: string | null
  score: number
  priority: SuspectPriority
  role: SuspectRole
  role_title: string
  role_description: string
  victim_funds: number
  victim_share: number
  received: number
  sent: number
  unit: string
  exchange_name: string | null
  linked_cases: { case_id: string; complaint_ref: string | null; reported_address: string }[]
  same_owner_as: string[]
  detected_live: boolean
  reasons: SuspectReason[]
  recommended_action: string
  first_activity: number | null
  last_activity: number | null
  decision: SuspectDecision
}

export type NextStepAction =
  | 'legal_notice'
  | 'filter_holding'
  | 'review_suspects'
  | 'suspect_report'
  | 'linked_cases'
  | null

export interface NextStep {
  key: string
  priority: SuspectPriority
  action: NextStepAction
  title: string
  detail: string
}

export interface CaseBriefingSummary {
  headline: string
  unit: string
  chain: string
  victim_total: number
  to_exchanges: number
  exchange_names: string[]
  still_held: number
  holding_wallets: number
  beyond_depth: number
  to_mixers: number
  to_bridges: number
  counts: Record<'total' | 'high' | 'medium' | 'low' | 'confirmed' | 'dismissed' | 'pending', number>
  linked_case_count: number
  next_steps: NextStep[]
}

export interface SuspectsResult {
  ready: boolean
  reason: string | null
  summary: CaseBriefingSummary | null
  suspects: Suspect[]
}


// ── Live monitoring ───────────────────────────────────────────────────────

export interface LiveTransfer {
  tx_hash: string
  chain: string
  from_address: string
  to_address: string
  value: number
  timestamp: number
  hop: number
  to_node_type: string | null
  to_label_name: string | null
  detected_at: string
}

export interface LiveCheck {
  checked_at: string
  addresses_checked: number
  errors: { address: string; error: string }[]
  new_count: number
}
