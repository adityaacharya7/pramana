import { ArrowRight, FlaskConical } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { api, ApiError, type User } from '../api'
import { useAuth } from '../auth'
import { ErrorNote } from '../components/bits'
import Wordmark from '../components/Wordmark'

const GROUPS: { title: string; roles: User['role'][] }[] = [
  { title: 'Investigating Officers', roles: ['IO'] },
  { title: 'Intelligence Analyst', roles: ['ANALYST'] },
  { title: 'Supervisory Officers', roles: ['SUPERVISOR'] },
  { title: 'Oversight and administration', roles: ['AUDITOR', 'ADMIN'] },
]

export default function Login() {
  const { me, build, signIn } = useAuth()
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from ?? '/cases'
  if (me) return <Navigate to={from} replace />

  const done = () => navigate(from, { replace: true })
  return (
    <div className="login">
      <section className="login-brand">
        <Wordmark large />
        <p className="login-tagline">Find the Connection. Show the Evidence. Test the Lead.</p>
        <p className="login-lede">
          An investigation-review workspace. The system proposes; the officer decides. Every lead carries the evidence,
          rule and assumptions behind it, so it can be inspected, challenged and handed over.
        </p>
        <ul className="login-points">
          <li>
            <strong>Evidence Receipt</strong> source passage, rule and version, supporting and conflicting records,
            unknowns, next step
          </li>
          <li>
            <strong>Challenge Mode</strong> set evidence aside in a scenario copy and see exactly what changes
          </li>
          <li>
            <strong>Reproducible handover</strong> another officer can re-run the same analysis and re-check every
            hash
          </li>
        </ul>
      </section>
      <section className="login-panel">{build === 'demo' ? <RoleSwitcher onDone={done} signIn={signIn} /> : <PasswordForm onDone={done} signIn={signIn} />}</section>
    </div>
  )
}

type SignIn = ReturnType<typeof useAuth>['signIn']

function RoleSwitcher({ onDone, signIn }: { onDone: () => void; signIn: SignIn }) {
  const [users, setUsers] = useState<User[] | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.demoUsers().then(setUsers, (e) => setError(e.message))
  }, [])

  async function choose(username: string) {
    setBusy(username)
    setError(null)
    try {
      await signIn(await api.demoSession(username))
      onDone()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start the session.')
      setBusy(null)
    }
  }

  return (
    <div className="switcher">
      <div className="demo-banner">
        <FlaskConical size={18} aria-hidden />
        <div>
          <strong>Synthetic demo build</strong>
          <span>Isolated database. Every person, number and account is invented. Choose a role to continue.</span>
        </div>
      </div>
      <ErrorNote error={error} />
      {!users && !error && <p className="muted">Loading roles…</p>}
      {users &&
        GROUPS.map((g) => {
          const members = users.filter((u) => g.roles.includes(u.role))
          if (!members.length) return null
          return (
            <div key={g.title} className="switcher-group">
              <h2>{g.title}</h2>
              <div className="switcher-grid">
                {members.map((u) => (
                  <button key={u.username} className="role-card" disabled={busy !== null} onClick={() => choose(u.username)}>
                    <span className="role-card-name">{u.name}</span>
                    <span className="role-card-meta">
                      {u.role_label} · {u.unit}
                    </span>
                    <code className="role-card-user">{busy === u.username ? 'signing in…' : u.username}</code>
                  </button>
                ))}
              </div>
            </div>
          )
        })}
    </div>
  )
}

function PasswordForm({ onDone, signIn }: { onDone: () => void; signIn: SignIn }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [totp, setTotp] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signIn(await api.login(username.trim(), password, totp.trim()))
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sign-in failed.')
      setTotp('')
      setBusy(false)
    }
  }

  return (
    <form className="login-form" onSubmit={submit}>
      <h2>Sign in</h2>
      <label>
        Username
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required autoFocus />
      </label>
      <label>
        Password
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
      </label>
      <label>
        One-time code
        <input
          value={totp}
          onChange={(e) => setTotp(e.target.value.replace(/\D/g, '').slice(0, 6))}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder="6-digit code from your authenticator"
          pattern="\d{6}"
          required
        />
      </label>
      <ErrorNote error={error} />
      <button className="btn btn-primary" disabled={busy}>
        {busy ? 'Signing in…' : 'Sign in'} <ArrowRight size={16} aria-hidden />
      </button>
      <p className="muted small">Every sign-in attempt, successful or not, is written to the audit log.</p>
    </form>
  )
}
