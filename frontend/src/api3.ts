// Weeks 3-5: analysis, leads, Challenge Mode, drafts, handover, cross-case.
// Shapes follow the API; fields the UI does not read are left loose.
import { json, post, send, type LedgerReport } from './api'

export interface Support {
  kind: string
  label: string
  file_id: string
  case_id: string
  span: [number, number]
  source: string
  role: string
  note?: string
  event_id?: string
  filename?: string
  sha256?: string
}

export interface Receipt {
  key: string
  title: string
  rule: { id: string; version: string; params: Record<string, unknown> }
  observation: string
  subject: { kind: string; value: string; label: string }
  cases: string[]
  metrics: Record<string, unknown>
  supporting_records: Support[]
  independent_sources: number
  unknowns: string[]
  conflicts: string[]
  what_could_make_this_wrong: {
    contradictions: string[]
    ordinary_explanation: string
    records_that_would_distinguish: string[]
    independent_sources: number
    note: string
  }
  next_verification_step: string
}

export interface LeadSummary {
  id: string
  key: string
  rule_id: string
  title: string
  observation: string
  status: string
  active: boolean
  case_ids: string[]
  analysis_cases: string[]
  subject: { kind: string; value: string; label: string } | null
  metrics: Record<string, unknown> | null
  independent_sources: number | null
  pending: { status: string; reason: string; by: string | null } | null
  updated_at: string | null
}

export interface Draft {
  id: string
  set_id: string
  account_id: string
  method: string
  amount: number
  estimate_min: number
  estimate_max: number
  as_of: string | null
  assumptions: string[]
  notes: string[]
  draft_text: string
  status: string
  stale: boolean
  stale_reason: string | null
  created_by: string | null
  created_at: string | null
  approved_by: string | null
  approved_at: string | null
}

export interface DiffItem {
  key: string
  title: string
  subject: string
  summary?: string
  rule?: string
  why?: string
  before?: { summary: string; metrics: Record<string, unknown>; independent_sources: number }
  after?: { summary: string; metrics: Record<string, unknown>; independent_sources: number }
}

export interface Dependent {
  key: string
  title: string
  subject: string
  independent_sources: number
  single_source: boolean
}

export interface Operation {
  op: 'exclude_source' | 'dispute_txn' | 'simulate_no_txn'
  source?: string
  event_id?: string
}

export interface Scenario {
  id: string
  lead_id: string
  case_ids: string[]
  operations: Operation[]
  status: 'sandbox' | 'proposed' | 'applied' | 'rejected'
  reconciles: boolean
  diff: {
    removed: DiffItem[]
    added: DiffItem[]
    changed: DiffItem[]
    estimates: { party: string; before: Record<string, number>; after: Record<string, number>; uncertain_after: boolean }[]
    affected_drafts: { draft_id: string; account_id: string; status: string; lead: string; amount: number; why: string }[]
    dependencies: { source: string; findings: Dependent[] }[]
    reconciles_before: boolean
    reconciles_after: boolean
  }
  created_at: string
  proposed_by: string | null
  approved_by: string | null
  proposal_reason: string | null
  decision_reason: string | null
  decided_at: string | null
}

export interface SourceGroup {
  source: string
  records: { kind: string; label: string; file_id: string; case_id: string; span: [number, number] }[]
  events: string[]
  dependents: Dependent[]
}

export interface LeadDetail extends LeadSummary {
  receipt: Receipt | null
  reproduced_now: boolean
  drafts: Draft[]
  scenarios: Scenario[]
  history: { seq: number; ts: string; actor: string; action: string }[]
  sources: SourceGroup[]
  filenames: Record<string, string>
  operations_applied: Operation[]
}

export interface TrailMethod {
  method: string
  method_text: string
  seeds: { event: string; case_id: string; victim: string; to: string; amount: number; ts: string }[]
  flows: { event: string; from: string; to: string; tag: string; amount: number; layer: number; ts: string; exit: string | null }[]
  holdings: { party: string; tag: string; amount: number; as_of: string | null; has_statement: boolean; layer: number; uncertain: boolean }[]
  exits: { event: string; party: string; to: string; tag: string; amount: number; kind: string; ts: string; uncertain: boolean }[]
  issues: { party: string; kind: string; detail: string; amount?: number; computed?: number; stated?: number }[]
  reconciles: boolean
  by_case: Record<string, { loss: number; held: number; exited: number; missing_statement: number }>
  missing_statements: string[]
  total_loss: number
}

export type Method = 'fifo' | 'lifo' | 'prorata'

export interface MoneyTrail {
  cases: string[]
  trail: { methods: Record<Method, TrailMethod>; spread: Record<string, Record<string, number>> }
  labels: Record<string, string>
  method_text: Record<string, string>
  reconciles: boolean
  note: string
}

export interface MatchRow {
  entity_id: string
  type: string
  value: string
  names_seen: string[]
  visible_cases: { id: string; title: string; unit: string }[]
  hidden: { unit: string; token: string; request_status: string | null }[]
  total_cases: number
  likely_hub: boolean
}

export interface Passage {
  attribute: string
  value: string
  text: string
  context: string
}

export interface MoProposal {
  case_id: string
  score: number
  attribute_cosine: number
  text_cosine: number
  matching_attribute_types: string[]
  shared: string[]
  proposed: boolean
  this_file: { evidence_id: string; filename: string }
  other_file: { evidence_id: string; filename: string }
  this_passages: Passage[]
  other_passages: Passage[]
}

export interface AccessRequestRow {
  id: string
  status: string
  reason: string
  created_at: string
  decided_at: string | null
  decided_by: string | null
  requester: { username: string; name: string; unit: string }
  unit: string
  case_id: string | null
  case_title: string | null
}

export interface BundleReport {
  ok: boolean
  checks: { check: string; ok: boolean; detail: string }[]
  lead?: string
}

async function download(path: string, fallbackName: string) {
  const res = await send(path)
  const blob = await res.blob()
  const cd = res.headers.get('Content-Disposition') ?? ''
  const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? fallbackName
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

const enc = encodeURIComponent

export const api3 = {
  analysisScope: (caseId: string) =>
    json<{ suggested: string[]; available: { id: string; title: string; city: string }[]; open_quality_issues: { case_id: string; check: string }[] }>(
      `/cases/${enc(caseId)}/analysis-scope`,
    ),
  runAnalysis: (caseIds: string[]) =>
    json<{ created: number; updated: number; no_longer_produced: number; by_rule: Record<string, number>; reconciles: boolean }>(
      '/analysis/run',
      post({ case_ids: caseIds }),
    ),
  caseLeads: (caseId: string) => json<LeadSummary[]>(`/cases/${enc(caseId)}/leads`),
  lead: (id: string) => json<LeadDetail>(`/leads/${id}`),
  transition: (id: string, action: 'propose' | 'approve' | 'reject', reason: string, to?: string) =>
    json<{ result: string; status: string }>(`/leads/${id}/transition`, post({ action, to, reason })),
  challenge: (id: string, operations: Operation[]) => json<Scenario>(`/leads/${id}/challenge`, post({ operations })),
  scenarioAction: (id: string, action: 'propose' | 'approve' | 'reject', reason: string) =>
    json<Scenario>(`/scenarios/${id}/apply`, post({ action, reason })),
  createDrafts: (id: string, method: Method) =>
    json<{ total: number; attributable_under_method: number; within_attributable: boolean }>(`/leads/${id}/action-drafts`, post({ method })),
  approveDraft: (id: string, reason: string) => json<Draft>(`/action-drafts/${id}/approve`, post({ reason })),
  moneyTrail: (caseId: string, cases: string[]) =>
    json<MoneyTrail>(`/cases/${enc(caseId)}/money-trail?cases=${cases.map(enc).join(',')}`),
  matches: (caseId: string) => json<{ matches: MatchRow[] }>(`/cases/${enc(caseId)}/matches`),
  moMatches: (caseId: string) =>
    json<{ method: string; note: string; attributes?: Record<string, string[]>; proposals: MoProposal[] }>(`/cases/${enc(caseId)}/mo-matches`),
  accessRequests: () => json<{ mine: AccessRequestRow[]; to_decide: AccessRequestRow[] }>('/access-requests'),
  requestAccess: (token: string, reason: string) => json<AccessRequestRow>('/access-requests', post({ token, reason })),
  decideAccess: (id: string, decision: 'approve' | 'reject', reason: string) =>
    json<AccessRequestRow>(`/access-requests/${id}/decision`, post({ decision, reason })),
  exportJson: (id: string) => download(`/leads/${id}/export`, 'pramana-handover.json'),
  exportPdf: (id: string) => download(`/leads/${id}/export.pdf`, 'pramana-handover.pdf'),
  verifyBundle: (bundle: unknown) => json<BundleReport>('/bundles/verify', post(bundle)),
  checkpoint: () => json<{ checkpoint: Record<string, unknown> | null; trusted_public_key: string }>('/ledger/checkpoint'),
  verifyWithCheckpoint: (checkpoint: unknown) => json<LedgerReport>('/ledger/verify', post(checkpoint)),
}

export const STATUS_LABELS: Record<string, string> = {
  DETECTED: 'Detected',
  UNDER_VERIFICATION: 'Under verification',
  VERIFIED: 'Verified',
  DISMISSED: 'Dismissed',
  NEEDS_EVIDENCE: 'Needs evidence',
}

export const NEXT_STATUSES: Record<string, string[]> = {
  DETECTED: ['UNDER_VERIFICATION', 'DISMISSED'],
  UNDER_VERIFICATION: ['VERIFIED', 'DISMISSED', 'NEEDS_EVIDENCE'],
  NEEDS_EVIDENCE: ['UNDER_VERIFICATION', 'DISMISSED'],
  VERIFIED: ['UNDER_VERIFICATION'],
  DISMISSED: ['UNDER_VERIFICATION'],
}
