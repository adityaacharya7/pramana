import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import Shell from './components/Shell'
import Wordmark, { Seal } from './components/Wordmark'
import AccessRequests from './pages/AccessRequests'
import AuditLog from './pages/AuditLog'
import CaseView from './pages/CaseView'
import Cases from './pages/Cases'
import LeadPage from './pages/LeadPage'
import Login from './pages/Login'
import VerifyBundle from './pages/VerifyBundle'

function RequireSession({ children }: { children: ReactNode }) {
  const { me } = useAuth()
  const location = useLocation()
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}

export default function App() {
  const { ready, backendDown } = useAuth()
  if (!ready)
    return (
      <div className="boot">
        <div className="boot-loading">
          <Seal size={48} />
          <span>Loading PRAMANA…</span>
        </div>
      </div>
    )
  if (backendDown) {
    return (
      <div className="boot">
        <div className="boot-card">
          <Wordmark />
          <h1>PRAMANA is not reachable</h1>
          <p>The API server did not respond. Start the backend, then reload this page.</p>
          <pre>python -m pramana.cli serve</pre>
        </div>
      </div>
    )
  }
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <Shell>
            <Login />
          </Shell>
        }
      />
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
        <Route path="/roles" element={<Login isSwitcher />} />
        <Route path="/select-role" element={<Login isSwitcher />} />
      </Route>
      <Route path="*" element={<Navigate to="/cases" replace />} />
    </Routes>
  )
}
