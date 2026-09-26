import { Link2, Search, ShieldAlert, ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, type LedgerEntry, type LedgerReport } from '../api'
import { useAuth } from '../auth'
import { ErrorNote } from '../components/bits'
import { formatDateTime, shortHash } from '../format'

const SUMMARY_KEYS = ['filename', 'attempted', 'reason', 'username', 'stage', 'fir_no', 'status', 'dataset', 'role', 'method'] as const

function summarize(e: LedgerEntry): string {
  const p = e.payload
  const parts: string[] = []
  for (const k of SUMMARY_KEYS) {
    const v = p[k]
    if (v !== undefined && v !== null && v !== '') parts.push(`${k.replace('_', ' ')}: ${String(v)}`)
  }
  if (typeof p.sha256 === 'string') parts.push(`sha256 ${shortHash(p.sha256, 8, 4)}`)
  if (e.action === 'LEDGER_VERIFIED') parts.push(p.ok ? `intact through #${p.head_seq}` : `broken at #${p.first_bad_seq}`)
  return parts.join(' · ')
}

function tone(action: string): string {
  if (action.includes('REFUSED') || action.includes('MISMATCH') || action.includes('FAILED') || action.includes('REJECTED')) return 'chip-bad'
  if (action.startsWith('EVIDENCE')) return 'chip-evidence'
  if (action.startsWith('AUTH') || action.startsWith('DEMO_SESSION')) return 'chip-auth'
  return 'chip-neutral'
}

export default function AuditLog() {
  const { can } = useAuth()
  const [report, setReport] = useState<LedgerReport | null>(null)
  const [checking, setChecking] = useState(false)
  const [entries, setEntries] = useState<LedgerEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const canRead = can('ledger.read')

  const loadEntries = useCallback(() => {
    if (canRead) api.ledger().then(setEntries, (e) => setError(e.message))
  }, [canRead])
  useEffect(loadEntries, [loadEntries])

  async function verify() {
    setChecking(true)
    setError(null)
    try {
      setReport(await api.verifyLedger())
      loadEntries()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Verification failed.')
    } finally {
      setChecking(false)
    }
  }

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!entries || !needle) return entries
    return entries.filter((e) => [e.action, e.actor, e.case_id ?? '', summarize(e)].some((v) => v.toLowerCase().includes(needle)))
  }, [entries, q])

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Audit log</h1>
          <p className="muted">Append-only and hash-chained: every entry commits to the one before it.</p>
        </div>
        <button className="btn btn-primary" onClick={verify} disabled={checking}>
          <Link2 size={16} aria-hidden /> {checking ? 'Verifying…' : 'Verify chain'}
        </button>
      </div>
      <ErrorNote error={error} />

      {report && (
        <section className={`panel verify ${report.ok ? 'verify-ok' : 'verify-bad'}`}>
          <div className="verify-title">
            {report.ok ? <ShieldCheck size={22} aria-hidden /> : <ShieldAlert size={22} aria-hidden />}
            <div>
              <h2>{report.ok ? 'Chain intact' : `Chain broken at entry #${report.first_bad_seq}`}</h2>
              <p className="small">
                {report.ok
                  ? `${report.entries} entries checked · head #${report.head_seq}`
                  : report.reason}
              </p>
            </div>
          </div>
          {report.ok && (
            <div className="small mono muted" title={report.head_hash}>
              head {report.head_hash}
            </div>
          )}
          <p className="small verify-limit">
            <strong>Coverage: internal chain only.</strong> No signed checkpoint is retained yet, so a chain rewritten with
            recomputed hashes would still pass this check. Signed checkpoints kept outside the database close that gap.
          </p>
        </section>
      )}

      {!canRead && (
        <div className="empty">
          <p>Your role can verify the chain but not read its entries. Auditors and supervisors read the trail.</p>
        </div>
      )}

      {canRead && (
        <section className="panel">
          <div className="panel-head">
            <h2>Entries</h2>
            <label className="search">
              <Search size={16} aria-hidden />
              <input placeholder="Filter by action, actor, case" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter entries" />
            </label>
          </div>
          {shown && (
            <div className="table-wrap">
              <table className="table table-dense">
                <thead>
                  <tr>
                    <th className="num">#</th>
                    <th>Time</th>
                    <th>Actor</th>
                    <th>Action</th>
                    <th>Case</th>
                    <th>Details</th>
                    <th>Hash</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((e) => (
                    <tr key={e.seq}>
                      <td className="num mono">{e.seq}</td>
                      <td className="nowrap small">{formatDateTime(e.ts)}</td>
                      <td className="mono small">{e.actor}</td>
                      <td>
                        <span className={`chip ${tone(e.action)}`}>{e.action}</span>
                      </td>
                      <td className="mono small">{e.case_id ?? '—'}</td>
                      <td className="small details">{summarize(e)}</td>
                      <td className="mono small muted" title={e.hash}>
                        {e.hash.slice(0, 10)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!entries && !error && <p className="muted pad">Loading entries…</p>}
        </section>
      )}
    </div>
  )
}
