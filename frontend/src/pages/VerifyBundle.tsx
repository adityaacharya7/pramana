import { CheckCircle2, FileUp, XCircle } from 'lucide-react'
import { useState } from 'react'
import { api3, type BundleReport } from '../api3'
import { ErrorNote } from '../components/bits'

export default function VerifyBundle() {
  const [report, setReport] = useState<BundleReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState<string | null>(null)

  async function onFile(f: File | undefined) {
    if (!f) return
    setBusy(true)
    setError(null)
    setReport(null)
    setName(f.name)
    try {
      setReport(await api3.verifyBundle(JSON.parse(await f.text())))
    } catch (e) {
      setError(e instanceof SyntaxError ? 'That file is not JSON.' : e instanceof Error ? e.message : 'Verification failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Verify a handover pack</h1>
          <p className="muted">
            Re-runs the analysis from the bundle alone and compares every finding and estimate with what was exported, then checks the
            hashes and the signed audit-log checkpoint. Offline equivalent: <code>python -m pramana.cli verify-bundle bundle.json</code>.
          </p>
        </div>
      </div>
      <label className="dropzone">
        <FileUp size={22} aria-hidden />
        <span>{busy ? 'Re-running…' : 'Choose a PRAMANA handover bundle (.json)'}</span>
        <input type="file" accept=".json,application/json" hidden onChange={(e) => onFile(e.target.files?.[0])} />
      </label>
      <ErrorNote error={error} />
      {report && (
        <section className={`panel verify ${report.ok ? 'verify-ok' : 'verify-bad'}`}>
          <div className="verify-title">
            {report.ok ? <CheckCircle2 size={22} aria-hidden /> : <XCircle size={22} aria-hidden />}
            <div>
              <h2>{report.ok ? 'Reproduced' : 'Not reproduced'}</h2>
              <p className="small">{name} · lead {report.lead}</p>
            </div>
          </div>
          <ul className="checklist">
            {report.checks.map((c) => (
              <li key={c.check} className={c.ok ? 'ok' : 'bad'}>
                {c.ok ? <CheckCircle2 size={14} aria-hidden /> : <XCircle size={14} aria-hidden />} <strong>{c.check}</strong>
                <span className="small"> — {c.detail}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
