import { Download, Link2, ScrollText, Search, ShieldAlert, ShieldCheck, Upload } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, type LedgerEntry, type LedgerReport } from '../api'
import { api3 } from '../api3'
import { useAuth } from '../auth'
import { ErrorNote } from '../components/bits'
import { formatDateTime, shortHash } from '../format'
import { Card, EmptyState, PageHeader, Skeleton } from '../components/ui'

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

  async function downloadCheckpoint() {
    try {
      const r = await api3.checkpoint()
      if (!r.checkpoint) {
        setError('No signed checkpoint has been retained yet (one is taken every 50 entries and at approvals and exports).')
        return
      }
      const blob = new Blob([JSON.stringify({ ...r.checkpoint, trusted_public_key: r.trusted_public_key }, null, 2)], { type: 'application/json' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `pramana-checkpoint-${r.checkpoint.seq}.json`
      a.click()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed.')
    }
  }

  async function verifyFile(f: File | undefined) {
    if (!f) return
    setChecking(true)
    setError(null)
    try {
      setReport(await api3.verifyWithCheckpoint(JSON.parse(await f.text())))
      loadEntries()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Verification failed.')
    } finally {
      setChecking(false)
    }
  }

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
      <PageHeader
        eyebrow="Integrity"
        title="Audit log"
        subtitle="Append-only and hash-chained: every entry commits to the one before it. Signed checkpoints let you prove nothing was rewritten."
        actions={
          <>
            <button className="btn" onClick={downloadCheckpoint}>
              <Download size={15} aria-hidden /> Signed checkpoint
            </button>
            <label className="btn">
              <Upload size={15} aria-hidden /> Verify against checkpoint
              <input type="file" accept=".json" hidden onChange={(e) => verifyFile(e.target.files?.[0])} />
            </label>
            <button className="btn btn-primary" onClick={verify} disabled={checking}>
              <Link2 size={15} aria-hidden /> {checking ? 'Verifying…' : 'Verify chain'}
            </button>
          </>
        }
      />
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
            <strong>Coverage: {report.checked_against}.</strong> {report.limitation}
          </p>
        </section>
      )}

      {!canRead && (
        <Card>
          <EmptyState icon={<ShieldCheck size={22} />} title="Entries are not visible to your role">
            Your role can verify the chain but not read its entries. Auditors and supervisors read the trail.
          </EmptyState>
        </Card>
      )}

      {canRead && (
        <section className="panel">
          <div className="panel-head">
            <h2>
              <ScrollText size={17} aria-hidden /> Entries {entries && <span className="chip">{shown?.length ?? 0}</span>}
            </h2>
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
          {!entries && !error && <Skeleton lines={6} />}
        </section>
      )}
    </div>
  )
}
