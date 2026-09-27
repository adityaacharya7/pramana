import { CheckCircle2, ChevronLeft, Download, FileSearch, FlaskConical, ShieldAlert } from 'lucide-react'
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api3, NEXT_STATUSES, STATUS_LABELS, type Draft, type LeadDetail, type Method, type Operation, type Scenario } from '../api3'
import { useAuth } from '../auth'
import { ErrorNote } from '../components/bits'
import { StatusChip } from '../components/LeadsTab'
import SourceDrawer, { type SourceRef } from '../components/SourceDrawer'
import { formatDateTime, formatINR } from '../format'

export default function LeadPageRoute() {
  const { leadId = '' } = useParams()
  return <LeadPage key={leadId} leadId={leadId} />
}

function LeadPage({ leadId }: { leadId: string }) {
  const { me } = useAuth()
  const [lead, setLead] = useState<LeadDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [source, setSource] = useState<SourceRef | null>(null)
  const load = useCallback(() => api3.lead(leadId).then(setLead, (e) => setError(e.message)), [leadId])
  useEffect(() => {
    load()
  }, [load])
  const closeSource = useCallback(() => setSource(null), [])

  if (error && !lead) return <div className="page"><ErrorNote error={error} /></div>
  if (!lead) return <div className="page muted">Loading lead…</div>
  const r = lead.receipt
  const role = me?.user.role
  const back = lead.case_ids[0]

  return (
    <div className="page">
      <Link to={`/cases/${back}/leads`} className="back">
        <ChevronLeft size={16} aria-hidden /> Leads in {back}
      </Link>
      <div className="case-head">
        <div>
          <div className="case-kicker">
            <StatusChip status={lead.status} />
            <span className="muted mono small">{lead.rule_id}</span>
            {!lead.active && <span className="chip chip-warn">Not produced by the latest analysis</span>}
          </div>
          <h1>{lead.title}</h1>
          <p className="lead-subject-lg">{lead.subject?.label}</p>
          <p>{lead.observation}</p>
          <p className="muted small">
            Cases: {lead.case_ids.join(', ')} · analysed with {lead.analysis_cases.join(', ')}
          </p>
        </div>
        <div className="members">
          <h3>Handover</h3>
          <p className="muted small">Export the Evidence Receipt, estimates and a re-run bundle another officer can reproduce offline.</p>
          <div className="row-actions">
            <button className="btn btn-small" disabled={!lead.reproduced_now} onClick={() => api3.exportJson(lead.id).then(load, (e) => setError(e.message))}>
              <Download size={14} aria-hidden /> Bundle (JSON)
            </button>
            <button className="btn btn-small" disabled={!lead.reproduced_now} onClick={() => api3.exportPdf(lead.id).then(load, (e) => setError(e.message))}>
              <Download size={14} aria-hidden /> Pack (PDF)
            </button>
          </div>
        </div>
      </div>
      <ErrorNote error={error} />

      <Lifecycle lead={lead} role={role} onDone={load} onError={setError} />

      {r ? (
        <section className="panel">
          <div className="panel-head">
            <h2>Evidence Receipt</h2>
            <span className="muted small">
              {r.rule.id} v{r.rule.version} · {r.independent_sources} independent source{r.independent_sources === 1 ? '' : 's'}
            </span>
          </div>
          <div className="receipt">
            <div>
              <h3>Supporting records</h3>
              <ul className="source-list">
                {r.supporting_records.map((s, i) => (
                  <li key={i}>
                    <button className="source-link" onClick={() => setSource({ evidenceId: s.file_id, filename: s.filename ?? '', spans: [s.span], title: s.label })}>
                      <span className="small">
                        <FileSearch size={12} aria-hidden /> {s.case_id} · {s.filename} · <span className="muted">{s.kind}</span>
                      </span>
                      <span className="small">{s.label}</span>
                      {s.note && <span className="muted small">“{s.note}”</span>}
                    </button>
                  </li>
                ))}
              </ul>
              <p className="muted small">{r.what_could_make_this_wrong.note}</p>
            </div>
            <div className="receipt-side">
              <Block title="Unknowns" items={r.unknowns} />
              <div className="wrong">
                <h3>
                  <ShieldAlert size={15} aria-hidden /> What could make this wrong?
                </h3>
                <p className="small"><strong>Ordinary explanation.</strong> {r.what_could_make_this_wrong.ordinary_explanation}</p>
                <Block title="Contradictions" items={r.what_could_make_this_wrong.contradictions} />
                <Block title="Records that would tell the two apart" items={r.what_could_make_this_wrong.records_that_would_distinguish} />
              </div>
              <div>
                <h3>Next verification step</h3>
                <p className="small">{r.next_verification_step}</p>
              </div>
            </div>
          </div>
        </section>
      ) : (
        <div className="note note-bad">This lead is not produced by the current analysis of its cases, so no live receipt is shown.</div>
      )}

      {(r || lead.scenarios.length > 0) && <Challenge lead={lead} role={role} onDone={load} onError={setError} />}
      {(r || lead.drafts.length > 0) && <Drafts lead={lead} role={role} onDone={load} onError={setError} />}

      <section className="panel">
        <div className="panel-head">
          <h2>Decision trail</h2>
          <span className="muted small">Every step on this lead, from the audit log</span>
        </div>
        <table className="table table-dense">
          <tbody>
            {lead.history.map((h) => (
              <tr key={h.seq}>
                <td className="num mono">#{h.seq}</td>
                <td className="nowrap small">{formatDateTime(h.ts)}</td>
                <td className="mono small">{h.actor}</td>
                <td><span className="chip chip-neutral">{h.action}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {source && <SourceDrawer source={source} onClose={closeSource} />}
    </div>
  )
}

function Block({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3>{title}</h3>
      <ul className="bullets">
        {(items.length ? items : ['None recorded.']).map((x, i) => (
          <li key={i} className="small">{x}</li>
        ))}
      </ul>
    </div>
  )
}

type Props = { lead: LeadDetail; role?: string; onDone: () => void; onError: (e: string | null) => void }

function Lifecycle({ lead, role, onDone, onError }: Props) {
  const [to, setTo] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const act = async (action: 'propose' | 'approve' | 'reject') => {
    setBusy(true)
    onError(null)
    try {
      await api3.transition(lead.id, action, reason.trim(), action === 'propose' ? to : undefined)
      setReason('')
      setTo('')
      onDone()
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed.')
    } finally {
      setBusy(false)
    }
  }
  const canAct = role === 'IO' || role === 'SUPERVISOR'
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Lead status</h2>
        <span className="muted small">
          Detected → Under verification → Verified / Dismissed / Needs evidence. An IO proposes; a supervisory officer approves. Every change needs a reason.
        </span>
      </div>
      <div className="issue-body">
        {lead.pending && (
          <div className="note note-warn">
            {lead.pending.by} proposed <strong>{STATUS_LABELS[lead.pending.status]}</strong>: {lead.pending.reason}
          </div>
        )}
        {canAct && (
          <div className="decide-row">
            {!lead.pending && (
              <select value={to} onChange={(e) => setTo(e.target.value)} aria-label="New status">
                <option value="">Move to…</option>
                {(NEXT_STATUSES[lead.status] ?? []).map((s) => (
                  <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                ))}
              </select>
            )}
            <input placeholder="Reason (required, logged)" value={reason} onChange={(e) => setReason(e.target.value)} aria-label="Reason" />
            {!lead.pending && (
              <button className="btn btn-small" disabled={busy || !to || reason.trim().length < 3} onClick={() => act('propose')}>
                {role === 'SUPERVISOR' ? 'Change status' : 'Propose'}
              </button>
            )}
            {lead.pending && role === 'SUPERVISOR' && (
              <>
                <button className="btn btn-small btn-primary" disabled={busy || reason.trim().length < 3} onClick={() => act('approve')}>Approve</button>
                <button className="btn btn-small btn-ghost" disabled={busy || reason.trim().length < 3} onClick={() => act('reject')}>Reject</button>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  )
}

const OP_TEXT: Record<Operation['op'], string> = {
  exclude_source: 'Exclude this source — set the record aside; facts it alone supports lose support',
  dispute_txn: 'Dispute this transaction — keep it, flagged; show results with and without it',
  simulate_no_txn: 'Simulate it not occurring — a counterfactual; balances are recomputed',
}

function Challenge({ lead, role, onDone, onError }: Props) {
  const [pick, setPick] = useState(lead.sources[0]?.source ?? '')
  const [op, setOp] = useState<Operation['op']>('exclude_source')
  const [busy, setBusy] = useState(false)
  const [reason, setReason] = useState('')
  const group = lead.sources.find((s) => s.source === pick)
  const latest: Scenario | undefined = lead.scenarios[0]

  async function run() {
    if (!group) return
    const operation: Operation = op === 'exclude_source' ? { op, source: group.source } : { op, event_id: group.events[0] }
    setBusy(true)
    onError(null)
    try {
      await api3.challenge(lead.id, [operation])
      onDone()
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Challenge failed.')
    } finally {
      setBusy(false)
    }
  }
  async function act(action: 'propose' | 'approve' | 'reject') {
    if (!latest) return
    setBusy(true)
    onError(null)
    try {
      await api3.scenarioAction(latest.id, action, reason.trim())
      setReason('')
      onDone()
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>
          <FlaskConical size={16} aria-hidden /> Challenge Mode
        </h2>
        <span className="muted small">Runs on a scenario copy. The live case and its approved drafts change only when a reviewed change is applied.</span>
      </div>
      <div className="issue-body">
        {!lead.reproduced_now && (
          <p className="small muted">This lead is no longer produced, so new scenarios cannot be run on it. Earlier scenarios are shown below.</p>
        )}
        <div className="challenge-grid">
          <label className="small">
            Record to challenge
            <select value={pick} onChange={(e) => setPick(e.target.value)}>
              {lead.sources.map((s) => (
                <option key={s.source} value={s.source}>
                  {s.records[0]?.label ?? s.source} {s.records.length > 1 ? `(+${s.records.length - 1} view${s.records.length > 2 ? 's' : ''} of it)` : ''}
                </option>
              ))}
            </select>
          </label>
          <label className="small">
            Operation
            <select value={op} onChange={(e) => setOp(e.target.value as Operation['op'])}>
              {(Object.keys(OP_TEXT) as Operation['op'][]).map((k) => (
                <option key={k} value={k} disabled={k !== 'exclude_source' && !group?.events.length}>{OP_TEXT[k]}</option>
              ))}
            </select>
          </label>
        </div>
        {group && (
          <div className="small">
            <strong>Findings that depend on this record:</strong>
            <ul className="bullets">
              {group.dependents.map((d) => (
                <li key={d.key}>
                  {d.title} — {d.subject}{' '}
                  {d.single_source ? <span className="chip chip-bad">single source</span> : <span className="muted">({d.independent_sources} independent sources)</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
        <div>
          <button className="btn btn-primary btn-small" disabled={busy || !group || !lead.reproduced_now} onClick={run}>
            <FlaskConical size={14} aria-hidden /> Run scenario
          </button>
        </div>

        {latest && <ScenarioView sc={latest} />}
        {latest && latest.status !== 'applied' && latest.status !== 'rejected' && (role === 'IO' || role === 'SUPERVISOR') && (
          <div className="decide-row">
            <input placeholder="Reason (required, logged)" value={reason} onChange={(e) => setReason(e.target.value)} aria-label="Reason for scenario decision" />
            {latest.status === 'sandbox' && (
              <button className="btn btn-small" disabled={busy || reason.trim().length < 3} onClick={() => act('propose')}>
                Propose applying to the case
              </button>
            )}
            {latest.status === 'proposed' && role === 'SUPERVISOR' && (
              <>
                <button className="btn btn-small btn-primary" disabled={busy || reason.trim().length < 3} onClick={() => act('approve')}>
                  Approve and apply
                </button>
                <button className="btn btn-small btn-ghost" disabled={busy || reason.trim().length < 3} onClick={() => act('reject')}>
                  Reject
                </button>
              </>
            )}
          </div>
        )}
        {lead.operations_applied.length > 0 && (
          <p className="muted small">
            Applied to the live case: {lead.operations_applied.map((o) => `${o.op.replace(/_/g, ' ')} ${o.source ?? o.event_id}`).join('; ')}
          </p>
        )}
      </div>
    </section>
  )
}

function ScenarioView({ sc }: { sc: Scenario }) {
  const d = sc.diff
  return (
    <div className="scenario">
      <div className="scenario-head">
        <span className={`chip ${sc.status === 'applied' ? 'chip-bad' : sc.status === 'proposed' ? 'chip-warn' : 'chip-neutral'}`}>
          {sc.status === 'sandbox' ? 'Scenario (sandbox)' : sc.status === 'proposed' ? `Proposed by ${sc.proposed_by}` : sc.status === 'applied' ? `Applied — approved by ${sc.approved_by}` : 'Rejected'}
        </span>
        <span className="small muted">{sc.operations.map((o) => `${o.op.replace(/_/g, ' ')}: ${o.source ?? o.event_id}`).join('; ')}</span>
      </div>
      <div className="diff-grid">
        <div>
          <h4>Findings removed</h4>
          {d.removed.length === 0 && <p className="muted small">None.</p>}
          {d.removed.map((x) => (
            <div key={x.key} className="diff-item diff-removed">
              <strong className="small">{x.title}</strong> <span className="small muted">{x.subject}</span>
              <p className="small">{x.why}</p>
            </div>
          ))}
          <h4>Findings changed</h4>
          {d.changed.length === 0 && <p className="muted small">None.</p>}
          {d.changed.map((x) => (
            <div key={x.key} className="diff-item">
              <strong className="small">{x.title}</strong>
              <p className="small">Before: {x.before?.summary}</p>
              <p className="small">After: {x.after?.summary}</p>
            </div>
          ))}
          {d.added.length > 0 && <h4>Findings added</h4>}
          {d.added.map((x) => <div key={x.key} className="diff-item small">{x.title} — {x.subject}</div>)}
        </div>
        <div>
          <h4>Amount estimates</h4>
          {!d.reconciles_after && (
            <div className="note note-bad small">The remaining records do not reconcile: affected figures read “insufficient evidence to recompute reliably”.</div>
          )}
          <table className="table table-dense">
            <thead><tr><th>Account</th><th className="num">FIFO</th><th className="num">LIFO</th><th className="num">Pro-rata</th></tr></thead>
            <tbody>
              {d.estimates.map((e) => (
                <tr key={e.party}>
                  <td className="mono small">{e.party}</td>
                  {(['fifo', 'lifo', 'prorata'] as const).map((m) => (
                    <td key={m} className="num small">
                      {e.uncertain_after ? <span className="bad">insufficient evidence</span> : <>{formatINR(e.before[m])} → {formatINR(e.after[m])}</>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <h4>Drafts this would affect</h4>
          {d.affected_drafts.length === 0 && <p className="muted small">None.</p>}
          <ul className="bullets">
            {d.affected_drafts.map((x) => (
              <li key={x.draft_id} className="small">
                <span className="mono">{x.account_id}</span> ({x.status.toLowerCase()}, {formatINR(x.amount)}): {x.why}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

function Drafts({ lead, role, onDone, onError }: Props) {
  const [method, setMethod] = useState<Method>('prorata')
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<string | null>(null)
  const sets = useMemo(() => {
    const m = new Map<string, Draft[]>()
    for (const d of lead.drafts) m.set(d.set_id, [...(m.get(d.set_id) ?? []), d])
    return [...m.values()].reverse()
  }, [lead.drafts])

  const create = async () => {
    setBusy(true)
    onError(null)
    try {
      await api3.createDrafts(lead.id, method)
      onDone()
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed.')
    } finally {
      setBusy(false)
    }
  }
  const approve = async (id: string) => {
    setBusy(true)
    onError(null)
    try {
      await api3.approveDraft(id, 'Reviewed')
      onDone()
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Amount &amp; Draft Assistant</h2>
        <span className="muted small">One method per draft set; every figure is an estimate; drafts are never sent by the system.</span>
      </div>
      <div className="issue-body">
        {role === 'IO' && (
          <div className="decide-row">
            <select value={method} onChange={(e) => setMethod(e.target.value as Method)} aria-label="Attribution method">
              <option value="fifo">FIFO — oldest funds leave first</option>
              <option value="lifo">LIFO — newest funds leave first</option>
              <option value="prorata">Pro-rata — every source in proportion</option>
            </select>
            <button className="btn btn-small" disabled={busy || !lead.reproduced_now} onClick={create}>Prepare draft set</button>
          </div>
        )}
        {sets.length === 0 && <p className="muted small">No drafts for this lead.</p>}
        {sets.map((set) => (
          <div key={set[0].set_id} className="draft-set">
            <p className="small">
              <strong>{set[0].method.toUpperCase()}</strong> · prepared by {set[0].created_by} {formatDateTime(set[0].created_at)} · total{' '}
              {formatINR(set.reduce((n, d) => n + d.amount, 0))}
            </p>
            <table className="table table-dense">
              <thead><tr><th>Account</th><th className="num">Estimate</th><th className="num">Range across methods</th><th>As of</th><th>Status</th><th /></tr></thead>
              <tbody>
                {set.map((d) => (
                  <Fragment key={d.id}>
                    <tr className={d.stale ? 'row-bad' : undefined}>
                      <td className="mono small">{d.account_id}</td>
                      <td className="num">{formatINR(d.amount)}</td>
                      <td className="num small">{formatINR(d.estimate_min)} – {formatINR(d.estimate_max)}</td>
                      <td className="small">{d.as_of ? d.as_of.slice(0, 10) : 'no statement'}</td>
                      <td>
                        <span className={`chip ${d.status === 'APPROVED' ? 'chip-evidence' : d.status === 'NEEDS_REAPPROVAL' ? 'chip-bad' : 'chip-neutral'}`}>
                          {d.status === 'NEEDS_REAPPROVAL' ? 'Needs re-approval' : d.status.toLowerCase()}
                        </span>
                        {d.approved_by && d.status === 'APPROVED' && <div className="muted small">by {d.approved_by}</div>}
                        {d.stale_reason && <div className="bad small">{d.stale_reason}</div>}
                      </td>
                      <td className="actions">
                        <button className="btn btn-small btn-ghost" onClick={() => setOpen(open === d.id ? null : d.id)}>{open === d.id ? 'Hide' : 'View'}</button>
                        {role === 'SUPERVISOR' && d.status !== 'APPROVED' && (
                          <button className="btn btn-small" disabled={busy} onClick={() => approve(d.id)}>
                            <CheckCircle2 size={14} aria-hidden /> Approve
                          </button>
                        )}
                      </td>
                    </tr>
                    {open === d.id && (
                      <tr>
                        <td colSpan={6}>
                          {d.notes.length > 0 && (
                            <ul className="bullets">{d.notes.map((n, i) => <li key={i} className="small">{n}</li>)}</ul>
                          )}
                          <pre className="doc">{d.draft_text}</pre>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </section>
  )
}
