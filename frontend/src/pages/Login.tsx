import {
  ArrowRight,
  BarChart2,
  ChevronRight,
  KeyRound,
  Lock,
  MapPin,
  Settings,
  Shield,
  Users,
} from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api, ApiError, type User } from '../api'
import { useAuth } from '../auth'
import { ErrorNote } from '../components/bits'
import { PramanaLogo } from '../components/Emblems'

interface RoleGroupConfig {
  titleEn: string
  titleHi: string
  icon: typeof Shield
  roleKeys: User['role'][]
}

const ROLE_GROUPS: RoleGroupConfig[] = [
  {
    titleEn: 'INVESTIGATING OFFICERS',
    titleHi: 'जांच अधिकारी',
    icon: Shield,
    roleKeys: ['IO'],
  },
  {
    titleEn: 'INTELLIGENCE ANALYST',
    titleHi: 'खुफिया विश्लेषक',
    icon: BarChart2,
    roleKeys: ['ANALYST'],
  },
  {
    titleEn: 'SUPERVISORY OFFICERS',
    titleHi: 'पर्यवेक्षण अधिकारी',
    icon: Users,
    roleKeys: ['SUPERVISOR'],
  },
  {
    titleEn: 'OVERSIGHT AND ADMINISTRATION',
    titleHi: 'पर्यवेक्षण और प्रशासन',
    icon: Settings,
    roleKeys: ['AUDITOR', 'ADMIN'],
  },
]

const USER_COLOR_MAP: Record<string, string> = {
  'io.bengaluru': '#6d28d9',
  'io.delhi': '#1d4ed8',
  'io.mumbai': '#059669',
  'analyst.mumbai': '#047857',
  'sup.bengaluru': '#475569',
  'sup.delhi': '#0e7490',
  'sup.mumbai': '#c2410c',
  'auditor': '#7c3aed',
  'admin': '#334155',
}

const USER_STATE_MAP: Record<string, { cityUnit: string; state: string }> = {
  'io.bengaluru': { cityUnit: 'BLR-CEN · Bengaluru', state: 'Karnataka' },
  'io.delhi': { cityUnit: 'DEL-CYB · Delhi', state: 'Delhi' },
  'io.mumbai': { cityUnit: 'MUM-CYB · Mumbai', state: 'Maharashtra' },
  'analyst.mumbai': { cityUnit: 'MUM-CYB · Mumbai', state: 'Maharashtra' },
  'sup.bengaluru': { cityUnit: 'BLR-CEN · Bengaluru', state: 'Karnataka' },
  'sup.delhi': { cityUnit: 'DEL-CYB · Delhi', state: 'Delhi' },
  'sup.mumbai': { cityUnit: 'MUM-CYB · Mumbai', state: 'Maharashtra' },
  'auditor': { cityUnit: 'VIG · Vigilance', state: 'New Delhi' },
  'admin': { cityUnit: 'HQ · New Delhi', state: 'New Delhi' },
}

function getUserColor(u: User): string {
  if (USER_COLOR_MAP[u.username]) return USER_COLOR_MAP[u.username]
  switch (u.role) {
    case 'IO': return '#059669'
    case 'ANALYST': return '#047857'
    case 'SUPERVISOR': return '#c2410c'
    case 'AUDITOR': return '#7c3aed'
    case 'ADMIN': return '#334155'
    default: return '#0b2545'
  }
}

function getUserLocation(u: User): { cityUnit: string; state: string } {
  if (USER_STATE_MAP[u.username]) return USER_STATE_MAP[u.username]
  const stateByCity: Record<string, string> = {
    MUM: 'Maharashtra', DEL: 'Delhi', BLR: 'Karnataka', HYD: 'Telangana', CHE: 'Tamil Nadu', KOL: 'West Bengal',
  }
  const prefix = u.unit.split('-')[0]?.toUpperCase() ?? ''
  return {
    cityUnit: u.unit,
    state: stateByCity[prefix] ?? 'India',
  }
}

export default function Login({ isSwitcher = false }: { isSwitcher?: boolean }) {
  const { me, signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const done = () => navigate('/cases', { replace: true })
  const showSwitcher = isSwitcher || location.pathname === '/roles' || location.pathname === '/select-role'

  return (
    <div className="gov-role-page">
      {showSwitcher && me ? (
        <RoleSwitcher onDone={done} signIn={signIn} />
      ) : (
        <PasswordForm onDone={done} signIn={signIn} />
      )}
    </div>
  )
}

type SignIn = ReturnType<typeof useAuth>['signIn']

function RoleSwitcher({ onDone, signIn }: { onDone: () => void; signIn: SignIn }) {
  const [users, setUsers] = useState<User[] | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.demoUsers().then(
      (data) => {
        const order = [
          'io.bengaluru',
          'io.delhi',
          'io.mumbai',
          'analyst.mumbai',
          'sup.bengaluru',
          'sup.delhi',
          'sup.mumbai',
          'auditor',
          'admin',
        ]
        const sorted = [...data].sort((a, b) => order.indexOf(a.username) - order.indexOf(b.username))
        setUsers(sorted)
      },
      (e) => setError(e.message)
    )
  }, [])

  async function choose(username: string) {
    setBusy(username)
    setError(null)
    try {
      await signIn(await api.demoSession(username))
      onDone()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not switch session.')
      setBusy(null)
    }
  }

  const getInitials = (name: string) => {
    const clean = name.replace(/^(Insp\.|SI|PSI|ACP|DySP|Dr\.)\s+/i, '')
    const parts = clean.split(/\s+/).filter(Boolean)
    if (name.includes('IT Cell')) return 'IC'
    return parts.slice(0, 2).map((w) => w[0]?.toUpperCase()).join('')
  }

  return (
    <div className="gov-choose-role-wrap">
      {/* 1. PAGE HEADER */}
      <div className="gov-role-header">
        <h1 className="gov-role-title">Select Officer Role</h1>
        <div className="gov-role-title-hi">अधिकारी भूमिका का चयन करें</div>
        <div className="gov-role-subtitle">
          <div>Each role sees only what its permissions allow. Switch at any time from the navigation menu.</div>
          <div className="gov-role-subtitle-hi">
            प्रत्येक भूमिका में केवल वही जानकारी दिखाई देती है जिसकी अनुमति दी गई है। आप कभी भी नेविगेशन मेन्यू से भूमिका बदल सकते हैं।
          </div>
        </div>
      </div>

      <ErrorNote error={error} />
      {!users && !error && <p style={{ color: 'var(--muted)', padding: '24px 0' }}>Loading available roles…</p>}

      {/* 2. FOUR ROLE CATEGORIES */}
      {users && (
        <div className="gov-role-groups">
          {ROLE_GROUPS.map((grp) => {
            const members = users.filter((u) => grp.roleKeys.includes(u.role))
            if (!members.length) return null
            const GroupIcon = grp.icon

            return (
              <section key={grp.titleEn} className="gov-role-section">
                <div className="gov-role-group-header">
                  <GroupIcon size={16} className="gov-role-group-icon" />
                  <span className="gov-role-group-en">{grp.titleEn}</span>
                  <span className="gov-role-group-sep">|</span>
                  <span className="gov-role-group-hi">{grp.titleHi}</span>
                </div>

                <div className="gov-role-grid">
                  {members.map((u) => {
                    const initials = getInitials(u.name)
                    const color = getUserColor(u)
                    const meta = getUserLocation(u)

                    return (
                      <button
                        key={u.username}
                        className={`gov-role-card ${busy === u.username ? 'busy' : ''}`}
                        disabled={busy !== null}
                        onClick={() => choose(u.username)}
                        aria-label={`Select role ${u.name}, ${u.role_label}`}
                      >
                        <div className="gov-role-avatar" style={{ backgroundColor: color }}>
                          {initials}
                        </div>

                        <div className="gov-role-card-info">
                          <div className="gov-role-card-name">{u.name}</div>
                          <div className="gov-role-card-role">{u.role_label}</div>
                          <div className="gov-role-card-unit">{meta.cityUnit}</div>
                          <div className="gov-role-card-state">
                            <MapPin size={11} className="gov-role-pin-icon" />
                            <span>{meta.state}</span>
                          </div>
                        </div>

                        <div className="gov-role-card-arrow">
                          <ChevronRight size={18} />
                        </div>
                      </button>
                    )
                  })}
                </div>
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}

function PasswordForm({ onDone, signIn }: { onDone: () => void; signIn: SignIn }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [totp, setTotp] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Only the isolated demo build serves /demo/*; a standard build answers 404
  // and the quick-select panel stays hidden.
  const [isDemoBuild, setIsDemoBuild] = useState(false)

  useEffect(() => {
    api.demoUsers().then(
      () => setIsDemoBuild(true),
      () => setIsDemoBuild(false)
    )
  }, [])

  const OFFICER_PRESETS = [
    { label: 'Insp. Deshmukh', role: 'IO (Mumbai)', user: 'io.mumbai' },
    { label: 'Analyst Kelkar', role: 'Analyst (Mumbai)', user: 'analyst.mumbai' },
    { label: 'ACP Pawar', role: 'Supervisor (Mumbai)', user: 'sup.mumbai' },
    { label: 'Insp. Malik', role: 'IO (Delhi)', user: 'io.delhi' },
    { label: 'Admin', role: 'IT Cell HQ', user: 'admin' },
  ]

  async function selectPreset(u: string) {
    setUsername(u)
    setBusy(true)
    setError(null)
    try {
      await signIn(await api.demoSession(u))
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the demo session.')
      setBusy(false)
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signIn(await api.login(username.trim(), password, totp.trim()))
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sign-in failed. Please verify credentials.')
      setBusy(false)
    }
  }

  return (
    <div style={{ maxWidth: 460, margin: '24px auto', padding: '0 16px' }}>
      <form className="login-form gov-card-panel" onSubmit={submit} style={{ padding: '32px 28px' }}>
        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <div style={{ display: 'inline-flex', justifyContent: 'center', marginBottom: 12 }}>
            <PramanaLogo size={48} />
          </div>
          <h2 style={{ margin: 0, fontSize: 20, color: 'var(--text, #0b2545)', fontWeight: 750 }}>
            Official Portal Sign In
          </h2>
          <div style={{ fontSize: 13, color: 'var(--text-muted, #64748b)', fontWeight: 600, marginTop: 2 }}>
            आधिकारिक पोर्टल साइन इन
          </div>
          <p className="muted small" style={{ marginTop: 6, fontSize: 12.5, lineHeight: 1.4 }}>
            Enter your official credentials and 2FA verification PIN to access the investigation workspace.
          </p>
        </div>

        {/* Quick Officer Selection Pills (demo build only) */}
        {isDemoBuild && <div style={{ background: 'var(--subtle-bg, #f8fafc)', padding: '10px 12px', borderRadius: 8, border: '1px solid #e2e8f0', marginBottom: 4 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>
            Demo build: quick officer select / अधिकारी चयन
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {OFFICER_PRESETS.map((p) => (
              <button
                key={p.user}
                type="button"
                onClick={() => selectPreset(p.user)}
                disabled={busy}
                style={{
                  fontSize: 11.5,
                  padding: '4px 8px',
                  borderRadius: 4,
                  border: username === p.user ? '1px solid #0047ba' : '1px solid #cbd5e1',
                  background: username === p.user ? '#0047ba' : '#ffffff',
                  color: username === p.user ? '#ffffff' : '#1e293b',
                  cursor: 'pointer',
                  fontWeight: username === p.user ? 700 : 500,
                  transition: 'all 0.15s ease',
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>}

        <label>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Shield size={14} /> Official Username / आईडी
          </span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            placeholder="e.g. io.mumbai, analyst.mumbai"
            required
            autoFocus
          />
        </label>

        <label>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Lock size={14} /> Password / पासवर्ड
          </span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            placeholder="Enter password"
            required
          />
        </label>

        <label>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <KeyRound size={14} /> Security PIN / 2FA Code (6 Digits)
          </span>
          <input
            value={totp}
            onChange={(e) => setTotp(e.target.value.replace(/\D/g, '').slice(0, 6))}
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="6-digit security PIN"
            pattern="\d{6}"
            required
          />
        </label>

        <ErrorNote error={error} />

        <button className="btn btn-primary" disabled={busy} style={{ marginTop: 4, height: 42, fontWeight: 700, fontSize: 14 }}>
          {busy ? 'Verifying & Signing in…' : 'Sign in to PRAMANA'} <ArrowRight size={16} aria-hidden />
        </button>

        <div style={{ marginTop: 8, padding: '8px 10px', background: 'var(--subtle-bg, #f1f5f9)', borderRadius: 6, fontSize: 11, color: 'var(--text-muted, #64748b)', lineHeight: 1.4 }}>
          <strong>Notice:</strong> Authorized law enforcement and intelligence personnel only. All access transactions are cryptographically recorded in the immutable audit ledger.
        </div>
      </form>
    </div>
  )
}
