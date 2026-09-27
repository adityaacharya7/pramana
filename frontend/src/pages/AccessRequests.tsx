import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api3, type AccessRequestRow } from '../api3'
import { useAuth } from '../auth'
import { ErrorNote } from '../components/bits'
import { formatDateTime } from '../format'

export default function AccessRequests() {
  const { me } = useAuth()
  const [data, setData] = useState<{ mine: AccessRequestRow[]; to_decide: AccessRequestRow[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(() => api3.accessRequests().then(setData, (e) => setError(e.message)), [])
  useEffect(() => {
    load()
  }, [load])

  async function decide(id: string, decision: 'approve' | 'reject') {
    const reason = window.prompt(`Reason to ${decision} (logged):`)
    if (!reason || reason.trim().length < 3) return
    try {
      await api3.decideAccess(id, decision, reason.trim())
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed.')
    }
  }

  const Row = ({ r, deciding }: { r: AccessRequestRow; deciding: boolean }) => (
    <tr>
      <td className="small nowrap">{formatDateTime(r.created_at)}</td>
      <td className="small">
        {r.requester.name} <span className="muted">({r.requester.unit})</span>
      </td>
      <td className="small">
        {r.case_id ? <Link to={`/cases/${r.case_id}`} className="case-id">{r.case_id}</Link> : <span className="muted">a case in {r.unit}</span>}
        {r.case_title && <div className="muted">{r.case_title}</div>}
      </td>
      <td className="small details">{r.reason}</td>
      <td>
        <span className={`chip ${r.status === 'APPROVED' ? 'chip-evidence' : r.status === 'REJECTED' ? 'chip-bad' : 'chip-warn'}`}>{r.status.toLowerCase()}</span>
        {r.decided_by && <div className="muted small">by {r.decided_by}</div>}
      </td>
      <td className="actions">
        {deciding && r.status === 'PENDING' && (
          <>
            <button className="btn btn-small btn-primary" onClick={() => decide(r.id, 'approve')}>Approve</button>
            <button className="btn btn-small btn-ghost" onClick={() => decide(r.id, 'reject')}>Reject</button>
          </>
        )}
      </td>
    </tr>
  )

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Access requests</h1>
          <p className="muted">
            A match in a case outside your scope shows only the owning unit. Access is granted by that unit's supervisory officer, and
            every request and decision is logged.
          </p>
        </div>
      </div>
      <ErrorNote error={error} />
      {me?.user.role === 'SUPERVISOR' && (
        <section className="panel">
          <div className="panel-head"><h2>Requests for your unit's cases</h2></div>
          {data && data.to_decide.length === 0 && <p className="muted pad">None.</p>}
          {data && data.to_decide.length > 0 && (
            <table className="table table-dense">
              <thead><tr><th>When</th><th>Requested by</th><th>Case</th><th>Reason</th><th>Status</th><th /></tr></thead>
              <tbody>{data.to_decide.map((r) => <Row key={r.id} r={r} deciding />)}</tbody>
            </table>
          )}
        </section>
      )}
      <section className="panel">
        <div className="panel-head"><h2>Your requests</h2></div>
        {data && data.mine.length === 0 && <p className="muted pad">You have not requested access to any case. Requests start from the Cross-case tab of a case.</p>}
        {data && data.mine.length > 0 && (
          <table className="table table-dense">
            <thead><tr><th>When</th><th>Requested by</th><th>Case</th><th>Reason</th><th>Status</th><th /></tr></thead>
            <tbody>{data.mine.map((r) => <Row key={r.id} r={r} deciding={false} />)}</tbody>
          </table>
        )}
      </section>
    </div>
  )
}
