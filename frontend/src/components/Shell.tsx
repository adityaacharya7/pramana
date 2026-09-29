import {
  ArrowDownCircle,
  Bell,
  ChevronDown,
  ChevronRight,
  FileCheck2,
  Folder,
  Headphones,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Moon,
  ScrollText,
  Settings,
  Sun,
  UserCheck,
} from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { applyTheme, effectiveTheme, type Theme } from '../theme'
import { PramanaLogo } from './Emblems'
import { HelplineModal, NotificationPopover } from './GovModals'
import AiCopilot from './AiCopilot'

const TAB_NAMES: Record<string, string> = {
  review: 'Review queue',
  graph: 'Graph & timeline',
  leads: 'Leads',
  trail: 'Money trail',
  crosscase: 'Cross-case',
  ai: 'AI Forensic Intelligence',
}

function useFormattedClock() {
  const [timeStr, setTimeStr] = useState(() => formatNow())

  function formatNow() {
    try {
      const now = new Date()
      const datePart = new Intl.DateTimeFormat('en-IN', {
        timeZone: 'Asia/Kolkata',
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      }).format(now)
      const timePart = new Intl.DateTimeFormat('en-IN', {
        timeZone: 'Asia/Kolkata',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      }).format(now)

      return `${datePart}  |  ${timePart.toUpperCase()}`
    } catch {
      const d = new Date()
      return `${d.toLocaleDateString()}  |  ${d.toLocaleTimeString()}`
    }
  }

  useEffect(() => {
    const timer = setInterval(() => setTimeStr(formatNow()), 30000)
    return () => clearInterval(timer)
  }, [])

  return timeStr
}

function GovCrumbs() {
  const location = useLocation()
  const parts = location.pathname.split('/').filter(Boolean)
  const items: { to?: string; label: string }[] = [{ to: '/cases', label: 'Home' }]

  if (parts.length === 0 || parts[0] === 'cases') {
    if (parts.length === 1) {
      items.push({ label: 'Cases' })
    } else if (parts[1]) {
      items.push({ to: '/cases', label: 'Cases' })
      items.push({ to: parts[2] ? `/cases/${parts[1]}` : undefined, label: parts[1] })
      if (parts[2]) {
        items.push({ label: TAB_NAMES[parts[2]] ?? parts[2] })
      }
    }
  } else if (parts[0] === 'login') {
    items.push({ label: 'Sign In' })
  } else if (parts[0] === 'roles' || parts[0] === 'select-role') {
    items.push({ label: 'Select Role' })
  } else if (parts[0] === 'leads') {
    items.push({ to: '/cases', label: 'Cases' }, { label: 'Lead Details' })
  } else if (parts[0] === 'access') {
    items.push({ label: 'Access Requests' })
  } else if (parts[0] === 'verify') {
    items.push({ label: 'Verify Handover' })
  } else if (parts[0] === 'audit') {
    items.push({ label: 'Audit Log' })
  } else {
    items.push({ label: parts[0].charAt(0).toUpperCase() + parts[0].slice(1) })
  }

  return (
    <nav className="gov-crumbs" aria-label="Breadcrumb">
      <Link to="/cases" className="gov-crumb-home" title="Home">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          <polyline points="9 22 9 12 15 12 15 22" />
        </svg>
      </Link>
      {items.map((it, i) => (
        <span key={i} className="gov-crumb-item">
          {i > 0 && <span className="gov-crumb-sep">&gt;</span>}
          {it.to && i < items.length - 1 ? (
            <Link to={it.to} className="gov-crumb-link">
              {it.label}
            </Link>
          ) : (
            <span className="gov-crumb-current">{it.label}</span>
          )}
        </span>
      ))}
    </nav>
  )
}

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(effectiveTheme)
  const next: Theme = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      className="gov-header-icon-btn"
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      onClick={() => {
        applyTheme(next)
        setTheme(next)
      }}
    >
      {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
    </button>
  )
}

export default function Shell({ children }: { children?: ReactNode }) {
  const { me, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [helpOpen, setHelpOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [zoomLevel, setZoomLevel] = useState<'normal' | 'small' | 'large'>('normal')
  const [hindiOnly, setHindiOnly] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  const clockString = useFormattedClock()

  const isRoleSelect =
    location.pathname === '/roles' ||
    location.pathname === '/select-role' ||
    location.pathname === '/login'

  const user = me?.user ?? null

  const initials = user?.name
    ? user.name
        .replace(/^(Insp\.|SI|PSI|ACP|DySP|Dr\.)\s+/i, '')
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((w) => w[0]?.toUpperCase())
        .join('')
    : 'PO'

  const handleZoom = (level: 'small' | 'normal' | 'large') => {
    setZoomLevel(level)
    const root = document.documentElement
    if (level === 'small') root.style.fontSize = '90%'
    else if (level === 'large') root.style.fontSize = '110%'
    else root.style.fontSize = '100%'
  }

  const handleSignOut = () => {
    signOut()
    setUserMenuOpen(false)
    navigate('/login')
  }

  const scrollToContent = () => {
    const el = document.getElementById('main-content')
    if (el) el.scrollIntoView({ behavior: 'smooth' })
  }

  // Close menus on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div className="gov-shell-wrapper">
      {/* 1. TOP PRAMANA INSTITUTIONAL HEADER */}
      <header className="gov-header" role="banner">
        <div className="gov-header-left">
          {/* PRAMANA Brand Title */}
          <Link to="/cases" className="gov-brand-wrap" aria-label="PRAMANA Home">
            <PramanaLogo size={40} className="gov-brand-icon" />
            <div className="gov-brand-text">
              <span className="gov-brand-hi">प्रमाण — Investigation Review System</span>
            </div>
          </Link>
        </div>

        <div className="gov-header-right">
          {/* Skip to content link */}
          <button onClick={scrollToContent} className="gov-skip-link" title="Skip to main content">
            <ArrowDownCircle size={14} aria-hidden />
            <span>Skip to main content</span>
          </button>

          {/* Text size controls */}
          <div className="gov-text-size" aria-label="Text Size Adjustment">
            <button
              onClick={() => handleZoom('small')}
              className={zoomLevel === 'small' ? 'active' : ''}
              title="Decrease text size"
            >
              A-
            </button>
            <button
              onClick={() => handleZoom('normal')}
              className={zoomLevel === 'normal' ? 'active' : ''}
              title="Default text size"
            >
              A
            </button>
            <button
              onClick={() => handleZoom('large')}
              className={zoomLevel === 'large' ? 'active' : ''}
              title="Increase text size"
            >
              A+
            </button>
          </div>

          <span className="gov-util-sep" aria-hidden />

          {/* Language selector */}
          <button
            className="gov-lang-btn"
            onClick={() => setHindiOnly(!hindiOnly)}
            title="भाषा बदलें / Toggle primary language"
          >
            हिंदी
          </button>

          {/* Dark mode moon/sun */}
          <ThemeToggle />

          {/* Notification bell */}
          <div style={{ position: 'relative' }}>
            <button
              className="gov-header-icon-btn"
              onClick={() => setNotifOpen(!notifOpen)}
              title="Notifications"
              aria-label="Notifications"
            >
              <Bell size={18} />
              <span className="gov-notif-badge">3</span>
            </button>
            <NotificationPopover isOpen={notifOpen} onClose={() => setNotifOpen(false)} />
          </div>

          {/* User profile with initials & dropdown */}
          {user ? (
            <div className="gov-user-profile-wrap" ref={userMenuRef}>
              <button
                className="gov-user-profile-btn"
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                aria-expanded={userMenuOpen}
                aria-label="User menu"
              >
                <span className="gov-user-avatar" style={{ background: '#073b3a' }}>
                  {initials}
                </span>
                <div className="gov-user-info">
                  <span className="gov-user-name">{user.name}</span>
                  <span className="gov-user-role">{user.role_label || 'Officer'}</span>
                </div>
                <ChevronDown size={14} className="gov-user-chevron" />
              </button>

              {userMenuOpen && (
                <div className="gov-user-dropdown" role="menu">
                  <div className="gov-user-dropdown-header">
                    <div className="gov-user-dropdown-name">{user.name}</div>
                    <div className="gov-user-dropdown-meta">
                      {user.role_label} · {user.unit}
                    </div>
                    <div className="gov-user-dropdown-id">{user.username}</div>
                  </div>
                  <div className="gov-user-dropdown-divider" />
                  <button
                    className="gov-user-dropdown-item"
                    onClick={() => {
                      setUserMenuOpen(false)
                      navigate('/roles')
                    }}
                  >
                    <UserCheck size={16} />
                    <span>Switch Role / भूमिका का चयन</span>
                  </button>
                  <button className="gov-user-dropdown-item gov-dropdown-danger" onClick={handleSignOut}>
                    <LogOut size={16} />
                    <span>Sign Out / बाहर निकलें</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link
              to="/login"
              className="gov-header-icon-btn"
              style={{ width: 'auto', height: 'auto', minWidth: 'max-content', padding: '8px 14px', fontSize: 13, fontWeight: 600, textDecoration: 'none', color: '#0b2545', background: '#e2e8f0', borderRadius: '6px', whiteSpace: 'nowrap', flexShrink: 0 }}
            >
              Sign In / लॉगिन
            </Link>
          )}
        </div>
      </header>

      {/* 2. DARK NAVY SUBHEADER BAR */}
      <div className="gov-subheader">
        <GovCrumbs />
        <div className="gov-subheader-clock" aria-label="Current date and time">
          {clockString}
        </div>
      </div>

      {/* 3. MAIN WORKSPACE WITH SIDEBAR */}
      <div className="gov-workspace">
        <aside className="gov-sidebar" aria-label="Main Navigation">
          <nav className="gov-sidebar-nav">
            {/* If on Select Role or in demo mode with extra tabs as shown in Image 2 */}
            {isRoleSelect ? (
              <>
                <NavLink to="/cases" className="gov-navlink">
                  <LayoutDashboard size={18} aria-hidden />
                  <div className="gov-nav-text">
                    <span className="gov-nav-en">Dashboard</span>
                    <span className="gov-nav-hi">डैशबोर्ड</span>
                  </div>
                </NavLink>

                <NavLink to="/cases" className="gov-navlink">
                  <Folder size={18} aria-hidden />
                  <div className="gov-nav-text">
                    <span className="gov-nav-en">Cases</span>
                    <span className="gov-nav-hi">मामले</span>
                  </div>
                </NavLink>

                <NavLink to="/access" className="gov-navlink">
                  <KeyRound size={18} aria-hidden />
                  <div className="gov-nav-text">
                    <span className="gov-nav-en">Access Requests</span>
                    <span className="gov-nav-hi">पहुंच अनुरोध</span>
                  </div>
                </NavLink>

                <NavLink
                  to="/roles"
                  className={`gov-navlink ${
                    location.pathname === '/roles' || location.pathname === '/select-role' ? 'active' : ''
                  }`}
                >
                  <UserCheck size={18} aria-hidden />
                  <div className="gov-nav-text">
                    <span className="gov-nav-en">Select Role</span>
                    <span className="gov-nav-hi">भूमिका का चयन</span>
                  </div>
                </NavLink>

                <NavLink to="/audit" className="gov-navlink">
                  <ScrollText size={18} aria-hidden />
                  <div className="gov-nav-text">
                    <span className="gov-nav-en">Audit Log</span>
                    <span className="gov-nav-hi">ऑडिट लॉग</span>
                  </div>
                </NavLink>

                <button
                  className="gov-navlink"
                  style={{ width: '100%', background: 'transparent', border: 0, textAlign: 'left', cursor: 'pointer' }}
                  onClick={() => alert('PRAMANA Investigation Review System v1.0.0')}
                >
                  <Settings size={18} aria-hidden />
                  <div className="gov-nav-text">
                    <span className="gov-nav-en">Settings</span>
                    <span className="gov-nav-hi">सेटिंग्स</span>
                  </div>
                </button>
              </>
            ) : (
              <>
                <NavLink to="/cases" className={({ isActive }) => `gov-navlink ${isActive ? 'active' : ''}`}>
                  <Folder size={18} aria-hidden />
                  <div className="gov-nav-text">
                    <span className="gov-nav-en">Cases</span>
                    <span className="gov-nav-hi">मामले</span>
                  </div>
                </NavLink>

                <NavLink to="/access" className={({ isActive }) => `gov-navlink ${isActive ? 'active' : ''}`}>
                  <KeyRound size={18} aria-hidden />
                  <div className="gov-nav-text">
                    <span className="gov-nav-en">Access Requests</span>
                    <span className="gov-nav-hi">पहुंच अनुरोध</span>
                  </div>
                </NavLink>

                <NavLink to="/verify" className={({ isActive }) => `gov-navlink ${isActive ? 'active' : ''}`}>
                  <FileCheck2 size={18} aria-hidden />
                  <div className="gov-nav-text">
                    <span className="gov-nav-en">Verify Handover</span>
                    <span className="gov-nav-hi">हस्तांतरण सत्यापन</span>
                  </div>
                </NavLink>

                <NavLink to="/audit" className={({ isActive }) => `gov-navlink ${isActive ? 'active' : ''}`}>
                  <ScrollText size={18} aria-hidden />
                  <div className="gov-nav-text">
                    <span className="gov-nav-en">Audit Log</span>
                    <span className="gov-nav-hi">ऑडिट लॉग</span>
                  </div>
                </NavLink>
              </>
            )}
          </nav>

          {/* Need Help? Helpline: 1930 */}
          <div className="gov-sidebar-footer">
            <button
              className="gov-helpline-card"
              onClick={() => setHelpOpen(true)}
              aria-label="Need Help? Helpline 1930"
            >
              <div className="gov-helpline-icon">
                <Headphones size={18} />
              </div>
              <div className="gov-helpline-text">
                <span className="gov-helpline-title">Need Help?</span>
                <span className="gov-helpline-hi">सहायता चाहिए?</span>
                <span className="gov-helpline-num">Helpline: <strong>1930</strong></span>
              </div>
              <ChevronRight size={16} className="gov-helpline-arrow" />
            </button>
          </div>
        </aside>

        {/* MAIN PAGE OUTLET */}
        <main className="gov-main-content" id="main-content">
          {children ?? <Outlet />}
        </main>
      </div>

      {/* 4. INSTITUTIONAL FOOTER */}
      <footer className="gov-app-footer" role="contentinfo">
        <div className="gov-footer-left">
          <span className="gov-footer-brand">PRAMANA (प्रमाण)</span>
          <span className="gov-footer-sep">·</span>
          <span className="gov-footer-sub">Investigation Review System</span>
        </div>
        <div className="gov-footer-right">
          <span className="gov-footer-disclaimer">
            <span>Official Cybercrime & Financial Fraud Investigation Review Framework</span>
          </span>
        </div>
      </footer>

      {/* Helpline 1930 Dialog */}
      <HelplineModal isOpen={helpOpen} onClose={() => setHelpOpen(false)} />

      {/* PRAMANA AI Copilot Floating Interface */}
      <AiCopilot />
    </div>
  )
}
