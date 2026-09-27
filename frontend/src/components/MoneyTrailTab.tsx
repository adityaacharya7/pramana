import { useEffect, useMemo, useState } from 'react'
import { api3, type Method, type MoneyTrail } from '../api3'
import { formatDateTime, formatINR } from '../format'
import { ErrorNote } from './bits'

const METHODS: { id: Method; label: string }[] = [
  { id: 'fifo', label: 'FIFO' },
  { id: 'lifo', label: 'LIFO' },
  { id: 'prorata', label: 'Pro-rata' },
]

export default function MoneyTrailTab({ caseId }: { caseId: string }) {
  const [scope, setScope] = useState<string[] | null>(null)
  const [data, setData] = useState<MoneyTrail | null>(null)
  const [method, setMethod] = useState<Method>('prorata')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api3.analysisScope(caseId).then((s) => setScope(s.suggested), () => setScope([caseId]))
  }, [caseId])
  useEffect(() => {
    if (scope) api3.moneyTrail(caseId, scope).then(setData, (e) => setError(e.message))
  }, [caseId, scope])

  const t = data?.trail.methods[method]
  const label = (p: string) => data?.labels[p] ?? p
  const layers = useMemo(() => {
    if (!t) return []
    const byLayer = new Map<number, typeof t.flows>()
    for (const f of t.flows) byLayer.set(f.layer, [...(byLayer.get(f.layer) ?? []), f])
    return [...byLayer.entries()].sort((a, b) => a[0] - b[0])
  }, [t])

  if (error) return <ErrorNote error={error} />
  if (!data || !t) return <p className="muted pad">Tracing…</p>

  return (
    <div className="review">
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Money trail</h2>
            <span className="muted small">Cases traced together: {data.cases.join(', ')}</span>
          </div>
          <div className="seg" role="tablist" aria-label="Attribution method">
            {METHODS.map((m) => (
              <button key={m.id} className={`seg-btn${method === m.id ? ' seg-on' : ''}`} onClick={() => setMethod(m.id)}>
                {m.label}
              </button>
            ))}
          </div>
        </div>
        <div className="issue-body">
          <p className="small">{t.method_text}</p>
          <p className="muted small">{data.note}</p>
          {!t.reconciles && (
            <div className="note note-bad small">
              Some records do not reconcile; figures for these accounts are uncertain: {t.issues.map((i) => `${label(i.party)} (${i.kind.replace(/_/g, ' ')})`).join('; ')}
            </div>
          )}
        </div>
      </section>

      <div className="stat-row">
        {Object.entries(t.by_case).map(([c, v]) => (
          <div key={c} className="stat">
            <span className="stat-l">{c} · victim loss</span>
            <span className="stat-n">{formatINR(v.loss)}</span>
            <span className="stat-l">
              held {formatINR(v.held)} · left the trail {formatINR(v.exited)}
              {v.missing_statement > 0 && ` · at accounts with no statement ${formatINR(v.missing_statement)}`}
            </span>
          </div>
        ))}
      </div>

      <section className="panel">
        <div className="panel-head"><h2>Victims' payments</h2></div>
        <table className="table table-dense">
          <thead><tr><th>When</th><th>Case</th><th>From</th><th>To</th><th className="num">Amount</th></tr></thead>
          <tbody>
            {t.seeds.map((s) => (
              <tr key={s.event}>
                <td className="nowrap small">{formatDateTime(s.ts)}</td>
                <td>{s.case_id}</td>
                <td className="small">{label(s.victim)}</td>
                <td className="small">{label(s.to)}</td>
                <td className="num">{formatINR(s.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Where the money is estimated to be</h2>
          <span className="muted small">Each victim rupee is counted at exactly one place</span>
        </div>
        <table className="table table-dense">
          <thead><tr><th>Account</th><th>From case</th><th className="num">Estimate ({method})</th><th className="num">Range across methods</th><th>As of</th></tr></thead>
          <tbody>
            {t.holdings.map((h, i) => {
              const s = data.trail.spread[h.party]
              return (
                <tr key={i} className={h.uncertain ? 'row-bad' : undefined}>
                  <td className="small">{label(h.party)} <span className="muted">layer {h.layer}</span></td>
                  <td>{h.tag.split(':')[1]}</td>
                  <td className="num">{h.uncertain ? <span className="bad">insufficient evidence</span> : formatINR(h.amount)}</td>
                  <td className="num small">{s ? `${formatINR(s.min)} – ${formatINR(s.max)}` : ''}</td>
                  <td className="small">{h.has_statement ? `${h.as_of?.slice(0, 10)} (statement end)` : 'no statement — onward movement unknown'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <div className="panel-head"><h2>Exit points</h2><span className="muted small">Money that left the banking trail</span></div>
        <table className="table table-dense">
          <thead><tr><th>When</th><th>From</th><th>How</th><th className="num">Victim share ({method})</th></tr></thead>
          <tbody>
            {t.exits.map((x, i) => (
              <tr key={i}>
                <td className="nowrap small">{formatDateTime(x.ts)}</td>
                <td className="small">{label(x.party)}</td>
                <td className="small">{x.kind}{x.kind.startsWith('merchant') && ' (purpose unverified)'} → {label(x.to)}</td>
                <td className="num">{formatINR(x.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <div className="panel-head"><h2>Layers</h2><span className="muted small">Hops away from the victim's account</span></div>
        <div className="issue-body">
          {layers.map(([n, flows]) => (
            <div key={n}>
              <h4>Layer {n}</h4>
              <ul className="bullets">
                {flows.map((f, i) => (
                  <li key={i} className="small">
                    {formatDateTime(f.ts)} · {label(f.from)} → {label(f.to)} · {formatINR(f.amount)} of case {f.tag.split(':')[1]} money
                    {f.exit && <span className="muted"> ({f.exit})</span>}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
