import { ArrowLeftRight, Banknote, Landmark, Layers, LogOut, Users } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api3, type Method, type MoneyTrail } from '../api3'
import { formatDateTime, formatINR } from '../format'
import { ErrorNote } from './bits'
import FlowDiagram, { CASE_COLORS } from './FlowDiagram'
import { Card, Metric, Skeleton } from './ui'

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
  if (!data || !t)
    return (
      <Card>
        <Skeleton lines={6} />
      </Card>
    )

  const totals = Object.values(t.by_case).reduce(
    (a, v) => ({ loss: a.loss + v.loss, held: a.held + v.held, exited: a.exited + v.exited, missing: a.missing + v.missing_statement }),
    { loss: 0, held: 0, exited: 0, missing: 0 },
  )
  const methodSwitch = (
    <div className="seg" role="tablist" aria-label="Attribution method">
      {METHODS.map((m) => (
        <button key={m.id} role="tab" aria-selected={method === m.id} className={`seg-btn${method === m.id ? ' seg-on' : ''}`} onClick={() => setMethod(m.id)}>
          {m.label}
        </button>
      ))}
    </div>
  )

  return (
    <div className="review">
      <div className="metrics">
        <Metric label="Victim loss" value={formatINR(totals.loss)} hint={`${t.seeds.length} payment${t.seeds.length === 1 ? '' : 's'} across ${data.cases.length} case${data.cases.length === 1 ? '' : 's'}`} />
        <Metric label="Still held" value={formatINR(totals.held)} hint="at accounts with a statement" tone="ok" />
        <Metric label="Left the trail" value={formatINR(totals.exited)} hint="cash, crypto, merchant payments" tone="bad" />
        <Metric label="Onward unknown" value={formatINR(totals.missing)} hint="at accounts with no statement" tone={totals.missing > 0 ? 'warn' : undefined} />
      </div>

      <Card
        icon={<ArrowLeftRight size={17} />}
        title="Money trail"
        subtitle={`Cases traced together: ${data.cases.join(', ')}`}
        actions={methodSwitch}
        flush
      >
        <div className="issue-body" style={{ paddingBottom: 4 }}>
          <p className="small">{t.method_text}</p>
          {!t.reconciles && (
            <div className="note note-bad small">
              Some records do not reconcile; figures for these accounts are uncertain:{' '}
              {t.issues.map((i) => `${label(i.party)} (${i.kind.replace(/_/g, ' ')})`).join('; ')}
            </div>
          )}
        </div>
        <FlowDiagram t={t} label={label} cases={data.cases} />
        <div className="flow-legend">
          {data.cases.map((c, i) => (
            <span key={c}>
              <i style={{ background: CASE_COLORS[i % CASE_COLORS.length], borderColor: CASE_COLORS[i % CASE_COLORS.length] }} /> {c} money
            </span>
          ))}
          <span>
            <i style={{ background: 'var(--accent-soft)', borderColor: 'var(--accent)' }} /> holds funds
          </span>
          <span>
            <i style={{ background: 'var(--bad-bg)', borderColor: 'var(--bad)' }} /> exit point
          </span>
          <span className="muted">{data.note}</span>
        </div>
      </Card>

      <div className="stat-row">
        {Object.entries(t.by_case).map(([c, v]) => (
          <div key={c} className="stat" style={{ borderTop: `3px solid ${CASE_COLORS[Math.max(data.cases.indexOf(c), 0) % CASE_COLORS.length]}` }}>
            <span className="stat-l">{c} · victim loss</span>
            <span className="stat-n">{formatINR(v.loss)}</span>
            <span className="stat-l">
              held {formatINR(v.held)} · left the trail {formatINR(v.exited)}
              {v.missing_statement > 0 && ` · no statement ${formatINR(v.missing_statement)}`}
            </span>
          </div>
        ))}
      </div>

      <Card icon={<Users size={17} />} title="Victims’ payments" flush>
        <div className="table-wrap">
          <table className="table table-dense table-hover">
            <thead><tr><th>When</th><th>Case</th><th>From</th><th>To</th><th className="num">Amount</th></tr></thead>
            <tbody>
              {t.seeds.map((s) => (
                <tr key={s.event}>
                  <td className="nowrap small">{formatDateTime(s.ts)}</td>
                  <td className="case-id">{s.case_id}</td>
                  <td className="small">{label(s.victim)}</td>
                  <td className="small">{label(s.to)}</td>
                  <td className="num">{formatINR(s.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card icon={<Landmark size={17} />} title="Where the money is estimated to be" subtitle="Each victim rupee is counted at exactly one place" flush>
        <div className="table-wrap">
          <table className="table table-dense table-hover">
            <thead><tr><th>Account</th><th>From case</th><th className="num">Estimate ({method})</th><th className="num">Range across methods</th><th>As of</th></tr></thead>
            <tbody>
              {t.holdings.map((h, i) => {
                const s = data.trail.spread[h.party]
                return (
                  <tr key={i} className={h.uncertain ? 'row-bad' : undefined}>
                    <td className="small">{label(h.party)} <span className="chip">layer {h.layer}</span></td>
                    <td className="case-id">{h.tag.split(':')[1]}</td>
                    <td className="num">{h.uncertain ? <span className="bad">insufficient evidence</span> : <strong>{formatINR(h.amount)}</strong>}</td>
                    <td className="num small muted">{s ? `${formatINR(s.min)} – ${formatINR(s.max)}` : ''}</td>
                    <td className="small">{h.has_statement ? `${h.as_of?.slice(0, 10)} (statement end)` : <span className="chip chip-warn">no statement — onward movement unknown</span>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Card icon={<LogOut size={17} />} title="Exit points" subtitle="Money that left the banking trail" flush>
        <div className="table-wrap">
          <table className="table table-dense table-hover">
            <thead><tr><th>When</th><th>From</th><th>How</th><th className="num">Victim share ({method})</th></tr></thead>
            <tbody>
              {t.exits.map((x, i) => (
                <tr key={i}>
                  <td className="nowrap small">{formatDateTime(x.ts)}</td>
                  <td className="small">{label(x.party)}</td>
                  <td className="small">
                    <span className={`chip ${x.kind.startsWith('cash') ? 'chip-bad' : x.kind.startsWith('crypto') ? 'chip-warn' : ''}`}>
                      {x.kind.startsWith('cash') && <Banknote size={12} aria-hidden />}
                      {x.kind}
                    </span>
                    {x.kind.startsWith('merchant') && <span className="muted"> purpose unverified</span>} → {label(x.to)}
                  </td>
                  <td className="num">{formatINR(x.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card icon={<Layers size={17} />} title="Layers" subtitle="Hops away from the victim’s account">
        {layers.map(([n, flows]) => (
          <div key={n}>
            <h4 style={{ marginBottom: 4 }}>Layer {n}</h4>
            <ul className="bullets">
              {flows.map((f, i) => (
                <li key={i} className="small">
                  {formatDateTime(f.ts)} · {label(f.from)} → {label(f.to)} · <strong>{formatINR(f.amount)}</strong> of case {f.tag.split(':')[1]} money
                  {f.exit && <span className="muted"> ({f.exit})</span>}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </Card>
    </div>
  )
}
