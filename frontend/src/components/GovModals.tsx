import { AlertCircle, CheckCircle2, FileText, PhoneCall, ShieldAlert, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'

export function HelplineModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  if (!isOpen) return null

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        className="modal gov-modal"
        role="dialog"
        aria-modal="true"
        onMouseDown={(e) => e.stopPropagation()}
        style={{ maxWidth: 520 }}
      >
        <div className="modal-head gov-modal-head">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                background: '#0e7490',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
              }}
            >
              <PhoneCall size={18} />
            </div>
            <div>
              <h2 style={{ fontSize: 17, margin: 0 }}>National Cyber Crime Helpline</h2>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>राष्ट्रीय साइबर अपराध हेल्पलाइन · 1930</div>
            </div>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="modal-body" style={{ padding: '20px 24px', display: 'grid', gap: 16 }}>
          <div
            style={{
              background: '#eff6ff',
              border: '1px solid #bfdbfe',
              borderRadius: 8,
              padding: '14px 16px',
              display: 'flex',
              gap: 12,
            }}
          >
            <ShieldAlert size={22} style={{ color: '#1d4ed8', flexShrink: 0, marginTop: 2 }} />
            <div>
              <div style={{ fontWeight: 700, color: '#1e3a8a', fontSize: 14 }}>Toll-Free Helpline: 1930</div>
              <div style={{ fontSize: 13, color: '#1e40af', marginTop: 4, lineHeight: 1.45 }}>
                Financial Fraud victims must call <strong>1930</strong> immediately within the <em>Golden Hour</em> to initiate fund freeze through the Citizen Financial Cyber Fraud Reporting and Management System (CFCFRMS).
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gap: 10, fontSize: 13 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
              <span style={{ color: 'var(--muted)' }}>Official Portal:</span>
              <a href="https://cybercrime.gov.in" target="_blank" rel="noreferrer" style={{ fontWeight: 600 }}>
                cybercrime.gov.in
              </a>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
              <span style={{ color: 'var(--muted)' }}>Operating Hours:</span>
              <span style={{ fontWeight: 600 }}>24x7 × 365 Days</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
              <span style={{ color: 'var(--muted)' }}>Administered By:</span>
              <span style={{ fontWeight: 600 }}>Indian Cyber Crime Coordination Centre (I4C), MHA</span>
            </div>
          </div>
        </div>
        <div className="modal-foot">
          <button className="btn btn-primary" onClick={onClose} style={{ marginLeft: 'auto' }}>
            Understood / समझा
          </button>
        </div>
      </div>
    </div>
  )
}

export function RegisterComplaintModal({
  isOpen,
  onClose,
  onSubmit,
}: {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: { firNo: string; complainant: string; title: string; city: string; unit: string }) => void
}) {
  const [firNo, setFirNo] = useState('')
  const [complainant, setComplainant] = useState('')
  const [title, setTitle] = useState('Digital arrest impersonation complaint')
  const [city, setCity] = useState('Mumbai')
  const [unit, setUnit] = useState('MUM-CYB')

  if (!isOpen) return null

  const handleCityChange = (c: string) => {
    setCity(c)
    if (c === 'Mumbai') setUnit('MUM-CYB')
    else if (c === 'Delhi') setUnit('DEL-CYB')
    else if (c === 'Bengaluru') setUnit('BLR-CEN')
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!firNo.trim() || !complainant.trim()) return
    onSubmit({ firNo: firNo.trim(), complainant: complainant.trim(), title: title.trim(), city, unit })
    onClose()
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        className="modal gov-modal"
        role="dialog"
        aria-modal="true"
        onMouseDown={(e) => e.stopPropagation()}
        style={{ maxWidth: 560 }}
      >
        <div className="modal-head gov-modal-head">
          <div>
            <h2 style={{ fontSize: 18, margin: 0 }}>Register New Complaint</h2>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>नई शिकायत दर्ज करें · PRAMANA Case Ingestion</div>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ padding: '20px 24px', display: 'grid', gap: 14 }}>
            <label className="gov-form-field">
              <span className="gov-form-label">
                FIR Number / प्राथमिकी संख्या <span style={{ color: '#ef4444' }}>*</span>
              </span>
              <input
                type="text"
                placeholder="e.g. 0495/2026"
                value={firNo}
                onChange={(e) => setFirNo(e.target.value)}
                required
                className="gov-input"
              />
            </label>

            <label className="gov-form-field">
              <span className="gov-form-label">
                Complainant Name / शिकायतकर्ता का नाम <span style={{ color: '#ef4444' }}>*</span>
              </span>
              <input
                type="text"
                placeholder="e.g. Ramesh Chandra Verma"
                value={complainant}
                onChange={(e) => setComplainant(e.target.value)}
                required
                className="gov-input"
              />
            </label>

            <label className="gov-form-field">
              <span className="gov-form-label">Complaint Nature / शिकायत की प्रकृति</span>
              <select value={title} onChange={(e) => setTitle(e.target.value)} className="gov-input">
                <option value="Digital arrest impersonation complaint">Digital arrest impersonation complaint</option>
                <option value="Online task-based job offer complaint">Online task-based job offer complaint</option>
                <option value="Marketplace buyer QR payment complaint">Marketplace buyer QR payment complaint</option>
                <option value="Fake customer care refund complaint">Fake customer care refund complaint</option>
                <option value="Instant loan application blackmail">Instant loan application blackmail</option>
                <option value="Trading investment portal fraud">Trading investment portal fraud</option>
              </select>
            </label>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <label className="gov-form-field">
                <span className="gov-form-label">Jurisdiction City / शहर</span>
                <select value={city} onChange={(e) => handleCityChange(e.target.value)} className="gov-input">
                  <option value="Mumbai">Mumbai</option>
                  <option value="Delhi">Delhi</option>
                  <option value="Bengaluru">Bengaluru</option>
                </select>
              </label>

              <label className="gov-form-field">
                <span className="gov-form-label">Cyber Unit / इकाई</span>
                <input type="text" value={unit} readOnly className="gov-input" style={{ background: '#f1f5f9' }} />
              </label>
            </div>
          </div>
          <div className="modal-foot">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Cancel / रद्द करें
            </button>
            <button type="submit" className="btn btn-primary" style={{ background: '#0b57d0' }}>
              Register Complaint / दर्ज करें
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export function NotificationPopover({
  isOpen,
  onClose,
}: {
  isOpen: boolean
  onClose: () => void
}) {
  if (!isOpen) return null

  const items = [
    {
      id: 1,
      title: 'Evidence Hash Verified',
      desc: 'Supplementary statement C-104 re-hashed and confirmed untampered.',
      time: '10 mins ago',
      type: 'ok',
    },
    {
      id: 2,
      title: 'Inter-Unit Lead Matched',
      desc: 'Shared mule account identified between MUM-CYB and BLR-CEN.',
      time: '1 hour ago',
      type: 'alert',
    },
    {
      id: 3,
      title: 'Daily Ledger Checkpoint Signed',
      desc: 'Ledger sequence #149 signed by Auditor K. Srinivasan.',
      time: '3 hours ago',
      type: 'info',
    },
  ]

  return (
    <>
      <div
        style={{ position: 'fixed', inset: 0, zIndex: 998 }}
        onClick={onClose}
      />
      <div
        className="gov-popover"
        style={{
          position: 'absolute',
          top: '100%',
          right: 0,
          marginTop: 8,
          width: 340,
          background: '#ffffff',
          borderRadius: 8,
          boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
          border: '1px solid #e2e8f0',
          zIndex: 999,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid #e2e8f0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: '#f8fafc',
          }}
        >
          <span style={{ fontWeight: 700, fontSize: 13.5, color: '#0f172a' }}>Notifications (3)</span>
          <span style={{ fontSize: 11.5, color: '#0284c7', fontWeight: 600, cursor: 'pointer' }}>Mark all read</span>
        </div>
        <div style={{ maxHeight: 320, overflowY: 'auto' }}>
          {items.map((it) => (
            <div
              key={it.id}
              style={{
                padding: '12px 16px',
                borderBottom: '1px solid #f1f5f9',
                display: 'flex',
                gap: 12,
                cursor: 'pointer',
              }}
              className="gov-notif-item"
            >
              {it.type === 'ok' ? (
                <CheckCircle2 size={16} style={{ color: '#16a34a', flexShrink: 0, marginTop: 2 }} />
              ) : it.type === 'alert' ? (
                <AlertCircle size={16} style={{ color: '#d97706', flexShrink: 0, marginTop: 2 }} />
              ) : (
                <FileText size={16} style={{ color: '#2563eb', flexShrink: 0, marginTop: 2 }} />
              )}
              <div style={{ display: 'grid', gap: 2 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>{it.title}</span>
                <span style={{ fontSize: 12, color: '#64748b', lineHeight: 1.35 }}>{it.desc}</span>
                <span style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{it.time}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
