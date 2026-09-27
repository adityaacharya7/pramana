import { EyeOff, Fingerprint, Link2, Lock } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api3, type MatchRow, type MoProposal } from '../api3'
import { ErrorNote } from './bits'
import { useAsk, useToast } from './ui'

export default function CrossCaseTab({ caseId }: { caseId: string }) {
  const [matches, setMatches] = useState<MatchRow[] | null>(null)
  const [mo, setMo] = useState<Awaited<ReturnType<typeof api3.moMatches>> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const ask = useAsk()
  const toast = useToast()

  const load = useCallback(() => {
    api3.matches(caseId).then((r) => setMatches(r.matches), (e) => setError(e.message))
    api3.moMatches(caseId).then(setMo, (e) => setError(e.message))
  }, [caseId])
  useEffect(load, [load])

  async function request(token: string, unit: string) {
    const reason = await ask({
      title: `Request access — ${unit}`,
      body: 'Your reason is logged and shown to that unit’s supervisory officer, who decides the request. You see nothing about the case until it is approved.',
      confirm: 'Send request',
      minLength: 10,
      placeholder: 'e.g. Same beneficiary account received money from a complainant in my case',
    })
    if (!reason) return
    try {
      await api3.requestAccess(token, reason)
      toast(`Access requested from ${unit}.`)
      setNote(`Access requested from ${unit}. Their supervisor decides it.`)
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed.')
    }
  }

  return (
    <div className="review">
      <ErrorNote error={error} />
      {note && <div className="note note-ok">{note}</div>}
      <section className="panel">
        <div className="panel-head">
          <h2>
            <Link2 size={17} aria-hidden /> Identifiers seen in other cases
          </h2>
          <span className="muted small">
            <EyeOff size={12} aria-hidden /> A match in a case outside your scope shows only its owning unit, until access is granted.
          </span>
        </div>
        {matches && matches.length === 0 && <p className="muted pad">No identifier from this case appears in another case.</p>}
        {matches && matches.length > 0 && (
          <div className="table-wrap"><table className="table table-dense table-hover">
            <thead><tr><th>Identifier</th><th>Cases you can see</th><th>Outside your scope</th></tr></thead>
            <tbody>
              {matches.map((m) => (
                <tr key={m.entity_id}>
                  <td>
                    <span className="muted small">{m.type.replace('_', ' ')}</span> <code>{m.value}</code>
                    {m.names_seen.length > 0 && <div className="muted small">{m.names_seen.slice(0, 2).join(', ')}</div>}
                    {m.likely_hub && <div className="muted small">Seen in {m.total_cases} cases: likely a biller or merchant</div>}
                  </td>
                  <td className="small">
                    {m.visible_cases.map((c) => (
                      <div key={c.id}><Link to={`/cases/${c.id}`} className="case-id">{c.id}</Link> {c.title}</div>
                    ))}
                  </td>
                  <td className="small">
                    {Object.entries(
                      m.hidden.reduce<Record<string, typeof m.hidden>>((acc, h) => ({ ...acc, [h.unit]: [...(acc[h.unit] ?? []), h] }), {}),
                    ).map(([unit, hs]) => (
                      <div key={unit} className="hidden-match">
                        <Lock size={12} aria-hidden /> {hs.length} match{hs.length === 1 ? '' : 'es'} in case{hs.length === 1 ? '' : 's'} of{' '}
                        <strong>{unit}</strong>
                        {!m.likely_hub &&
                          hs.map((h, i) =>
                            h.request_status ? (
                              <span key={i} className="chip">{h.request_status.toLowerCase()}</span>
                            ) : (
                              <button key={i} className="btn btn-small btn-ghost" onClick={() => request(h.token, unit)}>
                                Request access{hs.length > 1 ? ` (${i + 1})` : ''}
                              </button>
                            ),
                          )}
                      </div>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>
            <Fingerprint size={17} aria-hidden /> Similar method (MO)
          </h2>
          <span className="muted small">{mo?.note}</span>
        </div>
        {mo?.attributes && (
          <div className="issue-body small">
            This complaint's method: {Object.entries(mo.attributes).map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v.join(', ')}`).join(' · ')}
          </div>
        )}
        {mo && mo.proposals.length === 0 && <p className="muted pad">No other complaint to compare.</p>}
        {mo && mo.proposals.length > 0 && (
          <div className="table-wrap"><table className="table table-dense table-hover">
            <thead><tr><th>Case</th><th className="num">Score</th><th>Matching attributes</th><th>Proposed for comparison</th><th /></tr></thead>
            <tbody>
              {mo.proposals.slice(0, 12).map((p) => (
                <MoRow key={p.case_id} p={p} open={open === p.case_id} onToggle={() => setOpen(open === p.case_id ? null : p.case_id)} />
              ))}
            </tbody>
          </table></div>
        )}
        {mo && <p className="muted small pad">Method: {mo.method}. Score = 0.7 × attribute-profile similarity + 0.3 × text similarity; not a probability of linkage.</p>}
      </section>
    </div>
  )
}

function MoRow({ p, open, onToggle }: { p: MoProposal; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr className={p.proposed ? undefined : 'row-muted'}>
        <td><Link to={`/cases/${p.case_id}`} className="case-id">{p.case_id}</Link></td>
        <td className="num">{p.score.toFixed(2)}</td>
        <td className="small">{p.matching_attribute_types.map((a) => a.replace(/_/g, ' ')).join(', ') || '—'}</td>
        <td>{p.proposed ? <span className="chip chip-warn">Compare</span> : <span className="muted small">below threshold</span>}</td>
        <td className="actions"><button className="btn btn-small btn-ghost" onClick={onToggle}>{open ? 'Hide' : 'Side by side'}</button></td>
      </tr>
      {open && (
        <tr>
          <td colSpan={5}>
            <div className="side-by-side">
              <div>
                <h4>This case — {p.this_file.filename}</h4>
                {p.this_passages.map((x, i) => <p key={i} className="small"><strong>{x.value}</strong>: …{x.context}…</p>)}
              </div>
              <div>
                <h4>{p.case_id} — {p.other_file.filename}</h4>
                {p.other_passages.map((x, i) => <p key={i} className="small"><strong>{x.value}</strong>: …{x.context}…</p>)}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
