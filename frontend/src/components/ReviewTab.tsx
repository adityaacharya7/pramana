import { AlertTriangle, Check, FileSearch, GitMerge, Play, Split, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api, type IdentityCandidate, type QualityIssue, type ReviewFile, type ReviewQueue, type Snippet } from '../api'
import { useAuth } from '../auth'
import { DETERMINISTIC, extractorLabel, formatDateTime, formatINR, KIND_LABELS, TYPE_LABELS } from '../format'
import { ErrorNote } from './bits'
import SourceDrawer, { type SourceRef } from './SourceDrawer'

export function SnippetView({ s }: { s: Snippet | null }) {
  if (!s) return <span className="muted small">source blocked</span>
  return (
    <span className="snippet">
      {s.before}
      <mark>{s.match}</mark>
      {s.after}
    </span>
  )
}

export default function ReviewTab({ caseId, onChanged }: { caseId: string; onChanged?: () => void }) {
  const { can } = useAuth()
  const [queue, setQueue] = useState<ReviewQueue | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [source, setSource] = useState<SourceRef | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const canDecide = can('extraction.decide')

  const load = useCallback(() => api.reviewQueue(caseId).then(setQueue, (e) => setError(e.message)), [caseId])
  useEffect(() => {
    load()
  }, [load])

  async function act(key: string, fn: () => Promise<unknown>, done?: string) {
    setBusy(key)
    setError(null)
    try {
      await fn()
      if (done) setNote(done)
      await load()
      onChanged?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action failed.')
    } finally {
      setBusy(null)
    }
  }

  const closeSource = useCallback(() => setSource(null), [])
  if (!queue) return <p className="muted pad">{error ?? 'Loading review queue…'}</p>

  const t = queue.totals
  const pendingFiles = queue.files
    .filter((f) => f.pending_groups.length > 0)
    .sort((a, b) => b.counts.PENDING - a.counts.PENDING)
  const doneFiles = queue.files.filter((f) => f.extracted && f.pending_groups.length === 0)

  return (
    <div className="review">
      <div className="stat-row">
        <Stat n={t.pending_extractions} label="mentions awaiting review" />
        <Stat n={t.open_quality_issues} label="open intake issues" tone={t.open_quality_issues ? 'warn' : undefined} />
        <Stat n={t.undecided_identity_candidates} label="identity questions" />
        <Stat n={t.files_not_extracted} label="files not yet extracted" />
      </div>
      <p className="muted small">Nothing enters the graph until it is confirmed here. Every item links to the exact text it was read from.</p>
      <ErrorNote error={error} />
      {note && (
        <div className="note note-ok" role="status">
          <Check size={16} aria-hidden /> <span>{note}</span>
        </div>
      )}

      {t.files_not_extracted > 0 && can('extraction.run') && (
        <section className="panel callout">
          <div>
            <h2>
              {t.files_not_extracted} file{t.files_not_extracted === 1 ? '' : 's'} not yet extracted
            </h2>
            <p className="muted small">Extraction proposes people, identifiers and relationships with their source spans, and runs the intake quality checks.</p>
          </div>
          <button
            className="btn btn-primary"
            disabled={busy === 'extract'}
            onClick={() =>
              act('extract', async () => {
                const r = await api.extract(caseId)
                setNote(`Extracted ${r.extractions_created} mentions from ${r.files_processed.length} file(s).` +
                  (r.files_blocked.length ? ` Blocked: ${r.files_blocked.join(', ')}.` : ''))
              })
            }
          >
            <Play size={15} aria-hidden /> {busy === 'extract' ? 'Extracting…' : 'Run extraction'}
          </button>
        </section>
      )}

      {queue.quality_issues.length > 0 && (
        <section className="review-section">
          <h2>Intake quality checks</h2>
          {queue.quality_issues.map((q) => (
            <IssueCard
              key={q.id}
              issue={q}
              files={queue.files}
              canDecide={can('quality.decide')}
              busy={busy === q.id}
              onOpen={setSource}
              onAcknowledge={(reason, order) => act(q.id, () => api.decideQuality(q.id, reason, order), 'Issue acknowledged and logged.')}
            />
          ))}
        </section>
      )}

      <section className="review-section">
        <h2>Extracted mentions</h2>
        {pendingFiles.length === 0 && <p className="muted">No mentions are waiting for review.</p>}
        {pendingFiles.map((f) => (
          <FileBlock
            key={f.evidence_id}
            file={f}
            canDecide={canDecide}
            busy={busy}
            onOpen={setSource}
            onDecide={(key, id, decision, scope, extractors) =>
              act(key, () => api.decideExtraction(id, decision, scope, extractors))
            }
          />
        ))}
        {doneFiles.length > 0 && (
          <p className="muted small">
            {doneFiles.length} file{doneFiles.length === 1 ? '' : 's'} fully reviewed:{' '}
            {doneFiles.map((f) => `${f.filename} (${f.counts.CONFIRMED} confirmed${f.counts.REJECTED ? `, ${f.counts.REJECTED} rejected` : ''})`).join(' · ')}
          </p>
        )}
      </section>

      <section className="review-section">
        <h2>Identity review</h2>
        <p className="muted small">
          Records of people are never joined on a name alone. Suggestions are scored on shared or conflicting identifiers; the decision
          and its reason go to the audit log, and a merge can be split again.
        </p>
        {queue.identity_candidates.length === 0 && <p className="muted">No identity questions for this case.</p>}
        {queue.identity_candidates.map((c) => (
          <CandidateCard
            key={c.id}
            c={c}
            canDecide={can('identity.decide')}
            busy={busy === c.id}
            onOpen={setSource}
            onDecide={(decision, reason) =>
              act(c.id, () => api.decideIdentity(caseId, c.a, c.b, decision, reason), `Identity decision recorded: ${decision.replace('_', ' ').toLowerCase()}.`)
            }
          />
        ))}
      </section>

      {source && <SourceDrawer source={source} onClose={closeSource} />}
    </div>
  )
}

function Stat({ n, label, tone }: { n: number; label: string; tone?: 'warn' }) {
  return (
    <div className={`stat${tone ? ` stat-${tone}` : ''}`}>
      <span className="stat-n">{n}</span>
      <span className="stat-l">{label}</span>
    </div>
  )
}

type Decide = (
  key: string,
  id: string,
  decision: 'confirm' | 'reject',
  scope: 'mention' | 'value' | 'file',
  extractors?: string[],
) => void

function FileBlock({
  file,
  canDecide,
  busy,
  onOpen,
  onDecide,
}: {
  file: ReviewFile
  canDecide: boolean
  busy: string | null
  onOpen: (s: SourceRef) => void
  onDecide: Decide
}) {
  const ruleBased = file.pending_groups.filter((g) => !extractorLabel(g.extractor).model)
  const ruleCount = ruleBased.reduce((n, g) => n + g.count, 0)
  const allSpans = file.pending_groups.flatMap((g) => g.spans)
  return (
    <div className="panel file-block">
      <div className="panel-head">
        <div>
          <h3>{file.filename}</h3>
          <span className="muted small">
            {KIND_LABELS[file.kind] ?? file.kind} · {file.counts.PENDING} pending · {file.counts.CONFIRMED} confirmed · {file.counts.REJECTED} rejected
          </span>
        </div>
        <div className="row-actions">
          <button className="btn btn-small btn-ghost" onClick={() => onOpen({ evidenceId: file.evidence_id, filename: file.filename, spans: allSpans, title: 'Pending mentions in source' })}>
            <FileSearch size={14} aria-hidden /> Source
          </button>
          {canDecide && ruleCount > 0 && (
            <button
              className="btn btn-small"
              disabled={busy !== null}
              onClick={() => onDecide(`file:${file.evidence_id}`, ruleBased[0].sample_id, 'confirm', 'file', DETERMINISTIC)}
            >
              <Check size={14} aria-hidden /> Confirm {ruleCount} rule-based
            </button>
          )}
        </div>
      </div>
      <ul className="mention-list">
        {file.pending_groups.map((g) => {
          const ex = extractorLabel(g.extractor)
          const key = `g:${g.sample_id}`
          return (
            <li key={g.sample_id} className="mention">
              <div className="mention-head">
                <span className={`chip chip-type-${g.entity_type}`}>{TYPE_LABELS[g.entity_type] ?? g.entity_type}</span>
                <code className="mention-value">{g.value}</code>
                {g.count > 1 && <span className="muted small">×{g.count}</span>}
                <span className={`extractor${ex.model ? ' extractor-model' : ''}`} title={g.extractor}>
                  {ex.label}
                </span>
              </div>
              <div className="mention-body">
                <SnippetView s={g.snippet} />
              </div>
              <div className="row-actions">
                <button className="btn btn-small btn-ghost" onClick={() => onOpen({ evidenceId: file.evidence_id, filename: file.filename, spans: g.spans, title: g.value })}>
                  <FileSearch size={14} aria-hidden /> Source
                </button>
                {canDecide && (
                  <>
                    <button className="btn btn-small" disabled={busy !== null} onClick={() => onDecide(key, g.sample_id, 'confirm', 'value')}>
                      <Check size={14} aria-hidden /> Confirm
                    </button>
                    <button className="btn btn-small btn-ghost" disabled={busy !== null} onClick={() => onDecide(key, g.sample_id, 'reject', 'value')}>
                      <X size={14} aria-hidden /> Reject
                    </button>
                  </>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function IssueCard({
  issue,
  files,
  canDecide,
  busy,
  onOpen,
  onAcknowledge,
}: {
  issue: QualityIssue
  files: ReviewFile[]
  canDecide: boolean
  busy: boolean
  onOpen: (s: SourceRef) => void
  onAcknowledge: (reason: string, order?: 'DMY' | 'MDY') => void
}) {
  const [reason, setReason] = useState('')
  const [order, setOrder] = useState<'DMY' | 'MDY' | ''>('')
  const d = issue.detail as Record<string, never>
  const named = issue.file_ids.map((id) => files.find((f) => f.evidence_id === id)).filter(Boolean) as ReviewFile[]
  const ambiguous = issue.check === 'ambiguous_date_format'
  return (
    <div className={`panel issue ${issue.status === 'OPEN' ? 'issue-open' : ''}`}>
      <div className="panel-head">
        <div className="issue-title">
          <AlertTriangle size={16} aria-hidden />
          <h3>{issue.label}</h3>
          <span className={`chip ${issue.status === 'OPEN' ? 'chip-warn' : 'chip-neutral'}`}>{issue.status === 'OPEN' ? 'Open' : 'Acknowledged'}</span>
        </div>
        <div className="row-actions">
          {named.map((f) => (
            <button key={f.evidence_id} className="btn btn-small btn-ghost" onClick={() => onOpen({ evidenceId: f.evidence_id, filename: f.filename, spans: [] })}>
              <FileSearch size={14} aria-hidden /> {f.filename}
            </button>
          ))}
        </div>
      </div>
      <div className="issue-body">
        {issue.check === 'balance_does_not_reconcile' && (
          <table className="table table-dense recon">
            <tbody>
              <tr><th>Opening balance</th><td className="num">{formatINR(d.opening)}</td></tr>
              <tr><th>+ Inflows</th><td className="num">{formatINR(d.inflows)}</td></tr>
              <tr><th>− Outflows</th><td className="num">{formatINR(d.outflows)}</td></tr>
              <tr><th>Closing balance (stated)</th><td className="num">{formatINR(d.closing)}</td></tr>
              <tr className="recon-diff"><th>Unexplained difference</th><td className="num">{formatINR(d.unexplained_difference)}</td></tr>
              {d.first_break_row != null && <tr><th>Running balance first breaks at</th><td className="num">row {d.first_break_row}</td></tr>}
            </tbody>
          </table>
        )}
        {issue.check === 'statement_date_gap' && (
          <p>
            Account <code>{d.account}</code>: no statement covers {formatDateTime(d.missing_from)} to {formatDateTime(d.missing_to)}.
          </p>
        )}
        {issue.check === 'duplicate_statement' && <p>Account <code>{d.account}</code> received {(d.filenames as unknown as string[]).length} times.</p>}
        {typeof d.note === 'string' && <p className="muted small">{d.note}</p>}
        {issue.status === 'ACKNOWLEDGED' && issue.resolution && (
          <p className="small">
            Acknowledged {formatDateTime(issue.decided_at)}: {issue.resolution.reason}
            {issue.resolution.date_order && ` · dates read as ${issue.resolution.date_order === 'DMY' ? 'DD/MM' : 'MM/DD'}`}
          </p>
        )}
        {issue.status === 'OPEN' && canDecide && (
          <div className="decide-row">
            {ambiguous && (
              <select value={order} onChange={(e) => setOrder(e.target.value as 'DMY' | 'MDY')} aria-label="Date reading">
                <option value="">Read dates as…</option>
                <option value="DMY">DD/MM/YYYY</option>
                <option value="MDY">MM/DD/YYYY</option>
              </select>
            )}
            <input placeholder="Reason (required, logged)" value={reason} onChange={(e) => setReason(e.target.value)} aria-label="Reason" />
            <button
              className="btn btn-small"
              disabled={busy || reason.trim().length < 3 || (ambiguous && !order)}
              onClick={() => onAcknowledge(reason.trim(), ambiguous ? (order as 'DMY' | 'MDY') : undefined)}
            >
              Acknowledge
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

const SUGGESTION = {
  merge_suggested: { label: 'Merge suggested: an identifier is shared', tone: 'ok' },
  likely_different: { label: 'Likely different people: identifiers conflict', tone: 'bad' },
  insufficient_identifiers: { label: 'Not enough identifiers to decide', tone: 'neutral' },
} as const

function CandidateCard({
  c,
  canDecide,
  busy,
  onOpen,
  onDecide,
}: {
  c: IdentityCandidate
  canDecide: boolean
  busy: boolean
  onOpen: (s: SourceRef) => void
  onDecide: (decision: string, reason: string) => void
}) {
  const [reason, setReason] = useState('')
  const s = SUGGESTION[c.suggestion]
  const shared = new Set(c.shared.map((x) => `${x.type}:${x.value}`))
  const conflictTypes = new Set(c.conflicting.map((x) => x.type))
  const decided = c.decision
  const side = (card: IdentityCandidate['a_card'], ids: [string, string][]) => (
    <div className="identity-side">
      <div className="identity-name">
        {card.name} <span className="muted small">{TYPE_LABELS[card.type]}</span>
      </div>
      <div className="small">Cases: {card.cases.join(', ') || '—'}</div>
      <ul className="identity-ids">
        {ids.length === 0 && <li className="muted small">No identifiers linked</li>}
        {ids.map(([t, v]) => (
          <li key={`${t}:${v}`} className={shared.has(`${t}:${v}`) ? 'id-shared' : conflictTypes.has(t) ? 'id-conflict' : undefined}>
            <span className="muted small">{TYPE_LABELS[t] ?? t}</span> <code>{v}</code>
          </li>
        ))}
      </ul>
      {card.sources.map((src) => (
        <button key={src.evidence_id} className="source-link" onClick={() => onOpen({ evidenceId: src.evidence_id, filename: src.filename, spans: [src.span], title: card.name })}>
          <span className="small">{src.filename}</span>
          <SnippetView s={src.snippet} />
        </button>
      ))}
    </div>
  )
  return (
    <div className="panel identity">
      <div className="panel-head">
        <span className={`chip chip-sugg-${s.tone}`}>{s.label}</span>
        <span className="muted small">name similarity {Math.round(c.name_similarity * 100)}%</span>
      </div>
      <div className="identity-grid">
        {side(c.a_card, c.identifiers[c.a] ?? [])}
        {side(c.b_card, c.identifiers[c.b] ?? [])}
      </div>
      <div className="identity-foot">
        {decided ? (
          <div className="decided">
            <strong>{decided.decision === 'MERGE' ? 'Merged' : decided.decision === 'KEEP_SEPARATE' ? 'Kept separate' : decided.decision === 'SPLIT' ? 'Split' : 'Left unresolved'}</strong>
            <span className="muted small">
              {' '}
              · {formatDateTime(decided.decided_at)} · {decided.reason}
            </span>
          </div>
        ) : (
          <span className="muted small">No decision yet.</span>
        )}
        {canDecide && (
          <div className="decide-row">
            <input placeholder="Reason (required, logged)" value={reason} onChange={(e) => setReason(e.target.value)} aria-label="Reason for identity decision" />
            {decided?.decision === 'MERGE' ? (
              <button className="btn btn-small" disabled={busy || reason.trim().length < 3} onClick={() => onDecide('SPLIT', reason.trim())}>
                <Split size={14} aria-hidden /> Split
              </button>
            ) : (
              <>
                <button className="btn btn-small" disabled={busy || reason.trim().length < 3} onClick={() => onDecide('MERGE', reason.trim())}>
                  <GitMerge size={14} aria-hidden /> Merge
                </button>
                <button className="btn btn-small" disabled={busy || reason.trim().length < 3} onClick={() => onDecide('KEEP_SEPARATE', reason.trim())}>
                  Keep separate
                </button>
                <button className="btn btn-small btn-ghost" disabled={busy || reason.trim().length < 3} onClick={() => onDecide('UNRESOLVED', reason.trim())}>
                  Leave unresolved
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
