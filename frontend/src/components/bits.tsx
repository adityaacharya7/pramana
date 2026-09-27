import { AlertTriangle, Check, Copy, ShieldAlert, ShieldCheck, ShieldQuestion } from 'lucide-react'
import { useState } from 'react'
import type { Integrity } from '../api'
import { shortHash } from '../format'

export function IntegrityBadge({ status }: { status: Integrity }) {
  if (status === 'OK')
    return (
      <span className="badge badge-ok">
        <ShieldCheck size={14} aria-hidden /> Sealed
      </span>
    )
  if (status === 'MISMATCH')
    return (
      <span className="badge badge-bad">
        <ShieldAlert size={14} aria-hidden /> Integrity mismatch
      </span>
    )
  return (
    <span className="badge badge-bad">
      <ShieldQuestion size={14} aria-hidden /> File missing
    </span>
  )
}

export function Hash({ value, full = false }: { value: string; full?: boolean }) {
  const [copied, setCopied] = useState(false)
  return (
    <span className="hash">
      <code title={value} className={full ? 'hash-full' : undefined}>{full ? value : shortHash(value)}</code>
      <button
        className="icon-btn"
        aria-label="Copy SHA-256"
        title="Copy full SHA-256"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(value)
            setCopied(true)
            setTimeout(() => setCopied(false), 1400)
          } catch {
            // clipboard unavailable
          }
        }}
      >
        {copied ? <Check size={13} /> : <Copy size={13} />}
      </button>
    </span>
  )
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null
  return (
    <div className="note note-bad" role="alert">
      <AlertTriangle size={16} aria-hidden />
      <span>{error}</span>
    </div>
  )
}

export function AccessChip({ access }: { access: string }) {
  const label = access === 'owner' ? 'Owner' : access === 'member' ? 'Member' : 'Unit case'
  return <span className={`chip chip-${access}`}>{label}</span>
}
