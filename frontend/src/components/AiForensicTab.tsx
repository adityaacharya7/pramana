import {
  CheckCircle2,
  Copy,
  FileText,
  Gavel,
  RefreshCw,
  Shield,
  Sparkles,
  Users,
  Zap,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, type CaseDetail } from '../api'

interface AnalysisData {
  typology: string
  risk_score: number
  confidence: string
  summary: string
  modus_operandi: string[]
  statutory_sections: Array<{ section: string; desc: string }>
  syndicate_hierarchy: Array<{ role: string; entity: string; details: string }>
  immediate_actions: string[]
}

export default function AiForensicTab({ kase }: { kase: CaseDetail }) {
  const [loading, setLoading] = useState(false)
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [draftingNotice, setDraftingNotice] = useState(false)
  const [noticeResult, setNoticeResult] = useState<string | null>(null)
  const [noticeType, setNoticeType] = useState('SECTION_106_BNSS')

  const runAnalysis = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.ai.analyzeCase(kase.id)
      setAnalysis(res.analysis)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    runAnalysis()
  }, [kase.id])

  const draftQuickNotice = async (type: string) => {
    setNoticeType(type)
    setDraftingNotice(true)
    try {
      const res = await api.ai.draftNotice({
        case_id: kase.id,
        notice_type: type,
        // No invented figures: the officer fills in the account, amount and
        // UTR from the verified records before issuing the notice.
        entity_name: 'Nodal Officer, [bank to be filled by officer]',
        entity_identifier: '[account number to be filled by officer]',
      })
      setNoticeResult(res.notice_text)
    } catch (e) {
      alert(`Notice drafting failed: ${e instanceof Error ? e.message : 'Unknown error'}`)
    } finally {
      setDraftingNotice(false)
    }
  }

  const copyText = (text: string) => {
    navigator.clipboard.writeText(text)
    alert('Copied to clipboard!')
  }

  return (
    <div className="gov-card-panel" style={{ padding: '24px', marginTop: 16 }}>
      {/* HEADER SECTION */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border, #e2e8f0)', paddingBottom: 16, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 10, background: 'linear-gradient(135deg, #0b2545 0%, #1e3a8a 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#f59e0b', boxShadow: '0 4px 12px rgba(11,37,69,0.2)' }}>
            <Sparkles size={24} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, color: 'var(--text, #0b2545)', display: 'flex', alignItems: 'center', gap: 8 }}>
              UPAKARAKA (उपकारक) Forensic Intelligence
              <span style={{ fontSize: 11, background: '#f59e0b', color: '#07192f', padding: '2px 8px', borderRadius: 4, fontWeight: 700 }}>
                GEMINI 3.5
              </span>
            </h2>
            <div style={{ fontSize: 12.5, color: 'var(--text-muted, #64748b)', marginTop: 2 }}>
              Automated Modus Operandi classification, syndicate profiling & statutory BNSS action checklist for {kase.id}
            </div>
          </div>
        </div>

        <button
          className="btn btn-secondary"
          onClick={runAnalysis}
          disabled={loading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          <RefreshCw size={14} className={loading ? 'pramana-ai-spin' : ''} />
          {loading ? 'Analyzing with Gemini...' : 'Re-run Analysis'}
        </button>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '60px 20px' }}>
          <RefreshCw size={36} className="pramana-ai-spin" style={{ color: '#0047ba', margin: '0 auto 16px auto' }} />
          <h3 style={{ margin: '0 0 6px 0', fontSize: 16 }}>Analyzing Investigation Records & Modus Operandi...</h3>
          <p className="muted small">Extracting suspect hierarchy, financial layering flows, and statutory BNS citations via Google Gemini.</p>
        </div>
      )}

      {error && (
        <div style={{ padding: 16, background: '#fee2e2', border: '1px solid #f87171', borderRadius: 8, color: '#991b1b', marginBottom: 20 }}>
          <strong>Error running AI Analysis:</strong> {error}
          <div style={{ marginTop: 8 }}>
            <button className="btn btn-secondary" onClick={runAnalysis} style={{ fontSize: 12 }}>
              Try Again
            </button>
          </div>
        </div>
      )}

      {analysis && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* TOP METRICS CARDS */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
            <div style={{ padding: 14, background: 'var(--subtle-bg, #f8fafc)', border: '1px solid var(--border, #e2e8f0)', borderRadius: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>Fraud Typology</div>
              <div style={{ fontSize: 15, fontWeight: 750, color: '#0047ba', marginTop: 4 }}>{analysis.typology}</div>
            </div>

            <div style={{ padding: 14, background: 'var(--subtle-bg, #f8fafc)', border: '1px solid var(--border, #e2e8f0)', borderRadius: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>Syndicate Threat Score</div>
              <div style={{ fontSize: 18, fontWeight: 800, color: '#dc2626', marginTop: 4 }}>
                {analysis.risk_score} / 100 <span style={{ fontSize: 11, fontWeight: 600, color: '#64748b' }}>({analysis.confidence} CONFIDENCE)</span>
              </div>
            </div>

            <div style={{ padding: 14, background: 'var(--subtle-bg, #f8fafc)', border: '1px solid var(--border, #e2e8f0)', borderRadius: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>Statutory Framework</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#16a34a', marginTop: 4 }}>
                BNS, 2023 &amp; BNSS, 2023
              </div>
            </div>
          </div>

          {/* EXECUTIVE SYNOPSIS */}
          <div style={{ padding: 16, background: 'rgba(0, 71, 186, 0.04)', border: '1px solid rgba(0, 71, 186, 0.15)', borderRadius: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 750, color: '#0047ba', textTransform: 'uppercase', marginBottom: 6 }}>
              <Shield size={14} /> Executive Forensic Intelligence Summary
            </div>
            <div style={{ fontSize: 13.5, lineHeight: 1.6, color: 'var(--text, #1e293b)' }}>
              {analysis.summary}
            </div>
          </div>

          {/* TWO COLUMN GRID: MODUS OPERANDI & SYNDICATE HIERARCHY */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20 }}>
            {/* MODUS OPERANDI BREAKDOWN */}
            <div style={{ border: '1px solid var(--border, #e2e8f0)', borderRadius: 8, padding: 16, background: 'var(--surface, #ffffff)' }}>
              <div style={{ fontSize: 13, fontWeight: 750, color: 'var(--text, #0b2545)', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
                <Zap size={16} color="#d97706" /> Modus Operandi (Chronological Execution)
              </div>
              <ol style={{ margin: 0, paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {analysis.modus_operandi.map((step, idx) => (
                  <li key={idx} style={{ fontSize: 13, lineHeight: 1.5 }}>
                    {step}
                  </li>
                ))}
              </ol>
            </div>

            {/* SYNDICATE MULE HIERARCHY */}
            <div style={{ border: '1px solid var(--border, #e2e8f0)', borderRadius: 8, padding: 16, background: 'var(--surface, #ffffff)' }}>
              <div style={{ fontSize: 13, fontWeight: 750, color: 'var(--text, #0b2545)', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
                <Users size={16} color="#0047ba" /> Identified Syndicate Structure &amp; Mules
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {analysis.syndicate_hierarchy.map((mule, idx) => (
                  <div key={idx} style={{ padding: '8px 10px', background: 'var(--subtle-bg, #f8fafc)', borderRadius: 6, border: '1px solid var(--border, #e2e8f0)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: '#0b2545' }}>{mule.role}</span>
                      <span style={{ fontSize: 11, background: '#e2e8f0', padding: '1px 6px', borderRadius: 4, fontFamily: 'monospace' }}>{mule.entity}</span>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted, #64748b)', marginTop: 2 }}>{mule.details}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* STATUTORY PENAL PROVISIONS */}
          <div style={{ border: '1px solid var(--border, #e2e8f0)', borderRadius: 8, padding: 16, background: 'var(--surface, #ffffff)' }}>
            <div style={{ fontSize: 13, fontWeight: 750, color: 'var(--text, #0b2545)', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
              <Gavel size={16} color="#7c3aed" /> Statutory Legal Framework (BNS, 2023 &amp; IT Act)
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 10 }}>
              {analysis.statutory_sections.map((sec, idx) => (
                <div key={idx} style={{ padding: 10, background: 'var(--subtle-bg, #f8fafc)', borderRadius: 6, borderLeft: '3px solid #7c3aed' }}>
                  <div style={{ fontSize: 12.5, fontWeight: 750, color: '#7c3aed' }}>{sec.section}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--text, #334155)', marginTop: 2 }}>{sec.desc}</div>
                </div>
              ))}
            </div>
          </div>

          {/* IMMEDIATE INVESTIGATION ACTIONS CHECKLIST */}
          <div style={{ border: '1px solid var(--border, #e2e8f0)', borderRadius: 8, padding: 16, background: '#f0fdf4', borderColor: '#bbf7d0' }}>
            <div style={{ fontSize: 13, fontWeight: 750, color: '#166534', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
              <CheckCircle2 size={16} color="#16a34a" /> Immediate Statutory Action Checklist for IO
            </div>
            <ul style={{ margin: 0, paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {analysis.immediate_actions.map((act, idx) => (
                <li key={idx} style={{ fontSize: 13, color: '#14532d', lineHeight: 1.4 }}>
                  <strong>Priority {idx + 1}:</strong> {act}
                </li>
              ))}
            </ul>
          </div>

          {/* ONE-CLICK COURT-READY NOTICE DRAFTING */}
          <div style={{ border: '1.5px solid #0047ba', borderRadius: 8, padding: 18, background: 'var(--surface, #ffffff)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 15, color: '#0047ba', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <FileText size={18} /> One-Click Statutory Requisition Drafter
                </h3>
                <div style={{ fontSize: 12, color: 'var(--text-muted, #64748b)', marginTop: 2 }}>
                  Directly draft official Section 106 BNSS (Account Freeze) or Section 94 BNSS (Bank Summons) notices for this case.
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => draftQuickNotice('SECTION_106_BNSS')}
                  disabled={draftingNotice}
                  style={{ fontSize: 12 }}
                >
                  <Sparkles size={14} /> Draft Sec 106 BNSS (Freeze)
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => draftQuickNotice('SECTION_94_BNSS')}
                  disabled={draftingNotice}
                  style={{ fontSize: 12 }}
                >
                  <FileText size={14} /> Draft Sec 94 BNSS (Summons)
                </button>
              </div>
            </div>

            {noticeResult && (
              <div style={{ marginTop: 14, border: '1px solid var(--border, #cbd5e1)', borderRadius: 6, overflow: 'hidden' }}>
                <div style={{ padding: '8px 12px', background: 'var(--subtle-bg, #f1f5f9)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, fontWeight: 700 }}>
                  <span>Generated Notice ({noticeType})</span>
                  <button className="btn btn-secondary" onClick={() => copyText(noticeResult)} style={{ padding: '3px 8px', fontSize: 11 }}>
                    <Copy size={12} /> Copy to Clipboard
                  </button>
                </div>
                <pre style={{ margin: 0, padding: 14, fontSize: 12, lineHeight: 1.5, background: 'var(--surface, #ffffff)', maxHeight: 320, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace' }}>
                  {noticeResult}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
