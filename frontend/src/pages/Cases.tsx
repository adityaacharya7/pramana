import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type CaseSummary } from '../api'
import { useAuth } from '../auth'
import { AccessChip, ErrorNote } from '../components/bits'
import { formatDate } from '../format'

export default function Cases() {
  const { me } = useAuth()
  const navigate = useNavigate()
  const [cases, setCases] = useState<CaseSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')

  useEffect(() => {
    api.cases().then(setCases, (e) => setError(e.message))
  }, [])

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!cases || !needle) return cases
    return cases.filter((c) =>
      [c.id, c.fir_no, c.title, c.city, c.unit, c.complainant, c.station].some((v) => v?.toLowerCase().includes(needle)),
    )
  }, [cases, q])

  const role = me?.user.role
  const noCaseAccess = role === 'AUDITOR' || role === 'ADMIN'

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Cases</h1>
          <p className="muted">
            {noCaseAccess
              ? 'Your role does not open case content.'
              : 'Cases you are a member of' + (role === 'SUPERVISOR' ? ', and every case owned by your unit.' : '.')}
          </p>
        </div>
        {cases && cases.length > 0 && (
          <label className="search">
            <Search size={16} aria-hidden />
            <input placeholder="Search case, FIR, complainant, city" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search cases" />
          </label>
        )}
      </div>
      <ErrorNote error={error} />

      {noCaseAccess && (
        <div className="empty">
          <h2>{role === 'AUDITOR' ? 'Oversight view' : 'Administration view'}</h2>
          <p>
            {role === 'AUDITOR'
              ? 'Auditors read the decision trail and verify its integrity, without opening case files.'
              : 'Administrators manage users, units and roles, with no access to case content.'}
          </p>
          {role === 'AUDITOR' && (
            <Link className="btn btn-primary" to="/audit">
              Open the audit log
            </Link>
          )}
        </div>
      )}

      {shown && shown.length > 0 && (
        <div className="table-wrap">
          <table className="table table-click">
            <thead>
              <tr>
                <th>Case</th>
                <th>Complaint</th>
                <th>Unit</th>
                <th>Registered</th>
                <th className="num">Evidence</th>
                <th>Your access</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((c) => (
                <tr key={c.id} onClick={() => navigate(`/cases/${c.id}`)}>
                  <td>
                    <Link to={`/cases/${c.id}`} className="case-id" onClick={(e) => e.stopPropagation()}>
                      {c.id}
                    </Link>
                    <div className="muted small">FIR {c.fir_no}</div>
                  </td>
                  <td>
                    <div>{c.title}</div>
                    <div className="muted small">{c.complainant}</div>
                  </td>
                  <td>
                    <div>{c.city}</div>
                    <div className="muted small">{c.unit}</div>
                  </td>
                  <td>{formatDate(c.registered_on)}</td>
                  <td className="num">{c.evidence_count}</td>
                  <td>
                    <AccessChip access={c.my_access} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {shown && shown.length === 0 && !noCaseAccess && <p className="muted">{q ? 'No case matches that search.' : 'No cases yet.'}</p>}
      {!cases && !error && <p className="muted">Loading cases…</p>}
    </div>
  )
}
