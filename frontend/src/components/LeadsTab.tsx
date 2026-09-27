import { ArrowRight, FileStack, FolderOpen, Lightbulb, Play } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api3, STATUS_LABELS, type LeadSummary } from '../api3'
import { useAuth } from '../auth'
import { ErrorNote } from './bits'
import { RULE_META, RuleIcon } from './icons'
import { Card, EmptyState } from './ui'

const RULE_ORDER = [
  'CONVERGENCE-v1', 'LAYERING-v1', 'CASHOUT-v1', 'FACILITATOR-v1', 'FRONT-ENTITY-v1', 'SHARED-ID-v1',
  'MO-MATCH-v1', 'ORDINARY-PAYMENT-v1',
]

export function StatusChip({ status }: { status: string }) {
  return <span className={`chip chip-status-${status.toLowerCase()}`}>{STATUS_LABELS[status] ?? status}</span>
}

export default function LeadsTab({ caseId }: { caseId: string }) {
  const { can } = useAuth()
  const [leads, setLeads] = useState<LeadSummary[] | null>(null)
  const [scope, setScope] = useState<Awaited<ReturnType<typeof api3.analysisScope>> | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [showInactive, setShowInactive] = useState(false)

  const load = useCallback(() => api3.caseLeads(caseId).then(setLeads, (e) => setError(e.message)), [caseId])
  useEffect(() => {
    load()
    if (can('analysis.run'))
      api3.analysisScope(caseId).then((s) => {
        setScope(s)
        setSelected(new Set(s.suggested))
      }, () => undefined)
  }, [caseId, load, can])

  const groups = useMemo(() => {
    const g = new Map<string, LeadSummary[]>()
    for (const l of leads ?? []) {
      if (!l.active && !showInactive) continue
      g.set(l.rule_id, [...(g.get(l.rule_id) ?? []), l])
    }
    return [...g.entries()].sort((a, b) => RULE_ORDER.indexOf(a[0]) - RULE_ORDER.indexOf(b[0]))
  }, [leads, showInactive])

  async function run() {
    setBusy(true)
    setError(null)
    setNote(null)
    try {
      const r = await api3.runAnalysis([...selected])
      setNote(`Analysis run: ${r.created} new lead(s), ${r.updated} updated, ${r.no_longer_produced} no longer produced.`)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed.')
    } finally {
      setBusy(false)
    }
  }

  const inactive = (leads ?? []).filter((l) => !l.active).length
  const blocked = scope?.open_quality_issues.filter((q) => selected.has(q.case_id)) ?? []

  return (
    <div className="review">
      {scope && (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>
                <Lightbulb size={15} aria-hidden /> Run the rule library
              </h2>
              <span className="muted small">
                Eight versioned rules on confirmed evidence. They produce observations for an officer to verify, never conclusions.
              </span>
            </div>
            <button className="btn btn-primary" disabled={busy || selected.size === 0 || blocked.length > 0} onClick={run}>
              <Play size={15} aria-hidden /> {busy ? 'Running…' : `Analyse ${selected.size} case${selected.size === 1 ? '' : 's'}`}
            </button>
          </div>
          <div className="scope-list">
            {scope.available.map((c) => (
              <label key={c.id} className={`scope-item${scope.suggested.includes(c.id) ? ' scope-suggested' : ''}`}>
                <input
                  type="checkbox"
                  checked={selected.has(c.id)}
                  onChange={(e) => {
                    const next = new Set(selected)
                    if (e.target.checked) next.add(c.id)
                    else next.delete(c.id)
                    setSelected(next)
                  }}
                />
                <span className="case-id">{c.id}</span> <span className="muted small">{c.city}</span>
              </label>
            ))}
          </div>
          <p className="muted small pad-x">
            Pre-selected: this case and the cases you can see that share an account, phone or UPI ID with it (billers used by many
            cases are ignored).
          </p>
          {blocked.length > 0 && (
            <div className="note note-bad">
              Open intake quality issues must be reviewed first: {blocked.map((q) => `${q.case_id} ${q.check.replace(/_/g, ' ')}`).join('; ')}.
            </div>
          )}
        </section>
      )}
      <ErrorNote error={error} />
      {note && <div className="note note-ok">{note}</div>}

      {leads && leads.length === 0 && (
        <Card>
          <EmptyState icon={<Lightbulb size={22} />} title="No leads involve this case yet">
            Run the rule library above on this case and the related cases it shares identifiers with.
          </EmptyState>
        </Card>
      )}
      {inactive > 0 && (
        <label className="small toggle">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} /> Show {inactive} lead(s) no
          longer produced by the latest run
        </label>
      )}
      {groups.map(([rule, items]) => (
        <section key={rule} className="review-section">
          <div className={`rule-head ${RULE_META[rule]?.tone ?? ''}`}>
            <span className="rule-icon"><RuleIcon rule={rule} size={16} /></span>
            <h2>{items[0].title}</h2>
            <span className="rule-count">{items.length}</span>
            <span className="extractor">{rule}</span>
          </div>
          <div className="lead-grid">
            {items.map((l) => (
              <Link key={l.id} to={`/leads/${l.id}`} className={`lead-card ${RULE_META[rule]?.tone ?? ''}${l.active ? '' : ' lead-inactive'}`}>
                <div className="lead-card-head">
                  <StatusChip status={l.status} />
                  {l.pending && <span className="chip chip-warn">Proposed: {STATUS_LABELS[l.pending.status]}</span>}
                  {!l.active && <span className="chip">Not produced by latest run</span>}
                </div>
                <div className="lead-subject">{l.subject?.label}</div>
                <p className="small">{l.observation}</p>
                <div className="lead-card-foot">
                  <span>
                    <FolderOpen size={13} aria-hidden /> {l.case_ids.join(', ')}
                  </span>
                  <span>
                    <FileStack size={13} aria-hidden /> {l.independent_sources ?? '?'} source{l.independent_sources === 1 ? '' : 's'}
                    <ArrowRight size={13} aria-hidden />
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
