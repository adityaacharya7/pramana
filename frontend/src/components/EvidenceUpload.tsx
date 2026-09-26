import { CheckCircle2, FileUp, Lock, XCircle } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { api, sha256Hex, type Evidence } from '../api'
import { formatBytes, guessKind, KIND_LABELS, shortHash } from '../format'

type Status = 'hashing' | 'ready' | 'sealing' | 'sealed' | 'rejected'

interface Item {
  key: string
  file: File
  kind: string
  localSha?: string
  status: Status
  message?: string
  result?: Evidence
}

const ACCEPT = '.csv,.txt,.log,.pdf'

export default function EvidenceUpload({ caseId, onSealed }: { caseId: string; onSealed: (ev: Evidence) => void }) {
  const [items, setItems] = useState<Item[]>([])
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const patch = (key: string, p: Partial<Item>) => setItems((xs) => xs.map((x) => (x.key === key ? { ...x, ...p } : x)))

  function add(files: FileList | null) {
    if (!files) return
    const next = [...files].map<Item>((file) => ({
      key: `${file.name}-${file.size}-${file.lastModified}-${Math.random()}`,
      file,
      kind: guessKind(file.name),
      status: 'hashing',
    }))
    setItems((xs) => [...xs.filter((x) => x.status !== 'sealed'), ...next])
    // Hash locally first, so the officer can see the server sealed exactly
    // the bytes they chose.
    next.forEach(async (it) => {
      try {
        patch(it.key, { localSha: await sha256Hex(it.file), status: 'ready' })
      } catch {
        patch(it.key, { status: 'ready' })
      }
    })
  }

  async function sealAll() {
    setBusy(true)
    for (const it of items.filter((x) => x.status === 'ready')) {
      patch(it.key, { status: 'sealing', message: undefined })
      try {
        const ev = await api.upload(caseId, it.file, it.kind)
        patch(it.key, { status: 'sealed', result: ev })
        onSealed(ev)
      } catch (e) {
        patch(it.key, { status: 'rejected', message: e instanceof Error ? e.message : 'Upload failed.' })
      }
    }
    setBusy(false)
  }

  const ready = items.filter((x) => x.status === 'ready').length
  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    add(e.dataTransfer.files)
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Add evidence</h2>
        <span className="muted small">CSV, TXT or PDF text · each file is SHA-256 sealed on arrival</span>
      </div>
      <div
        className={`dropzone${dragging ? ' dropzone-active' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => input.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
      >
        <FileUp size={22} aria-hidden />
        <span>
          Drop files here or <u>choose files</u>
        </span>
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPT}
          hidden
          onChange={(e) => {
            add(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      {items.length > 0 && (
        <ul className="upload-list">
          {items.map((it) => (
            <li key={it.key} className={`upload-item upload-${it.status}`}>
              <div className="upload-file">
                <span className="upload-name">{it.file.name}</span>
                <span className="muted small">{formatBytes(it.file.size)}</span>
              </div>
              <select
                value={it.kind}
                disabled={it.status !== 'ready'}
                onChange={(e) => patch(it.key, { kind: e.target.value })}
                aria-label={`Evidence type for ${it.file.name}`}
              >
                {Object.entries(KIND_LABELS).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </select>
              <div className="upload-status">
                {it.status === 'hashing' && <span className="muted small">Hashing locally…</span>}
                {it.status === 'ready' && it.localSha && (
                  <span className="muted small mono" title={it.localSha}>
                    local {shortHash(it.localSha, 8, 4)}
                  </span>
                )}
                {it.status === 'sealing' && <span className="muted small">Sealing…</span>}
                {it.status === 'sealed' && it.result && (
                  <span className="ok small">
                    <CheckCircle2 size={14} aria-hidden /> Sealed
                    {it.localSha &&
                      (it.localSha === it.result.sha256 ? ' · hash matches your copy' : ' · hash differs from your copy')}
                    {it.result.duplicate_of && ' · identical to a file already in this case'}
                  </span>
                )}
                {it.status === 'rejected' && (
                  <span className="bad small">
                    <XCircle size={14} aria-hidden /> {it.message}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {ready > 0 && (
        <div className="panel-actions">
          <button className="btn btn-primary" disabled={busy} onClick={sealAll}>
            <Lock size={15} aria-hidden /> Seal and upload {ready} file{ready === 1 ? '' : 's'}
          </button>
          <span className="muted small">Uploads are recorded in the audit log with their hash.</span>
        </div>
      )}
    </section>
  )
}
