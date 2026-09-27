import { ChevronLeft, Eye, Lock, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, NavLink, useParams } from 'react-router-dom'
import { api, ApiError, type CaseDetail, type Evidence, type VerifyResult } from '../api'
import { useAuth } from '../auth'
import { AccessChip, ErrorNote, Hash, IntegrityBadge } from '../components/bits'
import EvidenceUpload from '../components/EvidenceUpload'
import EvidenceViewer from '../components/EvidenceViewer'
import CrossCaseTab from '../components/CrossCaseTab'
import GraphTab from '../components/GraphTab'
import LeadsTab from '../components/LeadsTab'
import MoneyTrailTab from '../components/MoneyTrailTab'
import ReviewTab from '../components/ReviewTab'
import { formatBytes, formatDate, formatDateTime, KIND_LABELS } from '../format'

// Workspaces that arrive in later weeks of the build plan. Listed so the
// shape of a case is visible, but not clickable until they exist.
type Tab = 'evidence' | 'review' | 'graph' | 'leads' | 'trail' | 'crosscase'
const TABS: Tab[] = ['evidence', 'review', 'graph', 'leads', 'trail', 'crosscase']

// Keyed by case id so switching cases starts from a clean state.
export default function CaseViewRoute() {
  const { caseId = '', tab } = useParams()
  const t: Tab = TABS.includes(tab as Tab) ? (tab as Tab) : 'evidence'
  return <CaseView key={caseId} caseId={caseId} tab={t} />
}

function CaseView({ caseId, tab }: { caseId: string; tab: Tab }) {
  const { can } = useAuth()
  const [kase, setCase] = useState<CaseDetail | null>(null)
  const [evidence, setEvidence] = useState<Evidence[] | null>(null)
  const [failure, setFailure] = useState<{ status: number; message: string } | null>(null)
  const [viewing, setViewing] = useState<Evidence | null>(null)
  const [verifying, setVerifying] = useState<string | null>(null)
  const [verified, setVerified] = useState<Record<string, VerifyResult>>({})
  const [actionError, setActionError] = useState<string | null>(null)

  const loadEvidence = useCallback(() => api.evidence(caseId).then(setEvidence), [caseId])

  useEffect(() => {
    api.case(caseId).then(
      (c) => {
        setCase(c)
        loadEvidence().catch((e) => setActionError(e.message))
      },
      (e) => setFailure({ status: e instanceof ApiError ? e.status : 0, message: e.message }),
    )
  }, [caseId, loadEvidence])

  async function verify(ev: Evidence) {
    setVerifying(ev.id)
    setActionError(null)
    try {
      const r = await api.verify(ev.id)
      setVerified((v) => ({ ...v, [ev.id]: r }))
      setEvidence((xs) => xs?.map((x) => (x.id === ev.id ? { ...x, integrity_status: r.status, last_verified_at: r.verified_at } : x)) ?? xs)
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Verification failed.')
    } finally {
      setVerifying(null)
    }
  }

  const closeViewer = useCallback(() => setViewing(null), [])
  const onBlocked = useCallback(() => {
    loadEvidence().catch(() => undefined)
  }, [loadEvidence])

  if (failure) {
    return (
      <div className="page">
        <BackLink />
        <div className="empty">
          <h2>{failure.status === 403 ? 'You do not have access to this case' : failure.status === 404 ? 'Case not found' : 'Could not open the case'}</h2>
          <p>{failure.status === 403 ? 'This attempt has been recorded in the audit log. Access to a case outside your scope needs an approved access request.' : failure.message}</p>
        </div>
      </div>
    )
  }
  if (!kase) return <div className="page muted">Loading case…</div>

  const canUpload = can('evidence.upload') && kase.my_access !== 'unit'
  const groups = new Map<string, number>()
  evidence?.forEach((e) => groups.set(e.source_group_id, (groups.get(e.source_group_id) ?? 0) + 1))
  const byId = new Map(evidence?.map((e) => [e.id, e]))

  return (
    <div className="page">
      <BackLink />
      <div className="case-head">
        <div>
          <div className="case-kicker">
            <span className="case-id">{kase.id}</span>
            <span className="muted">FIR {kase.fir_no}</span>
            <AccessChip access={kase.my_access} />
          </div>
          <h1>{kase.title}</h1>
          <dl className="facts">
            <div>
              <dt>Complainant</dt>
              <dd>{kase.complainant ?? '—'}</dd>
            </div>
            <div>
              <dt>Police station</dt>
              <dd>{kase.station ?? '—'}</dd>
            </div>
            <div>
              <dt>Registered</dt>
              <dd>{formatDate(kase.registered_on)}</dd>
            </div>
            <div>
              <dt>Owning unit</dt>
              <dd>{kase.unit}</dd>
            </div>
          </dl>
        </div>
        <div className="members">
          <h3>Case members</h3>
          <ul>
            {kase.members.map((m) => (
              <li key={m.username}>
                <span>{m.name}</span>
                <span className="muted small">
                  {m.role} · {m.access}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <nav className="tabs" aria-label="Case workspaces">
        <NavLink end to={`/cases/${kase.id}`} className={({ isActive }) => `tab${isActive ? ' tab-active' : ''}`}>
          Evidence <span className="tab-count">{evidence?.length ?? kase.evidence_count}</span>
        </NavLink>
        {can('review.read') && (
          <NavLink to={`/cases/${kase.id}/review`} className={({ isActive }) => `tab${isActive ? ' tab-active' : ''}`}>
            Review queue
          </NavLink>
        )}
        {can('graph.read') && (
          <NavLink to={`/cases/${kase.id}/graph`} className={({ isActive }) => `tab${isActive ? ' tab-active' : ''}`}>
            Graph &amp; timeline
          </NavLink>
        )}
        {can('lead.read') && (
          <NavLink to={`/cases/${kase.id}/leads`} className={({ isActive }) => `tab${isActive ? ' tab-active' : ''}`}>
            Leads
          </NavLink>
        )}
        {can('graph.read') && (
          <NavLink to={`/cases/${kase.id}/trail`} className={({ isActive }) => `tab${isActive ? ' tab-active' : ''}`}>
            Money trail
          </NavLink>
        )}
        {can('graph.read') && (
          <NavLink to={`/cases/${kase.id}/crosscase`} className={({ isActive }) => `tab${isActive ? ' tab-active' : ''}`}>
            Cross-case
          </NavLink>
        )}
      </nav>

      {tab === 'review' && <ReviewTab caseId={kase.id} />}
      {tab === 'graph' && <GraphTab caseId={kase.id} />}
      {tab === 'leads' && <LeadsTab caseId={kase.id} />}
      {tab === 'trail' && <MoneyTrailTab caseId={kase.id} />}
      {tab === 'crosscase' && <CrossCaseTab caseId={kase.id} />}
      {tab === 'evidence' && (
        <>
      {canUpload && <EvidenceUpload caseId={kase.id} onSealed={() => loadEvidence().catch(() => undefined)} />}
      <ErrorNote error={actionError} />

      <section className="panel">
        <div className="panel-head">
          <h2>Sealed evidence</h2>
          <span className="muted small">
            <Lock size={12} aria-hidden /> Each file is re-hashed whenever it is opened; a mismatch blocks it.
          </span>
        </div>
        {evidence && evidence.length === 0 && <p className="muted pad">No evidence in this case yet.</p>}
        {evidence && evidence.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>SHA-256</th>
                  <th>Sealed</th>
                  <th>Integrity</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {evidence.map((ev) => {
                  const v = verified[ev.id]
                  const original = ev.duplicate_of ? byId.get(ev.duplicate_of) : null
                  return (
                    <tr key={ev.id} className={ev.integrity_status !== 'OK' ? 'row-bad' : undefined}>
                      <td>
                        <div className="file-name">{ev.filename}</div>
                        <div className="muted small">
                          {KIND_LABELS[ev.kind] ?? ev.kind} · {ev.type} · {formatBytes(ev.size_bytes)}
                        </div>
                        {original && <div className="dup small">Identical copy of {original.filename}: counts as one source</div>}
                        {!original && (groups.get(ev.id) ?? 0) > 1 && <div className="dup small">Has identical copies in this case</div>}
                      </td>
                      <td>
                        <Hash value={ev.sha256} />
                      </td>
                      <td>
                        <div className="small">{formatDateTime(ev.uploaded_at)}</div>
                        <div className="muted small">{ev.uploaded_by_name || ev.uploaded_by}</div>
                      </td>
                      <td>
                        <IntegrityBadge status={ev.integrity_status} />
                        <div className="muted small">
                          {v ? `re-checked ${formatDateTime(v.verified_at)}` : ev.last_verified_at ? `checked ${formatDateTime(ev.last_verified_at)}` : ''}
                        </div>
                      </td>
                      <td className="actions">
                        <button className="btn btn-small" onClick={() => setViewing(ev)}>
                          <Eye size={14} aria-hidden /> View
                        </button>
                        <button className="btn btn-small btn-ghost" disabled={verifying === ev.id} onClick={() => verify(ev)}>
                          <RefreshCw size={14} aria-hidden className={verifying === ev.id ? 'spin' : undefined} /> Verify
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        {!evidence && <p className="muted pad">Loading evidence…</p>}
      </section>
      {canUpload && evidence && evidence.length > 0 && (
        <p className="muted small">
          New files are extracted from the <Link to={`/cases/${kase.id}/review`}>review queue</Link>; nothing reaches the graph until it is confirmed there.
        </p>
      )}
        </>
      )}

      {viewing && <EvidenceViewer ev={viewing} onClose={closeViewer} onBlocked={onBlocked} />}
    </div>
  )
}

function BackLink() {
  return (
    <Link to="/cases" className="back">
      <ChevronLeft size={16} aria-hidden /> Cases
    </Link>
  )
}
