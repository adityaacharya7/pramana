import {
  ArrowRight,
  BarChart2,
  ChevronRight,
  Lock,
  MapPin,
  Settings,
  Shield,
  Users,
} from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError, type User } from '../api'
import { useAuth } from '../auth'
import { ErrorNote } from '../components/bits'
import { ParliamentWatermark } from '../components/Emblems'

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

// Accurate avatar colors matching Image 2
const USER_COLOR_MAP: Record<string, string> = {
  'io.bengaluru': '#6d28d9', // CG: Purple
  'io.delhi': '#1d4ed8',     // RM: Blue
  'io.mumbai': '#059669',    // AD: Green
  'analyst.mumbai': '#047857',// TK: Forest Green
  'sup.bengaluru': '#475569',// MB: Slate
  'sup.delhi': '#0e7490',    // RK: Teal
  'sup.mumbai': '#c2410c',   // SP: Rust Orange
  'auditor': '#7c3aed',      // KS: Violet/Purple
  'admin': '#334155',        // IC: Dark Slate
}

// State location mappings matching Image 2
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

export default function Login() {
  const { build, signIn } = useAuth()
  const navigate = useNavigate()

  const done = () => navigate('/cases', { replace: true })

  return (
    <div className="gov-role-page">
      {build === 'demo' ? (
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
        // Sort order to match Image 2 exactly:
        // IO: Chaitra Gowda, Rohit Malik, Aparna Deshmukh
        // Analyst: Tanvi Kelkar
        // Supervisor: Manjunath B., Ritu Khanna, Suhas Pawar
        // Oversight: K. Srinivasan, IT Cell Administrator
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
      setError(e instanceof Error ? e.message : 'Could not start the session.')
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
        <h1 className="gov-role-title">Choose a role</h1>
        <div className="gov-role-title-hi">भूमिका का चयन करें</div>
        <div className="gov-role-subtitle">
          <div>Each role sees only what its permissions allow. Switch at any time from the sidebar.</div>
          <div className="gov-role-subtitle-hi">
            प्रत्येक भूमिका में केवल वही जानकारी दिखाई देती है जिसकी अनुमति दी गई है। आप कभी भी साइडबार से भूमिका बदल सकते हैं।
          </div>
        </div>
      </div>

      {/* 2. SYNTHETIC DEMO BUILD BANNER WITH PARLIAMENT WATERMARK */}
      <div className="gov-demo-banner">
        <div className="gov-demo-banner-content">
          <div className="gov-demo-lock-box">
            <Lock size={18} />
          </div>
          <div className="gov-demo-banner-text">
            <div className="gov-demo-banner-heading">Synthetic demo build</div>
            <div className="gov-demo-banner-desc">
              Isolated database. Every person, number and account is invented. Choose a role to continue.
            </div>
          </div>
        </div>
        {/* Subtle Parliament / Rashtrapati Bhavan architectural illustration */}
        <ParliamentWatermark className="gov-demo-watermark" />
      </div>

      <ErrorNote error={error} />
      {!users && !error && <p style={{ color: 'var(--muted)', padding: '24px 0' }}>Loading available roles…</p>}

      {/* 3. FOUR ROLE CATEGORIES */}
      {users && (
        <div className="gov-role-groups">
          {ROLE_GROUPS.map((grp) => {
            const members = users.filter((u) => grp.roleKeys.includes(u.role))
            if (!members.length) return null
            const GroupIcon = grp.icon

            return (
              <section key={grp.titleEn} className="gov-role-section">
                {/* Category Header */}
                <div className="gov-role-group-header">
                  <GroupIcon size={16} className="gov-role-group-icon" />
                  <span className="gov-role-group-en">{grp.titleEn}</span>
                  <span className="gov-role-group-sep">|</span>
                  <span className="gov-role-group-hi">{grp.titleHi}</span>
                </div>

                {/* 3-Column Card Grid */}
                <div className="gov-role-grid">
                  {members.map((u) => {
                    const initials = getInitials(u.name)
                    const color = USER_COLOR_MAP[u.username] ?? '#0b2545'
                    const meta = USER_STATE_MAP[u.username] ?? {
                      cityUnit: `${u.unit}`,
                      state: 'India',
                    }

                    return (
                      <button
                        key={u.username}
                        className={`gov-role-card ${busy === u.username ? 'busy' : ''}`}
                        disabled={busy !== null}
                        onClick={() => choose(u.username)}
                        aria-label={`Select role ${u.name}, ${u.role_label}`}
                      >
                        {/* Avatar Circle with initials */}
                        <div className="gov-role-avatar" style={{ backgroundColor: color }}>
                          {initials}
                        </div>

                        {/* Text info */}
                        <div className="gov-role-card-info">
                          <div className="gov-role-card-name">{u.name}</div>
                          <div className="gov-role-card-role">{u.role_label}</div>
                          <div className="gov-role-card-unit">{meta.cityUnit}</div>
                          <div className="gov-role-card-state">
                            <MapPin size={11} className="gov-role-pin-icon" />
                            <span>{meta.state}</span>
                          </div>
                        </div>

                        {/* Chevron right */}
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
    <div style={{ maxWidth: 440, margin: '40px auto' }}>
      <form className="login-form gov-card-panel" onSubmit={submit}>
        <div>
          <h2>PRAMANA Sign In</h2>
          <p className="muted small" style={{ marginTop: 4 }}>
            Use your official credentials and the code from your authenticator app.
          </p>
        </div>
        <label>
          Username
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
            autoFocus
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
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
    </div>
  )
}
