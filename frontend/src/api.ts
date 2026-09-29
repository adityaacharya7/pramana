export type Role = 'IO' | 'ANALYST' | 'SUPERVISOR' | 'AUDITOR' | 'ADMIN' | 'TRAINEE'
export type Build = 'standard' | 'demo'

export interface User {
  id: string
  username: string
  name: string
  role: Role
  role_label: string
  unit: string
}

export interface Session {
  access_token: string
  expires_at: string
  user: User
}

export interface Me {
  user: User
  permissions: string[]
  build: Build
}

export interface CaseSummary {
  id: string
  fir_no: string
  unit: string
  city: string | null
  status: string
  title: string
  station: string | null
  registered_on: string | null
  complainant: string | null
  my_access: 'owner' | 'member' | 'unit'
  evidence_count: number
}

export interface CaseDetail extends CaseSummary {
  members: { username: string; name: string; role: Role; access: string }[]
}

export type Integrity = 'OK' | 'MISMATCH' | 'MISSING'

export interface Evidence {
  id: string
  case_id: string
  filename: string
  type: 'CSV' | 'TXT' | 'PDF'
  kind: string
  sha256: string
  size_bytes: number
  uploaded_by: string
  uploaded_by_name: string
  uploaded_at: string
  integrity_status: Integrity
  last_verified_at: string | null
  source_group_id: string
  duplicate_of: string | null
}

export interface VerifyResult {
  evidence_id: string
  filename: string
  expected_sha256: string
  actual_sha256: string | null
  status: Integrity
  verified_at: string
}

export interface LedgerEntry {
  seq: number
  ts: string
  actor: string
  action: string
  case_id: string | null
  payload: Record<string, unknown>
  hash: string
  prev_hash: string
}

export interface LedgerReport {
  ok: boolean
  entries: number
  first_bad_seq: number | null
  reason: string | null
  head_seq: number
  head_hash: string
  checked_against: string
  latest_trusted_checkpoint: unknown
  limitation: string
}

export interface Snippet {
  before: string
  match: string
  after: string
}

export interface PendingGroup {
  entity_type: string
  value: string
  extractor: string
  extraction_ids: string[]
  spans: [number, number][]
  sample_id: string
  count: number
  snippet: Snippet | null
}

export interface ReviewFile {
  evidence_id: string
  filename: string
  kind: string
  type: string
  integrity_status: Integrity
  extracted: boolean
  extractors: string[]
  counts: { PENDING: number; CONFIRMED: number; REJECTED: number }
  pending_groups: PendingGroup[]
}

export interface QualityIssue {
  id: string
  check: string
  label: string
  file_ids: string[]
  detail: Record<string, unknown>
  status: 'OPEN' | 'ACKNOWLEDGED'
  resolution: { reason?: string; date_order?: string } | null
  decided_at: string | null
}

export interface EntitySource {
  evidence_id: string
  filename: string
  case_id: string
  kind: string
  span: [number, number]
  snippet: Snippet | null
}

export interface EntityCard {
  entity_id: string
  type: string
  name: string
  attrs: Record<string, unknown>
  cases: string[]
  sources: EntitySource[]
}

export interface IdentityCandidate {
  id: string
  a: string
  b: string
  name_similarity: number
  shared: { type: string; value: string }[]
  conflicting: { type: string; a: string[]; b: string[] }[]
  suggestion: 'merge_suggested' | 'likely_different' | 'insufficient_identifiers'
  identifiers: Record<string, [string, string][]>
  decision: { decision: string; reason: string; decided_at: string } | null
  a_card: EntityCard
  b_card: EntityCard
}

export interface ReviewQueue {
  case_id: string
  files: ReviewFile[]
  quality_issues: QualityIssue[]
  identity_candidates: IdentityCandidate[]
  totals: {
    pending_extractions: number
    files_not_extracted: number
    open_quality_issues: number
    undecided_identity_candidates: number
  }
}

export interface ExtractSummary {
  files_processed: string[]
  files_blocked: string[]
  extractions_created: number
  by_type: Record<string, number>
  quality_issues_open: number
}

export interface GraphNode {
  id: string
  type: string
  label: string
  attrs: Record<string, unknown>
  merged_ids: string[]
  mentions: number
  other_cases: string[]
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
  edge_ids: string[]
  independent_sources: number
  supports: number
}

export interface CaseGraph {
  case_id: string
  focus: string | null
  hops: number | null
  nodes: GraphNode[]
  edges: GraphEdge[]
  truncated: boolean
}

export interface EntityDetail {
  id: string
  type: string
  label: string
  records: { id: string; type: string; value: string; attrs: Record<string, unknown> }[]
  cases: string[]
  mentions: (EntitySource & { extraction_id: string; text: string; extractor: string })[]
  mention_total: number
  document_file: { evidence_id: string; filename: string } | null
}

export interface EdgeSupport {
  supports: (EntitySource & { edge_id: string; type: string; source_group: string; support_kind: string })[]
  independent_sources: number
}

export interface TimelineEvent {
  id: string
  ts: string
  kind: 'transfer' | 'cash' | 'charge' | 'call' | 'sms'
  from: string
  to: string
  amount: number | null
  channel: string | null
  reference: string | null
  description: string | null
  ts_ambiguous: boolean
  names: string[]
  sources: { evidence_id: string; filename: string; span: [number, number]; row: number | null }[]
}

export type EvidenceContent =
  | { kind: 'text'; text: string; sha256: string }
  | { kind: 'pdf'; url: string; sha256: string }

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const BASE = import.meta.env.VITE_API_BASE ?? '/api'
const TOKEN_KEY = 'pramana.session'

let token: string | null = readToken()
let unauthorizedHandler: (() => void) | null = null

function readToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(value: string | null) {
  token = value
  try {
    if (value) sessionStorage.setItem(TOKEN_KEY, value)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // Storage can be unavailable (private mode); the in-memory token still works.
  }
}

export const hasToken = () => token !== null

export function onUnauthorized(handler: () => void) {
  unauthorizedHandler = handler
}

export async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const res = await fetch(BASE + path, { ...init, headers })
  if (res.status === 401 && token) {
    setToken(null)
    unauthorizedHandler?.()
  }
  if (!res.ok) {
    let detail: unknown = null
    try {
      detail = (await res.json()).detail
    } catch {
      // not JSON
    }
    if (typeof detail !== 'string' && res.status === 413) {
      // Rejected by the host before reaching the API (Vercel caps request bodies at 4.5 MB).
      detail = 'File too large for this deployment. Split it, or upload it on a local or Docker build.'
    }
    throw new ApiError(res.status, typeof detail === 'string' ? detail : `Request failed (${res.status})`)
  }
  return res
}

export async function json<T>(path: string, init?: RequestInit): Promise<T> {
  return (await send(path, init)).json() as Promise<T>
}

export const post = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  health: () => json<{ status: string; build: Build; version: string }>('/health'),
  login: (username: string, password: string, totp: string) =>
    json<Session>('/auth/login', post({ username, password, totp })),
  demoUsers: () => json<User[]>('/demo/users'),
  demoSession: (username: string) => json<Session>('/demo/session', post({ username })),
  me: () => json<Me>('/auth/me'),
  cases: () => json<CaseSummary[]>('/cases'),
  createCase: (data: { fir_no: string; title: string; complainant: string; city: string; unit: string; station?: string }) =>
    json<CaseDetail>('/cases', post(data)),
  case: (id: string) => json<CaseDetail>(`/cases/${encodeURIComponent(id)}`),
  evidence: (caseId: string) => json<Evidence[]>(`/cases/${encodeURIComponent(caseId)}/evidence`),
  upload: (caseId: string, file: File, kind: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('kind', kind)
    return json<Evidence>(`/cases/${encodeURIComponent(caseId)}/evidence`, { method: 'POST', body: form })
  },
  verify: (evidenceId: string) => json<VerifyResult>(`/evidence/${evidenceId}/verify`),
  content: async (ev: Evidence): Promise<EvidenceContent> => {
    const res = await send(`/evidence/${ev.id}/content`)
    const sha256 = res.headers.get('X-Evidence-SHA256') ?? ''
    if (ev.type === 'PDF') return { kind: 'pdf', url: URL.createObjectURL(await res.blob()), sha256 }
    return { kind: 'text', text: await res.text(), sha256 }
  },
  evidenceText: async (evidenceId: string) => (await send(`/evidence/${evidenceId}/text`)).text(),
  extract: (caseId: string) => json<ExtractSummary>(`/cases/${encodeURIComponent(caseId)}/extract`, post({})),
  reviewQueue: (caseId: string) => json<ReviewQueue>(`/cases/${encodeURIComponent(caseId)}/review-queue`),
  decideExtraction: (
    id: string,
    decision: 'confirm' | 'reject',
    scope: 'mention' | 'value' | 'file',
    extractors?: string[],
  ) => json<{ decided: number }>(`/extractions/${id}/decision`, post({ decision, scope, extractors })),
  decideIdentity: (caseId: string, a: string, b: string, decision: string, reason: string) =>
    json(`/identities/decision`, post({ case_id: caseId, entity_a: a, entity_b: b, decision, reason })),
  decideQuality: (id: string, reason: string, dateOrder?: 'DMY' | 'MDY') =>
    json(`/quality-issues/${id}/decision`, post({ reason, date_order: dateOrder })),
  graph: (caseId: string, focus?: string | null, hops?: number, documents = true) => {
    const q = new URLSearchParams({ documents: String(documents) })
    if (focus) {
      q.set('focus', focus)
      q.set('hops', String(hops ?? 1))
    }
    return json<CaseGraph>(`/cases/${encodeURIComponent(caseId)}/graph?${q}`)
  },
  timeline: (caseId: string, focus?: string | null) =>
    json<TimelineEvent[]>(`/cases/${encodeURIComponent(caseId)}/timeline${focus ? `?focus=${focus}` : ''}`),
  entity: (id: string, caseId: string) => json<EntityDetail>(`/entities/${id}?case_id=${encodeURIComponent(caseId)}`),
  edgeSupport: (edgeIds: string[], caseId: string) =>
    json<EdgeSupport>(`/edges/support?ids=${edgeIds.join(',')}&case_id=${encodeURIComponent(caseId)}`),
  ledger: (limit = 300) => json<LedgerEntry[]>(`/ledger?limit=${limit}`),
  verifyLedger: () => json<LedgerReport>('/ledger/verify'),
  ai: {
    status: () => json<{ status: string; provider: string; active_models: string[]; capabilities: string[] }>('/ai/status'),
    chat: (message: string, caseId?: string, history?: { role: string; content: string }[]) =>
      json<{ reply: string; case_id?: string; officer: string; timestamp: string }>('/ai/chat', post({ message, case_id: caseId, history })),
    analyzeCase: (caseId: string) =>
      json<{ case_id: string; analysis: any; analyzed_at: string }>('/ai/case-analysis', post({ case_id: caseId })),
    draftNotice: (data: { case_id: string; notice_type: string; entity_name: string; entity_identifier: string; amount?: string; utr?: string; ifsc?: string }) =>
      json<{ case_id: string; notice_type: string; target: string; notice_text: string; drafted_at: string }>('/ai/draft-notice', post(data)),
  },
}

export async function sha256Hex(file: Blob): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer())
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}
