import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api3, type AccessRequestRow } from '../api3'
import { useAuth } from '../auth'
import { ErrorNote } from '../components/bits'
import { Avatar, EmptyState, PageHeader, useAsk, useToast } from '../components/ui'
import { Inbox, KeyRound, Send } from 'lucide-react'
import { formatDateTime } from '../format'

export default function AccessRequests() {
  const { me } = useAuth()
  const ask = useAsk()
  const toast = useToast()
  const [data, setData] = useState<{ mine: AccessRequestRow[]; to_decide: AccessRequestRow[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(() => api3.accessRequests().then(setData, (e) => setError(e.message)), [])
  useEffect(() => {
    load()
  }, [load])

  async function decide(id: string, decision: 'approve' | 'reject') {
    const reason = await ask({
      title: decision === 'approve' ? 'Approve access request' : 'Reject access request',
      body: decision === 'approve' ? 'The requester becomes a member of the case and can open its evidence.' : 'The requester is told the request was declined.',
      confirm: decision === 'approve' ? 'Approve' : 'Reject',
      tone: decision === 'approve' ? 'primary' : 'danger',
    })
    if (!reason) return
    try {
      await api3.decideAccess(id, decision, reason)
      toast(decision === 'approve' ? 'Access granted and logged.' : 'Request rejected and logged.')
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed.')
    }
  }

  const Row = ({ r, deciding }: { r: AccessRequestRow; deciding: boolean }) => (
    <tr>
      <td className="small nowrap">{formatDateTime(r.created_at)}</td>
      <td className="small">
        <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
          <Avatar name={r.requester.name} size={26} />
          <span>
            {r.requester.name}
            <div className="muted">{r.requester.unit}</div>
          </span>
        </span>
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
      <PageHeader
        eyebrow="Coordination"
        title="Access requests"
        subtitle="A match in a case outside your scope shows only the owning unit. Access is granted by that unit’s supervisory officer, and every request and decision is logged."
      />
      <ErrorNote error={error} />
      {me?.user.role === 'SUPERVISOR' && (
        <section className="panel">
          <div className="panel-head">
            <h2>
              <Inbox size={17} aria-hidden /> Requests for your unit’s cases
            </h2>
            {data && <span className="chip chip-warn">{data.to_decide.filter((r) => r.status === 'PENDING').length} pending</span>}
          </div>
          {data && data.to_decide.length === 0 && (
            <EmptyState icon={<Inbox size={22} />} title="Nothing to decide">
              Requests from other units for your unit’s cases will appear here.
            </EmptyState>
          )}
          {data && data.to_decide.length > 0 && (
            <div className="table-wrap"><table className="table table-dense table-hover">
              <thead><tr><th>When</th><th>Requested by</th><th>Case</th><th>Reason</th><th>Status</th><th /></tr></thead>
              <tbody>{data.to_decide.map((r) => <Row key={r.id} r={r} deciding />)}</tbody>
            </table></div>
          )}
        </section>
      )}
      <section className="panel">
        <div className="panel-head">
          <h2>
            <Send size={16} aria-hidden /> Your requests
          </h2>
        </div>
        {data && data.mine.length === 0 && (
          <EmptyState icon={<KeyRound size={22} />} title="No requests yet">
            Requests start from the Cross-case tab of a case, when an identifier also appears in a case outside your scope.
          </EmptyState>
        )}
        {data && data.mine.length > 0 && (
          <div className="table-wrap"><table className="table table-dense table-hover">
            <thead><tr><th>When</th><th>Requested by</th><th>Case</th><th>Reason</th><th>Status</th><th /></tr></thead>
            <tbody>{data.mine.map((r) => <Row key={r.id} r={r} deciding={false} />)}</tbody>
          </table></div>
        )}
      </section>
    </div>
  )
}
