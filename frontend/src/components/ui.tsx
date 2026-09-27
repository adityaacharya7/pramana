import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'

/* ---------- layout ---------- */

export function PageHeader({ eyebrow, title, subtitle, actions }: {
  eyebrow?: ReactNode
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="page-header">
      <div className="page-header-text">
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {subtitle && <p className="page-sub">{subtitle}</p>}
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </header>
  )
}

export function Card({ title, subtitle, actions, icon, children, className = '', flush = false }: {
  title?: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  icon?: ReactNode
  children?: ReactNode
  className?: string
  flush?: boolean
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          <div className="card-title">
            {icon && <span className="card-icon">{icon}</span>}
            <div>
              {title && <h2>{title}</h2>}
              {subtitle && <p className="card-sub">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      <div className={flush ? 'card-body-flush' : 'card-body'}>{children}</div>
    </section>
  )
}

export function Metric({ label, value, hint, tone }: { label: ReactNode; value: ReactNode; hint?: ReactNode; tone?: 'ok' | 'warn' | 'bad' }) {
  return (
    <div className={`metric${tone ? ` metric-${tone}` : ''}`}>
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
      {hint && <span className="metric-hint">{hint}</span>}
    </div>
  )
}

const PALETTE = ['#2455C3', '#0E7490', '#7C3AED', '#B45309', '#15803D', '#BE185D', '#475569', '#1D4ED8']

export function Avatar({ name, size = 30 }: { name: string; size?: number }) {
  const clean = name.replace(/^(Insp\.|SI|PSI|ACP|DySP|Dr\.)\s+/i, '')
  const initials = clean.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join('')
  const color = PALETTE[[...name].reduce((n, c) => n + c.charCodeAt(0), 0) % PALETTE.length]
  return (
    <span className="avatar" style={{ width: size, height: size, background: color, fontSize: size * 0.4 }} aria-hidden>
      {initials}
    </span>
  )
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty-state">
      {icon && <div className="empty-icon">{icon}</div>}
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton" aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  )
}

export function Callout({ tone = 'info', title, children }: { tone?: 'info' | 'ok' | 'warn' | 'bad'; title?: ReactNode; children?: ReactNode }) {
  const Icon = tone === 'ok' ? CheckCircle2 : tone === 'info' ? Info : AlertTriangle
  return (
    <div className={`alert alert-${tone}`} role={tone === 'bad' ? 'alert' : undefined}>
      <Icon size={16} aria-hidden />
      <div>
        {title && <strong>{title}</strong>}
        {children && <div className="alert-body">{children}</div>}
      </div>
    </div>
  )
}

/* ---------- toasts ---------- */

type Toast = { id: number; text: string; tone: 'ok' | 'bad' | 'info' }
const ToastCtx = createContext<(text: string, tone?: Toast['tone']) => void>(() => undefined)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const push = useCallback((text: string, tone: Toast['tone'] = 'ok') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, text, tone }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4800)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`}>
            {t.tone === 'bad' ? <AlertTriangle size={16} aria-hidden /> : <CheckCircle2 size={16} aria-hidden />}
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export const useToast = () => useContext(ToastCtx)

/* ---------- reason dialog (replaces window.prompt) ---------- */

type Ask = { title: string; body?: ReactNode; confirm: string; tone?: 'primary' | 'danger'; minLength?: number; placeholder?: string }
type Pending = Ask & { resolve: (v: string | null) => void }
const DialogCtx = createContext<(a: Ask) => Promise<string | null>>(async () => null)

export function DialogProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null)
  const [value, setValue] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)
  const ask = useCallback((a: Ask) => new Promise<string | null>((resolve) => {
    setValue('')
    setPending({ ...a, resolve })
  }), [])
  useEffect(() => {
    if (pending) setTimeout(() => ref.current?.focus(), 0)
  }, [pending])
  const close = (v: string | null) => {
    pending?.resolve(v)
    setPending(null)
  }
  const min = pending?.minLength ?? 3
  return (
    <DialogCtx.Provider value={ask}>
      {children}
      {pending && (
        <div className="modal-backdrop" onMouseDown={() => close(null)}>
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="dlg-title" onMouseDown={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.key === 'Escape' && close(null)}>
            <div className="modal-head">
              <h2 id="dlg-title">{pending.title}</h2>
              <button className="icon-btn" onClick={() => close(null)} aria-label="Close"><X size={18} /></button>
            </div>
            {pending.body && <div className="modal-body">{pending.body}</div>}
            <label className="field">
              <span>Reason <em>(required, written to the audit log)</em></span>
              <textarea ref={ref} rows={3} value={value} onChange={(e) => setValue(e.target.value)} placeholder={pending.placeholder} />
            </label>
            <div className="modal-foot">
              <button className="btn btn-ghost" onClick={() => close(null)}>Cancel</button>
              <button className={`btn ${pending.tone === 'danger' ? 'btn-danger' : 'btn-primary'}`} disabled={value.trim().length < min}
                onClick={() => close(value.trim())}>
                {pending.confirm}
              </button>
            </div>
          </div>
        </div>
      )}
    </DialogCtx.Provider>
  )
}

export const useAsk = () => useContext(DialogCtx)
