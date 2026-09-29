import {
  Bot,
  Check,
  Copy,
  FileText,
  Flame,
  Maximize2,
  Minimize2,
  RefreshCw,
  Send,
  Shield,
  Sparkles,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from '../api'
import FormattedMarkdown from './FormattedMarkdown'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  isTyping?: boolean
  error?: boolean
}

export default function AiCopilot() {
  const [isOpen, setIsOpen] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        '**PRAMANA AI Forensic Copilot (दिव्य दृष्टि)** is active.\n\nI provide real-time statutory intelligence, Modus Operandi breakdown, money trail attribution analysis, and court-ready requisition drafting under the **Bharatiya Nagarik Suraksha Sanhita (BNSS)** and **IT Act, 2000**.\n\nHow may I assist your investigation today?',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ])
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'chat' | 'notice'>('chat')

  // Statutory Notice Draft State
  const [noticeType, setNoticeType] = useState('SECTION_106_BNSS')
  const [noticeBank, setNoticeBank] = useState('Axis Bank Ltd.')
  const [noticeAccount, setNoticeAccount] = useState('918020045582910')
  const [noticeAmount, setNoticeAmount] = useState('1,75,000')
  const [noticeUtr, setNoticeUtr] = useState('IMPS/UTR Ref: 624519800214')
  const [noticeDraft, setNoticeDraft] = useState<string | null>(null)
  const [noticeDrafting, setNoticeDrafting] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const location = useLocation()

  // Detect current case from URL (e.g. /cases/C-101)
  const caseMatch = location.pathname.match(/\/cases\/([^/]+)/)
  const activeCaseId = caseMatch ? decodeURIComponent(caseMatch[1]) : undefined

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isOpen])

  const copyText = (id: string, text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const handleSend = async (textToSend?: string) => {
    const q = (textToSend ?? input).trim()
    if (!q || loading) return

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: q,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const history = messages
        .filter((m) => m.id !== 'welcome' && !m.error)
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content }))

      const res = await api.ai.chat(q, activeCaseId, history)

      const assistantMsg: Message = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: res.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err) {
      const errMsg: Message = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `Error connecting to PRAMANA AI service: ${err instanceof Error ? err.message : 'Unknown error'}. Please verify connection.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        error: true,
      }
      setMessages((prev) => [...prev, errMsg])
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateNotice = async () => {
    if (!activeCaseId) {
      alert('Please open a case (e.g. C-101) to draft a statutory notice with case references.')
      return
    }
    setNoticeDrafting(true)
    try {
      const res = await api.ai.draftNotice({
        case_id: activeCaseId,
        notice_type: noticeType,
        entity_name: noticeBank,
        entity_identifier: noticeAccount,
        amount: noticeAmount,
        utr: noticeUtr,
      })
      setNoticeDraft(res.notice_text)
    } catch (e) {
      alert(`Drafting error: ${e instanceof Error ? e.message : 'Failed to draft notice'}`)
    } finally {
      setNoticeDrafting(false)
    }
  }

  const quickPrompts = [
    { label: 'Deep MO & Syndicate Analysis', prompt: `Perform a deep forensic analysis and Modus Operandi breakdown for case ${activeCaseId || 'C-101'}.` },
    { label: 'Money Trail & Cashouts', prompt: `Trace the money trail in case ${activeCaseId || 'C-101'} and identify the Layer-1, Layer-2, and final cashout mule accounts.` },
    { label: 'Applicable BNS & IT Sections', prompt: `What statutory penal sections under Bharatiya Nyaya Sanhita (BNS) and the IT Act should be added to the FIR in case ${activeCaseId || 'C-101'}?` },
    { label: 'Missing Evidence Checklist', prompt: `Review the evidence receipts and identify missing evidence required to secure a conviction in case ${activeCaseId || 'C-101'}.` },
  ]

  return (
    <>
      {/* FLOATING TRIGGER BUTTON */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="pramana-ai-fab"
          aria-label="Open PRAMANA AI Copilot"
          title="Open PRAMANA AI Copilot (Powered by Google Gemini)"
        >
          <div className="pramana-ai-fab-icon-box">
            <Sparkles size={20} className="pramana-ai-sparkle-spin" />
          </div>
          <div className="pramana-ai-fab-label">
            <span className="pramana-ai-fab-title">PRAMANA AI</span>
            <span className="pramana-ai-fab-sub">Forensic Copilot</span>
          </div>
          {activeCaseId && (
            <span className="pramana-ai-fab-case-badge">{activeCaseId}</span>
          )}
        </button>
      )}

      {/* EXPANDED COPILOT PANEL */}
      {isOpen && (
        <div className={`pramana-ai-panel ${isExpanded ? 'pramana-ai-panel-expanded' : ''}`}>
          {/* HEADER */}
          <div className="pramana-ai-header">
            <div className="pramana-ai-header-left">
              <div className="pramana-ai-badge">
                <Sparkles size={16} />
              </div>
              <div>
                <div className="pramana-ai-title-row">
                  <span className="pramana-ai-title">PRAMANA AI Copilot</span>
                  <span className="pramana-ai-tag">Gemini 3.5</span>
                </div>
                <div className="pramana-ai-sub">
                  दिव्य दृष्टि · Forensic Intelligence & Legal Requisitions
                  {activeCaseId && <strong style={{ color: '#F59E0B', marginLeft: 6 }}>[Active: {activeCaseId}]</strong>}
                </div>
              </div>
            </div>

            <div className="pramana-ai-header-actions">
              <button
                className="pramana-ai-hdr-btn"
                onClick={() => setIsExpanded(!isExpanded)}
                title={isExpanded ? 'Restore window size' : 'Maximize window'}
              >
                {isExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              </button>
              <button
                className="pramana-ai-hdr-btn"
                onClick={() => setIsOpen(false)}
                title="Minimize Copilot"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* TAB BAR */}
          <div className="pramana-ai-tabs">
            <button
              className={`pramana-ai-tab ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              <Bot size={15} /> Forensic Assistant
            </button>
            <button
              className={`pramana-ai-tab ${activeTab === 'notice' ? 'active' : ''}`}
              onClick={() => setActiveTab('notice')}
            >
              <FileText size={15} /> Statutory Notice Drafter (BNSS)
            </button>
          </div>

          {/* TAB 1: INTERACTIVE CHAT */}
          {activeTab === 'chat' && (
            <div className="pramana-ai-body">
              <div className="pramana-ai-messages">
                {messages.map((m) => (
                  <div key={m.id} className={`pramana-ai-bubble-wrap pramana-ai-${m.role}`}>
                    <div className="pramana-ai-bubble-header">
                      <span className="pramana-ai-sender">
                        {m.role === 'assistant' ? (
                          <>
                            <Shield size={13} style={{ color: '#0047ba' }} /> PRAMANA AI
                          </>
                        ) : (
                          'Investigating Officer'
                        )}
                      </span>
                      <span className="pramana-ai-time">{m.timestamp}</span>
                      {m.role === 'assistant' && (
                        <button
                          className="pramana-ai-copy-btn"
                          onClick={() => copyText(m.id, m.content)}
                          title="Copy AI response"
                        >
                          {copiedId === m.id ? <Check size={13} color="#16a34a" /> : <Copy size={13} />}
                        </button>
                      )}
                    </div>

                    <div className="pramana-ai-bubble-content">
                      <FormattedMarkdown content={m.content} />
                    </div>
                  </div>
                ))}

                {loading && (
                  <div className="pramana-ai-bubble-wrap pramana-ai-assistant">
                    <div className="pramana-ai-bubble-content pramana-ai-loading-box">
                      <RefreshCw size={16} className="pramana-ai-spin" />
                      <span>Synthesizing forensic intelligence with Gemini 3.5...</span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* QUICK PROMPTS CHIPS */}
              <div className="pramana-ai-quick-chips">
                <div className="pramana-ai-chips-label">
                  <Flame size={12} color="#f59e0b" /> Investigation Actions:
                </div>
                <div className="pramana-ai-chips-scroll">
                  {quickPrompts.map((p, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className="pramana-ai-chip"
                      onClick={() => handleSend(p.prompt)}
                      disabled={loading}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* INPUT FORM */}
              <form
                className="pramana-ai-input-form"
                onSubmit={(e) => {
                  e.preventDefault()
                  handleSend()
                }}
              >
                <input
                  type="text"
                  className="pramana-ai-input"
                  placeholder={
                    activeCaseId
                      ? `Ask PRAMANA AI about Case ${activeCaseId} (e.g. suspects, trail, law)...`
                      : 'Ask PRAMANA AI about cyber fraud, trail analysis, BNSS notices...'
                  }
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  disabled={loading}
                />
                <button
                  type="submit"
                  className="pramana-ai-send-btn"
                  disabled={!input.trim() || loading}
                  aria-label="Send message"
                >
                  <Send size={16} />
                </button>
              </form>
            </div>
          )}

          {/* TAB 2: STATUTORY NOTICE DRAFTER */}
          {activeTab === 'notice' && (
            <div className="pramana-ai-body pramana-ai-notice-body">
              <div className="pramana-ai-notice-form">
                <div className="pramana-ai-notice-desc">
                  Generate court-admissible requisitions formatted under the <strong>Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS)</strong>.
                </div>

                <div className="pramana-ai-field-grid">
                  <div>
                    <label className="pramana-ai-label">Statutory Notice Type</label>
                    <select
                      className="pramana-ai-select"
                      value={noticeType}
                      onChange={(e) => setNoticeType(e.target.value)}
                    >
                      <option value="SECTION_106_BNSS">Section 106 BNSS (Direct Debit Account Freeze)</option>
                      <option value="SECTION_94_BNSS">Section 94 BNSS (Summons for Bank Statements & KYC)</option>
                      <option value="SECTION_69A_IT_ACT">Section 69A IT Act (Emergency Website/Channel Takedown)</option>
                    </select>
                  </div>

                  <div>
                    <label className="pramana-ai-label">Target Entity / Bank Name</label>
                    <input
                      type="text"
                      className="pramana-ai-input"
                      value={noticeBank}
                      onChange={(e) => setNoticeBank(e.target.value)}
                      placeholder="e.g. Axis Bank Ltd. Nodal Officer"
                    />
                  </div>

                  <div>
                    <label className="pramana-ai-label">Account / Identifier to Freeze</label>
                    <input
                      type="text"
                      className="pramana-ai-input"
                      value={noticeAccount}
                      onChange={(e) => setNoticeAccount(e.target.value)}
                      placeholder="e.g. 918020045582910 or UPI VPA"
                    />
                  </div>

                  <div>
                    <label className="pramana-ai-label">Disputed Amount</label>
                    <input
                      type="text"
                      className="pramana-ai-input"
                      value={noticeAmount}
                      onChange={(e) => setNoticeAmount(e.target.value)}
                      placeholder="e.g. 1,75,000"
                    />
                  </div>

                  <div style={{ gridColumn: 'span 2' }}>
                    <label className="pramana-ai-label">Transaction / UTR Reference</label>
                    <input
                      type="text"
                      className="pramana-ai-input"
                      value={noticeUtr}
                      onChange={(e) => setNoticeUtr(e.target.value)}
                      placeholder="e.g. IMPS/UTR Ref: 624519800214"
                    />
                  </div>
                </div>

                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleGenerateNotice}
                  disabled={noticeDrafting}
                  style={{ width: '100%', marginTop: 12, height: 40, fontWeight: 700 }}
                >
                  {noticeDrafting ? (
                    <>
                      <RefreshCw size={15} className="pramana-ai-spin" /> Drafting Official Notice...
                    </>
                  ) : (
                    <>
                      <Sparkles size={15} /> Generate Court-Ready Requisition with Gemini
                    </>
                  )}
                </button>
              </div>

              {noticeDraft && (
                <div className="pramana-ai-notice-result">
                  <div className="pramana-ai-notice-result-header">
                    <span>Draft Requisition Preview</span>
                    <button
                      className="pramana-ai-copy-btn"
                      onClick={() => copyText('notice', noticeDraft)}
                      title="Copy full text"
                    >
                      {copiedId === 'notice' ? <Check size={14} color="#16a34a" /> : <Copy size={14} />} Copy Document
                    </button>
                  </div>
                  <pre className="pramana-ai-notice-text">{noticeDraft}</pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </>
  )
}
