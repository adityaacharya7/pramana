import { ShieldAlert, ShieldCheck, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api, ApiError, type Evidence, type EvidenceContent } from '../api'
import { formatBytes, formatDateTime, KIND_LABELS, parseCsv } from '../format'
import { Hash } from './bits'

const MAX_ROWS = 1000

export default function EvidenceViewer({ ev, onClose, onBlocked }: { ev: Evidence; onClose: () => void; onBlocked: () => void }) {
  const [content, setContent] = useState<EvidenceContent | null>(null)
  const [error, setError] = useState<{ status: number; message: string } | null>(null)

  useEffect(() => {
    let url: string | null = null
    let live = true
    api.content(ev).then(
      (c) => {
        if (c.kind === 'pdf') url = c.url
        if (live) setContent(c)
      },
      (e) => {
        if (!live) return
        const status = e instanceof ApiError ? e.status : 0
        setError({ status, message: e.message })
        if (status === 409) onBlocked()
      },
    )
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => {
      live = false
      window.removeEventListener('keydown', onKey)
      if (url) URL.revokeObjectURL(url)
    }
  }, [ev, onClose, onBlocked])

  const rows = useMemo(() => (content?.kind === 'text' && ev.type === 'CSV' ? parseCsv(content.text) : null), [content, ev.type])
  const matches = content && content.sha256 === ev.sha256

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={`Evidence ${ev.filename}`} onClick={(e) => e.stopPropagation()}>
        <header className="drawer-head">
          <div>
            <h2>{ev.filename}</h2>
            <p className="muted small">
              {KIND_LABELS[ev.kind] ?? ev.kind} · {ev.type} · {formatBytes(ev.size_bytes)} · sealed {formatDateTime(ev.uploaded_at)} by{' '}
              {ev.uploaded_by_name || ev.uploaded_by}
            </p>
            <div className="drawer-hash">
              <span className="muted small">SHA-256</span> <Hash value={ev.sha256} full />
            </div>
          </div>
          <button className="icon-btn icon-btn-lg" onClick={onClose} aria-label="Close">
            <X size={20} />
          </button>
        </header>

        {matches && (
          <div className="note note-ok">
            <ShieldCheck size={16} aria-hidden />
            <span>Re-hashed on load: matches the sealed manifest. A matching hash shows the file is unchanged since upload, not that its content is true.</span>
          </div>
        )}
        {error?.status === 409 && (
          <div className="note note-bad" role="alert">
            <ShieldAlert size={16} aria-hidden />
            <span>
              <strong>Integrity mismatch.</strong> This file no longer matches the hash recorded when it was sealed, so it is blocked from
              viewing and analysis. The event has been written to the audit log.
            </span>
          </div>
        )}
        {error && error.status !== 409 && <div className="note note-bad">{error.message}</div>}
        {!content && !error && <p className="muted pad">Loading and re-checking the hash…</p>}

        <div className="drawer-body">
          {content?.kind === 'pdf' && <iframe title={ev.filename} src={content.url} className="pdf-frame" />}
          {rows && (
            <div className="table-wrap">
              <table className="table table-dense">
                <thead>
                  <tr>
                    <th className="rownum">#</th>
                    {rows[0]?.map((h, i) => <th key={i}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(1, MAX_ROWS + 1).filter((r) => r.length > 1 || r[0]).map((r, i) => (
                    <tr key={i}>
                      <td className="rownum">{i + 1}</td>
                      {r.map((cell, j) => (
                        <td key={j} className={/^-?[\d,.]+$/.test(cell) ? 'num mono' : undefined}>
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length > MAX_ROWS + 1 && <p className="muted small pad">Showing the first {MAX_ROWS} rows.</p>}
            </div>
          )}
          {content?.kind === 'text' && !rows && <pre className="doc">{content.text}</pre>}
        </div>
      </aside>
    </div>
  )
}
