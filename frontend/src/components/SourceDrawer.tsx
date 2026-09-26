import { ShieldAlert, ShieldCheck, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError } from '../api'

export interface SourceRef {
  evidenceId: string
  filename: string
  spans: [number, number][]
  title?: string
}

/** The exact source text behind a mention or relationship, with every
 *  relevant span highlighted. The text is re-hashed by the server on load. */
export default function SourceDrawer({ source, onClose }: { source: SourceRef; onClose: () => void }) {
  const [text, setText] = useState<string | null>(null)
  const [error, setError] = useState<{ status: number; message: string } | null>(null)
  const first = useRef<HTMLElement | null>(null)

  useEffect(() => {
    let live = true
    api.evidenceText(source.evidenceId).then(
      (t) => live && setText(t),
      (e) => live && setError({ status: e instanceof ApiError ? e.status : 0, message: e.message }),
    )
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => {
      live = false
      window.removeEventListener('keydown', onKey)
    }
  }, [source.evidenceId, onClose])

  const parts = useMemo(() => {
    if (text === null) return []
    const spans = [...source.spans].filter(([s, e]) => e > s).sort((a, b) => a[0] - b[0])
    const out: { text: string; mark: boolean }[] = []
    let pos = 0
    for (const [s, e] of spans) {
      if (s < pos) continue
      out.push({ text: text.slice(pos, s), mark: false })
      out.push({ text: text.slice(s, e), mark: true })
      pos = e
    }
    out.push({ text: text.slice(pos), mark: false })
    return out
  }, [text, source.spans])

  useEffect(() => {
    first.current?.scrollIntoView({ block: 'center' })
  }, [parts])

  let firstAssigned = false
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={`Source ${source.filename}`} onClick={(e) => e.stopPropagation()}>
        <header className="drawer-head">
          <div>
            <h2>{source.title ?? source.filename}</h2>
            <p className="muted small">
              {source.filename} · {source.spans.length} highlighted passage{source.spans.length === 1 ? '' : 's'}
            </p>
          </div>
          <button className="icon-btn icon-btn-lg" onClick={onClose} aria-label="Close">
            <X size={20} />
          </button>
        </header>
        {text !== null && (
          <div className="note note-ok">
            <ShieldCheck size={16} aria-hidden />
            <span>Source text re-hashed on load and matches the sealed file.</span>
          </div>
        )}
        {error?.status === 409 && (
          <div className="note note-bad" role="alert">
            <ShieldAlert size={16} aria-hidden />
            <span>
              <strong>Integrity mismatch.</strong> This file has changed since it was sealed and is blocked. The event has been
              logged.
            </span>
          </div>
        )}
        {error && error.status !== 409 && <div className="note note-bad">{error.message}</div>}
        {text === null && !error && <p className="muted pad">Loading source…</p>}
        <div className="drawer-body">
          {text !== null && (
            <pre className="doc doc-source">
              {parts.map((p, i) => {
                if (!p.mark) return <span key={i}>{p.text}</span>
                const ref = !firstAssigned
                  ? (el: HTMLElement | null) => {
                      first.current = el
                    }
                  : undefined
                firstAssigned = true
                return (
                  <mark key={i} ref={ref}>
                    {p.text}
                  </mark>
                )
              })}
            </pre>
          )}
        </div>
      </aside>
    </div>
  )
}
