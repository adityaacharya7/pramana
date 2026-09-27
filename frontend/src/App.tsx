import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import Shell from './components/Shell'
import AuditLog from './pages/AuditLog'
import CaseView from './pages/CaseView'
import Cases from './pages/Cases'
import Login from './pages/Login'
import AccessRequests from './pages/AccessRequests'
import LeadPage from './pages/LeadPage'
import VerifyBundle from './pages/VerifyBundle'

function RequireSession({ children }: { children: ReactNode }) {
  const { me } = useAuth()
  const location = useLocation()
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}

export default function App() {
  const { ready, backendDown } = useAuth()
  if (!ready) return <div className="boot">Loading PRAMANA…</div>
  if (backendDown) {
    return (
      <div className="boot">
        <div className="boot-card">
          <h1>PRAMANA is not reachable</h1>
          <p>The API server did not respond. Start the backend, then reload this page.</p>
          <pre>python -m pramana.cli serve --demo</pre>
        </div>
      </div>
    )
  }
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireSession>
            <Shell />
          </RequireSession>
        }
      >
        <Route path="/cases" element={<Cases />} />
        <Route path="/cases/:caseId" element={<CaseView />} />
        <Route path="/cases/:caseId/:tab" element={<CaseView />} />
        <Route path="/audit" element={<AuditLog />} />
        <Route path="/leads/:leadId" element={<LeadPage />} />
        <Route path="/access" element={<AccessRequests />} />
        <Route path="/verify" element={<VerifyBundle />} />
      </Route>
      <Route path="*" element={<Navigate to="/cases" replace />} />
    </Routes>
  )
}
