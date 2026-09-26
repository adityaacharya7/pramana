import { FolderOpen, LogOut, ScrollText } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import Wordmark from './Wordmark'

export default function Shell() {
  const { me, build, signOut } = useAuth()
  const navigate = useNavigate()
  if (!me) return null
  const u = me.user

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-left">
          <Wordmark />
          {build === 'demo' && (
            <span className="pill pill-demo" title="Isolated synthetic demo build with its own database">
              Synthetic demo build
            </span>
          )}
        </div>
        <div className="topbar-right">
          <div className="whoami">
            <span className="whoami-name">{u.name}</span>
            <span className="whoami-meta">
              {u.role_label} · {u.unit}
            </span>
          </div>
          <button
            className="btn btn-ghost"
            onClick={() => {
              signOut()
              navigate('/login')
            }}
          >
            <LogOut size={16} aria-hidden /> {build === 'demo' ? 'Switch role' : 'Sign out'}
          </button>
        </div>
      </header>
      <nav className="sidenav" aria-label="Main">
        <NavLink to="/cases" className="navlink">
          <FolderOpen size={17} aria-hidden /> Cases
        </NavLink>
        <NavLink to="/audit" className="navlink">
          <ScrollText size={17} aria-hidden /> Audit log
        </NavLink>
        <p className="sidenav-note">
          Decision support only. The legal basis and final action rest with the officer and the competent authority.
        </p>
      </nav>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
