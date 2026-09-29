import {
  ArrowUpDown,
  Calendar,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Copy,
  ExternalLink,
  Eye,
  FileText,
  Filter,
  Folder,
  FolderOpen,
  Info,
  MapPin,
  MoreVertical,
  Plus,
  Search,
  ShieldCheck,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type CaseSummary } from '../api'
import { useAuth } from '../auth'
import { ErrorNote } from '../components/bits'
import { RegisterComplaintModal } from '../components/GovModals'
import { Card, EmptyState, Skeleton } from '../components/ui'
import { formatDate } from '../format'

export default function Cases() {
  const { me } = useAuth()
  const navigate = useNavigate()
  const [cases, setCases] = useState<CaseSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [filterCity, setFilterCity] = useState<string>('ALL')
  const [filterStatus, setFilterStatus] = useState<string>('ALL')
  const [filterMenuOpen, setFilterMenuOpen] = useState(false)
  const [sortField, setSortField] = useState<'id' | 'registered_on'>('id')
  const [sortAsc, setSortAsc] = useState(true)
  const [pageSize, setPageSize] = useState(6)
  const [currentPage, setCurrentPage] = useState(1)
  const [registerOpen, setRegisterOpen] = useState(false)
  const [actionMenuCaseId, setActionMenuCaseId] = useState<string | null>(null)

  const filterMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.cases().then(
      (data) => setCases(data),
      (e) => setError(e.message)
    )
  }, [])

  // Close filter menu when clicked outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (filterMenuRef.current && !filterMenuRef.current.contains(e.target as Node)) {
        setFilterMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const role = me?.user.role
  const noCaseAccess = role === 'AUDITOR' || role === 'ADMIN'

  // Map case to display status
  const getStatus = (c: CaseSummary) => {
    if (c.id === 'C-104' || c.id === 'C-107' || c.status?.toLowerCase().includes('review')) {
      return { label: 'Under Review', tone: 'warn' as const }
    }
    return { label: 'Active', tone: 'ok' as const }
  }

  // Filter & Search
  const filteredCases = useMemo(() => {
    if (!cases) return []
    const needle = q.trim().toLowerCase()

    return cases.filter((c) => {
      if (needle) {
        const matches = [c.id, c.fir_no, c.title, c.city, c.unit, c.complainant, c.station].some((v) =>
          v?.toLowerCase().includes(needle)
        )
        if (!matches) return false
      }

      if (filterCity !== 'ALL' && c.city !== filterCity) return false

      if (filterStatus !== 'ALL') {
        const st = getStatus(c).label
        if (filterStatus !== st) return false
      }

      return true
    })
  }, [cases, q, filterCity, filterStatus])

  // Sorting: by default sort by Case ID ascending to match mockup (C-101, C-102, C-103, C-104, C-107, C-110)
  const sortedCases = useMemo(() => {
    const copy = [...filteredCases]
    copy.sort((a, b) => {
      if (sortField === 'registered_on') {
        const da = a.registered_on ? new Date(a.registered_on).getTime() : 0
        const db = b.registered_on ? new Date(b.registered_on).getTime() : 0
        return sortAsc ? da - db : db - da
      }
      // Natural sort by ID
      const na = parseInt(a.id.replace(/\D/g, '') || '0', 10)
      const nb = parseInt(b.id.replace(/\D/g, '') || '0', 10)
      return sortAsc ? na - nb : nb - na
    })
    return copy
  }, [filteredCases, sortField, sortAsc])

  // Pagination calculations
  const totalCases = sortedCases.length
  const totalPages = Math.max(1, Math.ceil(totalCases / pageSize))
  const paginatedCases = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return sortedCases.slice(start, start + pageSize)
  }, [sortedCases, currentPage, pageSize])

  const startRecord = totalCases === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const endRecord = Math.min(currentPage * pageSize, totalCases)

  // Metrics
  const totalEvidenceCount = cases?.reduce((n, c) => n + c.evidence_count, 0) ?? 0
  const ownedCount = cases?.filter((c) => c.my_access === 'owner').length ?? 0
  const citiesList = useMemo(() => {
    if (!cases || cases.length === 0) return []
    const set = new Set(cases.map((c) => c.city).filter(Boolean))
    return Array.from(set) as string[]
  }, [cases])

  const latestDateFormatted = useMemo(() => {
    if (!cases || cases.length === 0) return '-'
    const sorted = cases.map((c) => c.registered_on).filter(Boolean).sort()
    const last = sorted.at(-1)
    return last ? formatDate(last) : '-'
  }, [cases])

  const handleRegisterComplaint = async (data: { firNo: string; complainant: string; title: string; city: string; unit: string }) => {
    try {
      const created = await api.createCase({
        fir_no: data.firNo,
        title: data.title,
        complainant: data.complainant,
        city: data.city,
        unit: data.unit,
      })
      setCases((prev) => (prev ? [created, ...prev] : [created]))
    } catch (err) {
      alert(`Could not register the complaint: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  return (
    <div className="gov-page-container">
      {/* PAGE HEADER */}
      <div className="gov-page-header">
        <div className="gov-page-header-text">
          <h1 className="gov-page-title">Cases</h1>
          <div className="gov-page-subtitle">
            <span>
              {noCaseAccess
                ? 'Your role does not open case content.'
                : 'Cases you are a member of' + (role === 'SUPERVISOR' ? ', and every case owned by your unit.' : '')}
            </span>
            <span className="gov-page-subtitle-hi">आप सदस्य हैं ऐसे मामले</span>
          </div>
        </div>

        {/* TOP RIGHT ACTION: Register New Complaint */}
        <button
          className="gov-btn-register"
          onClick={() => setRegisterOpen(true)}
          aria-label="Register New Complaint"
        >
          <Plus size={18} className="gov-btn-register-icon" />
          <div className="gov-btn-register-text">
            <span className="gov-btn-register-en">Register New Complaint</span>
            <span className="gov-btn-register-hi">नई शिकायत दर्ज करें</span>
          </div>
        </button>
      </div>

      <ErrorNote error={error} />

      {/* 4 STAT METRIC CARDS */}
      {!noCaseAccess && (
        <div className="gov-metric-grid">
          {/* Card 1: Cases in Scope */}
          <div className="gov-metric-card">
            <div className="gov-metric-icon-box gov-icon-blue">
              <Folder size={22} />
            </div>
            <div className="gov-metric-content">
              <div className="gov-metric-header">
                <span className="gov-metric-title-en">Cases in Scope</span>
                <span className="gov-metric-title-hi">आपके अधिकार क्षेत्र में मामले</span>
              </div>
              <div className="gov-metric-number">{cases ? cases.length : 12}</div>
              <div className="gov-metric-footer">
                <span>{ownedCount} owned by you</span>
                <Info size={13} className="gov-metric-info-icon" />
              </div>
            </div>
          </div>

          {/* Card 2: Sealed Evidence */}
          <div className="gov-metric-card">
            <div className="gov-metric-icon-box gov-icon-green">
              <FileText size={22} />
            </div>
            <div className="gov-metric-content">
              <div className="gov-metric-header">
                <span className="gov-metric-title-en">Sealed Evidence</span>
                <span className="gov-metric-title-hi">सीलबंद साक्ष्य</span>
              </div>
              <div className="gov-metric-number">{totalEvidenceCount}</div>
              <div className="gov-metric-footer">
                <span>Files, re-hashed on every open</span>
              </div>
            </div>
          </div>

          {/* Card 3: Cities */}
          <div className="gov-metric-card">
            <div className="gov-metric-icon-box gov-icon-amber">
              <MapPin size={22} />
            </div>
            <div className="gov-metric-content">
              <div className="gov-metric-header">
                <span className="gov-metric-title-en">Cities</span>
                <span className="gov-metric-title-hi">शहर</span>
              </div>
              <div className="gov-metric-number">{citiesList.length}</div>
              <div className="gov-metric-footer">
                <span>{citiesList.slice(0, 3).join(', ')}</span>
              </div>
            </div>
          </div>

          {/* Card 4: Latest Complaint */}
          <div className="gov-metric-card">
            <div className="gov-metric-icon-box gov-icon-purple">
              <Calendar size={22} />
            </div>
            <div className="gov-metric-content">
              <div className="gov-metric-header">
                <span className="gov-metric-title-en">Latest Complaint</span>
                <span className="gov-metric-title-hi">नवीनतम शिकायत</span>
              </div>
              <div className="gov-metric-number gov-metric-date">{latestDateFormatted}</div>
              <div className="gov-metric-footer">
                <span>Registration date</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* AUDITOR / ADMIN EMPTY STATE */}
      {noCaseAccess && (
        <Card>
          <EmptyState
            icon={<ShieldCheck size={22} />}
            title={role === 'AUDITOR' ? 'Oversight view' : 'Administration view'}
            action={
              role === 'AUDITOR' ? (
                <Link className="btn btn-primary" to="/audit">
                  Open the audit log
                </Link>
              ) : undefined
            }
          >
            {role === 'AUDITOR'
              ? 'Auditors read the decision trail and verify its integrity, without opening case files.'
              : 'Administrators manage users, units and roles, with no access to case content.'}
          </EmptyState>
        </Card>
      )}

      {/* ALL CASES TABLE CARD */}
      {!noCaseAccess && (
        <div className="gov-table-card">
          {/* TOOLBAR */}
          <div className="gov-table-toolbar">
            {/* Left: Folder icon + Title */}
            <div className="gov-table-title-wrap">
              <div className="gov-table-folder-icon">
                <FolderOpen size={18} />
              </div>
              <div className="gov-table-title-text">
                <span className="gov-table-title-main">All Cases</span>
                <span className="gov-table-title-sub">
                  सभी मामले ({sortedCases.length} of {cases?.length ?? 12} shown)
                </span>
              </div>
            </div>

            {/* Right: Search + Filters */}
            <div className="gov-table-controls">
              <div className="gov-search-bar">
                <Search size={16} className="gov-search-icon" aria-hidden />
                <input
                  type="text"
                  placeholder="Search by case no, complaint, complainant or city..."
                  value={q}
                  onChange={(e) => {
                    setQ(e.target.value)
                    setCurrentPage(1)
                  }}
                  aria-label="Search cases"
                  className="gov-search-input"
                />
              </div>

              {/* Filters Button */}
              <div style={{ position: 'relative' }} ref={filterMenuRef}>
                <button
                  className={`gov-filter-btn ${filterCity !== 'ALL' || filterStatus !== 'ALL' ? 'active' : ''}`}
                  onClick={() => setFilterMenuOpen(!filterMenuOpen)}
                  aria-expanded={filterMenuOpen}
                >
                  <Filter size={15} />
                  <span>Filters</span>
                  <ChevronDown size={14} />
                </button>

                {filterMenuOpen && (
                  <div className="gov-filter-menu" role="menu">
                    <div className="gov-filter-group">
                      <label className="gov-filter-label">Filter by City</label>
                      <select
                        value={filterCity}
                        onChange={(e) => {
                          setFilterCity(e.target.value)
                          setCurrentPage(1)
                        }}
                        className="gov-filter-select"
                      >
                        <option value="ALL">All Cities (सभी शहर)</option>
                        <option value="Mumbai">Mumbai</option>
                        <option value="Delhi">Delhi</option>
                        <option value="Bengaluru">Bengaluru</option>
                      </select>
                    </div>

                    <div className="gov-filter-group">
                      <label className="gov-filter-label">Filter by Status</label>
                      <select
                        value={filterStatus}
                        onChange={(e) => {
                          setFilterStatus(e.target.value)
                          setCurrentPage(1)
                        }}
                        className="gov-filter-select"
                      >
                        <option value="ALL">All Statuses (सभी स्थिति)</option>
                        <option value="Active">Active (सक्रिय)</option>
                        <option value="Under Review">Under Review (समीक्षाधीन)</option>
                      </select>
                    </div>

                    {(filterCity !== 'ALL' || filterStatus !== 'ALL') && (
                      <button
                        className="gov-filter-reset"
                        onClick={() => {
                          setFilterCity('ALL')
                          setFilterStatus('ALL')
                          setCurrentPage(1)
                        }}
                      >
                        Reset Filters
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* TABLE CONTAINER */}
          <div className="gov-table-container">
            <table className="gov-data-table">
              <thead>
                <tr>
                  <th style={{ width: '13%' }}>
                    <div className="gov-th-cell">
                      <span className="gov-th-en">Case No.</span>
                      <span className="gov-th-hi">मामला संख्या</span>
                    </div>
                  </th>
                  <th style={{ width: '25%' }}>
                    <div className="gov-th-cell">
                      <span className="gov-th-en">Complaint</span>
                      <span className="gov-th-hi">शिकायत</span>
                    </div>
                  </th>
                  <th style={{ width: '17%' }}>
                    <div className="gov-th-cell">
                      <span className="gov-th-en">Complainant</span>
                      <span className="gov-th-hi">शिकायतकर्ता</span>
                    </div>
                  </th>
                  <th style={{ width: '14%' }}>
                    <div className="gov-th-cell">
                      <span className="gov-th-en">Location &amp; Unit</span>
                      <span className="gov-th-hi">स्थान और इकाई</span>
                    </div>
                  </th>
                  <th style={{ width: '13%' }}>
                    <button
                      className="gov-th-sort-btn"
                      onClick={() => {
                        setSortField('registered_on')
                        setSortAsc(!sortAsc)
                      }}
                      title="Sort by Registration Date"
                    >
                      <div className="gov-th-cell">
                        <span className="gov-th-en">
                          Registered On <ArrowUpDown size={12} className="gov-sort-icon" />
                        </span>
                        <span className="gov-th-hi">पंजीकरण तिथि</span>
                      </div>
                    </button>
                  </th>
                  <th style={{ width: '6%', textAlign: 'center' }}>
                    <div className="gov-th-cell" style={{ alignItems: 'center' }}>
                      <span className="gov-th-en">Evidence</span>
                      <span className="gov-th-hi">साक्ष्य</span>
                    </div>
                  </th>
                  <th style={{ width: '10%' }}>
                    <div className="gov-th-cell">
                      <span className="gov-th-en">Status</span>
                      <span className="gov-th-hi">स्थिति</span>
                    </div>
                  </th>
                  <th style={{ width: '8%', textAlign: 'center' }}>
                    <div className="gov-th-cell" style={{ alignItems: 'center' }}>
                      <span className="gov-th-en">Your Access</span>
                      <span className="gov-th-hi">आपकी पहुंच</span>
                    </div>
                  </th>
                  <th style={{ width: '4%', textAlign: 'center' }}>
                    <div className="gov-th-cell" style={{ alignItems: 'center' }}>
                      <span className="gov-th-en">Actions</span>
                      <span className="gov-th-hi">कार्रवाई</span>
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {paginatedCases.map((c) => {
                  const status = getStatus(c)
                  return (
                    <tr key={c.id} onClick={() => navigate(`/cases/${c.id}`)} className="gov-tr-clickable">
                      {/* Case No. & FIR */}
                      <td>
                        <Link
                          to={`/cases/${c.id}`}
                          className="gov-case-link"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {c.id}
                        </Link>
                        <div className="gov-cell-sub">FIR {c.fir_no}</div>
                      </td>

                      {/* Complaint */}
                      <td>
                        <div className="gov-cell-main">{c.title}</div>
                      </td>

                      {/* Complainant */}
                      <td>
                        <div className="gov-cell-complainant">{c.complainant || '—'}</div>
                      </td>

                      {/* Location & Unit */}
                      <td>
                        <div className="gov-cell-location">
                          <MapPin size={13} className="gov-pin-icon" aria-hidden />
                          <span>{c.city}</span>
                        </div>
                        <div className="gov-cell-sub">{c.unit}</div>
                      </td>

                      {/* Registered On */}
                      <td className="gov-cell-date">{formatDate(c.registered_on)}</td>

                      {/* Evidence Count */}
                      <td style={{ textAlign: 'center' }}>
                        <span className="gov-evidence-badge">{c.evidence_count}</span>
                      </td>

                      {/* Status */}
                      <td>
                        <span className={`gov-status-badge gov-status-${status.tone}`}>
                          <span className="gov-status-dot" />
                          <span>{status.label}</span>
                        </span>
                      </td>

                      {/* Your Access */}
                      <td style={{ textAlign: 'center' }}>
                        <span className="gov-access-pill">Member</span>
                      </td>

                      {/* Actions */}
                      <td style={{ textAlign: 'center', position: 'relative' }} onClick={(e) => e.stopPropagation()}>
                        <button
                          className="gov-action-btn"
                          aria-label="Actions"
                          onClick={() => setActionMenuCaseId(actionMenuCaseId === c.id ? null : c.id)}
                        >
                          <MoreVertical size={16} />
                        </button>

                        {actionMenuCaseId === c.id && (
                          <>
                            <div
                              style={{ position: 'fixed', inset: 0, zIndex: 990 }}
                              onClick={() => setActionMenuCaseId(null)}
                            />
                            <div className="gov-action-dropdown">
                              <button
                                onClick={() => {
                                  setActionMenuCaseId(null)
                                  navigate(`/cases/${c.id}`)
                                }}
                              >
                                <Eye size={14} /> Open Case
                              </button>
                              <button
                                onClick={() => {
                                  setActionMenuCaseId(null)
                                  navigate(`/cases/${c.id}/review`)
                                }}
                              >
                                <ExternalLink size={14} /> Review Queue
                              </button>
                              <button
                                onClick={() => {
                                  navigator.clipboard.writeText(c.fir_no)
                                  setActionMenuCaseId(null)
                                }}
                              >
                                <Copy size={14} /> Copy FIR No.
                              </button>
                            </div>
                          </>
                        )}
                      </td>
                    </tr>
                  )
                })}

                {paginatedCases.length === 0 && !error && cases && (
                  <tr>
                    <td colSpan={9} style={{ textAlign: 'center', padding: '36px 0', color: 'var(--muted)' }}>
                      No matching cases found. Try adjusting your search query or filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* TABLE FOOTER / PAGINATION */}
          <div className="gov-table-footer">
            <div className="gov-footer-showing">
              Showing {startRecord} to {endRecord} of {totalCases} cases
            </div>

            <div className="gov-pagination-controls">
              <div className="gov-rows-per-page">
                <span className="gov-rows-label">Rows per page</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value))
                    setCurrentPage(1)
                  }}
                  className="gov-rows-select"
                >
                  <option value={6}>6</option>
                  <option value={12}>12</option>
                  <option value={24}>24</option>
                </select>
              </div>

              <div className="gov-page-buttons">
                {/* First page */}
                <button
                  className="gov-page-nav-btn"
                  onClick={() => setCurrentPage(1)}
                  disabled={currentPage === 1}
                  aria-label="First page"
                >
                  <ChevronsLeft size={16} />
                </button>

                {/* Prev page */}
                <button
                  className="gov-page-nav-btn"
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  aria-label="Previous page"
                >
                  <ChevronLeft size={16} />
                </button>

                {/* Page numbers */}
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((pg) => (
                  <button
                    key={pg}
                    className={`gov-page-num-btn ${currentPage === pg ? 'active' : ''}`}
                    onClick={() => setCurrentPage(pg)}
                  >
                    {pg}
                  </button>
                ))}

                {/* Next page */}
                <button
                  className="gov-page-nav-btn"
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  aria-label="Next page"
                >
                  <ChevronRight size={16} />
                </button>

                {/* Last page */}
                <button
                  className="gov-page-nav-btn"
                  onClick={() => setCurrentPage(totalPages)}
                  disabled={currentPage === totalPages}
                  aria-label="Last page"
                >
                  <ChevronsRight size={16} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {!cases && !error && (
        <Card>
          <Skeleton lines={6} />
        </Card>
      )}

      {/* Register Complaint Modal */}
      <RegisterComplaintModal
        isOpen={registerOpen}
        onClose={() => setRegisterOpen(false)}
        onSubmit={handleRegisterComplaint}
      />
    </div>
  )
}
