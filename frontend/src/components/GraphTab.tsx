import cytoscape, { type Core } from 'cytoscape'
import { Crosshair, FileSearch, RotateCcw, Search } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, type CaseGraph, type EdgeSupport, type EntityDetail, type GraphEdge, type TimelineEvent } from '../api'
import { EDGE_LABELS, formatDateTime, formatINR, TYPE_LABELS } from '../format'
import { ErrorNote } from './bits'
import { SnippetView } from './ReviewTab'
import SourceDrawer, { type SourceRef } from './SourceDrawer'

// Colour and shape together, so node types stay distinguishable without colour.
const TYPE_STYLE: Record<string, { color: string; shape: cytoscape.Css.NodeShape }> = {
  person: { color: '#3b82f6', shape: 'ellipse' },
  organisation: { color: '#8b5cf6', shape: 'round-hexagon' },
  phone: { color: '#0d9488', shape: 'round-rectangle' },
  bank_account: { color: '#d97706', shape: 'rectangle' },
  upi: { color: '#db2777', shape: 'round-diamond' },
  imei: { color: '#64748b', shape: 'round-triangle' },
  crypto_wallet: { color: '#dc2626', shape: 'star' },
  bank_branch: { color: '#16a34a', shape: 'round-pentagon' },
  bank_official: { color: '#15803d', shape: 'round-tag' },
  location: { color: '#94a3b8', shape: 'ellipse' },
  document: { color: '#475569', shape: 'round-rectangle' },
}

function shortLabel(type: string, label: string): string {
  if (['bank_account', 'phone', 'imei'].includes(type) && label.length > 10) return `…${label.slice(-6)}`
  if (type === 'crypto_wallet') return `${label.slice(0, 5)}…${label.slice(-4)}`
  if (type === 'document') return label.length > 22 ? `${label.slice(0, 20)}…` : label
  return label
}

type Selected = { kind: 'node'; id: string } | { kind: 'edge'; edge: GraphEdge } | null

export default function GraphTab({ caseId }: { caseId: string }) {
  const [graph, setGraph] = useState<CaseGraph | null>(null)
  const [focus, setFocus] = useState<string | null>(null)
  const [hops, setHops] = useState(1)
  const [documents, setDocuments] = useState(true)
  const [selected, setSelected] = useState<Selected>(null)
  const [detail, setDetail] = useState<{ key: string; entity?: EntityDetail; support?: EdgeSupport } | null>(null)
  const [events, setEvents] = useState<TimelineEvent[] | null>(null)
  const [source, setSource] = useState<SourceRef | null>(null)
  const [query, setQuery] = useState('')
  const [error, setError] = useState<string | null>(null)
  const box = useRef<HTMLDivElement>(null)
  const cy = useRef<Core | null>(null)

  useEffect(() => {
    api.graph(caseId, focus, hops, documents).then(setGraph, (e) => setError(e.message))
  }, [caseId, focus, hops, documents])

  useEffect(() => {
    api.timeline(caseId, focus).then(setEvents, (e) => setError(e.message))
  }, [caseId, focus])

  const labelOf = useMemo(() => {
    const m = new Map<string, string>()
    graph?.nodes.forEach((n) => m.set(n.id, n.label))
    return m
  }, [graph])
  const byValue = useMemo(() => {
    const m = new Map<string, string>()
    graph?.nodes.forEach((n) => m.set(n.label, n.id))
    return m
  }, [graph])

  useEffect(() => {
    if (!box.current || !graph) return
    const css = getComputedStyle(document.documentElement)
    const text = css.getPropertyValue('--text').trim() || '#222'
    const muted = css.getPropertyValue('--muted').trim() || '#888'
    const focusColor = css.getPropertyValue('--focus').trim() || '#3b82f6'
    const inst = cytoscape({
      container: box.current,
      elements: [
        ...graph.nodes.map((n) => ({
          data: { id: n.id, label: shortLabel(n.type, n.label), type: n.type, shared: n.other_cases.length > 0 ? 1 : 0 },
        })),
        ...graph.edges.map((e) => ({ data: { id: e.id, source: e.source, target: e.target, type: e.type, n: e.independent_sources } })),
      ],
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'font-size': 9,
            color: text,
            'text-valign': 'bottom',
            'text-margin-y': 3,
            width: 20,
            height: 20,
            'border-width': 0,
            'text-wrap': 'ellipsis',
            'text-max-width': '110px',
          },
        },
        ...Object.entries(TYPE_STYLE).map(([t, s]) => ({
          selector: `node[type = "${t}"]`,
          style: { 'background-color': s.color, shape: s.shape },
        })),
        { selector: 'node[type = "document"]', style: { width: 16, height: 16, 'background-opacity': 0.55 } },
        { selector: 'node[shared = 1]', style: { 'border-width': 3, 'border-color': '#f1c453' } },
        {
          selector: 'edge',
          style: {
            width: 'mapData(n, 1, 4, 1.2, 3.5)',
            'line-color': muted,
            'target-arrow-color': muted,
            'target-arrow-shape': 'triangle',
            'arrow-scale': 0.7,
            'curve-style': 'bezier',
            opacity: 0.75,
          },
        },
        { selector: 'edge[type = "transferred"]', style: { 'line-color': '#d97706', 'target-arrow-color': '#d97706', opacity: 0.95 } },
        { selector: 'edge[type = "called"]', style: { 'line-color': '#0d9488', 'target-arrow-color': '#0d9488', 'line-style': 'dashed' } },
        { selector: 'edge[type = "appears_in"]', style: { opacity: 0.3, 'target-arrow-shape': 'none', 'line-style': 'dotted' } },
        { selector: ':selected', style: { 'border-width': 3, 'border-color': focusColor, 'line-color': focusColor, 'target-arrow-color': focusColor, opacity: 1 } },
      ],
      layout: { name: 'cose', animate: false, nodeRepulsion: () => 9000, idealEdgeLength: () => 70, padding: 20 } as cytoscape.LayoutOptions,
      wheelSensitivity: 0.25,
    })
    if (graph.focus) inst.getElementById(graph.focus).select()
    inst.on('tap', 'node', (e) => setSelected({ kind: 'node', id: e.target.id() }))
    inst.on('tap', 'edge', (e) => {
      const edge = graph.edges.find((x) => x.id === e.target.id())
      if (edge) setSelected({ kind: 'edge', edge })
    })
    inst.on('tap', (e) => {
      if (e.target === inst) setSelected(null)
    })
    cy.current = inst
    return () => inst.destroy()
  }, [graph])

  const selKey = selected ? (selected.kind === 'node' ? `n:${selected.id}` : `e:${selected.edge.id}`) : null
  useEffect(() => {
    if (!selected || !selKey) return
    if (selected.kind === 'node')
      api.entity(selected.id, caseId).then((entity) => setDetail({ key: selKey, entity }), (e) => setError(e.message))
    else
      api.edgeSupport(selected.edge.edge_ids, caseId).then((support) => setDetail({ key: selKey, support }), (e) => setError(e.message))
  }, [selected, selKey, caseId])
  // Details belong to the selection they were fetched for; never show stale ones.
  const entity = detail && detail.key === selKey ? detail.entity ?? null : null
  const support = detail && detail.key === selKey ? detail.support ?? null : null

  const closeSource = useCallback(() => setSource(null), [])
  const types = useMemo(() => [...new Set(graph?.nodes.map((n) => n.type) ?? [])].sort(), [graph])
  const label = (v: string) => {
    const id = byValue.get(v)
    return id ? labelOf.get(id) ?? v : v
  }

  return (
    <div className="graph-tab">
      <ErrorNote error={error} />
      <div className="graph-toolbar">
        {graph?.focus ? (
          <>
            <span className="small">
              Focused on <strong>{labelOf.get(graph.focus) ?? '…'}</strong>
            </span>
            <label className="small">
              Hops{' '}
              <select value={hops} onChange={(e) => setHops(Number(e.target.value))}>
                {[1, 2, 3].map((h) => (
                  <option key={h} value={h}>
                    {h}
                  </option>
                ))}
              </select>
            </label>
            <button className="btn btn-small btn-ghost" onClick={() => setFocus(null)}>
              <RotateCcw size={14} aria-hidden /> Whole case
            </button>
          </>
        ) : (
          <span className="small muted">Whole case · select a node and focus on it for a 1–3 hop view</span>
        )}
        <form
          className="search search-small"
          onSubmit={(e) => {
            e.preventDefault()
            const needle = query.trim().toLowerCase()
            const hit = graph?.nodes.find((n) => n.label.toLowerCase() === needle) ??
              graph?.nodes.find((n) => n.label.toLowerCase().includes(needle))
            if (!needle || !hit) return
            cy.current?.elements().unselect()
            const el = cy.current?.getElementById(hit.id)
            el?.select()
            if (el) cy.current?.animate({ center: { eles: el }, zoom: 1.4 }, { duration: 250 })
            setSelected({ kind: 'node', id: hit.id })
          }}
        >
          <Search size={14} aria-hidden />
          <input list="graph-labels" placeholder="Find a person, number, account…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Find entity in graph" />
          <datalist id="graph-labels">
            {graph?.nodes.slice(0, 400).map((n) => <option key={n.id} value={n.label} />)}
          </datalist>
        </form>
        <label className="small toggle">
          <input type="checkbox" checked={documents} onChange={(e) => setDocuments(e.target.checked)} /> Show documents
        </label>
        {graph && (
          <span className="small muted">
            {graph.nodes.length} nodes · {graph.edges.length} relationships{graph.truncated ? ' · truncated' : ''}
          </span>
        )}
      </div>
      <div className="graph-layout">
        <div className="graph-canvas-wrap">
          <div ref={box} className="graph-canvas" role="img" aria-label="Investigation graph" />
          {graph && graph.nodes.length === 0 && (
            <div className="graph-empty">
              <p>No confirmed entities yet.</p>
              <p className="muted small">Confirm mentions in the review queue and they appear here.</p>
            </div>
          )}
          <div className="legend">
            {types.map((t) => (
              <span key={t} className="legend-item">
                <span className="legend-dot" style={{ background: TYPE_STYLE[t]?.color ?? '#999' }} />
                {TYPE_LABELS[t] ?? t}
              </span>
            ))}
            <span className="legend-item">
              <span className="legend-dot legend-shared" /> Also in another case you can see
            </span>
          </div>
        </div>
        <aside className="graph-side">
          {!selected && <p className="muted small pad">Select a node or relationship to see where it comes from.</p>}
          {selected?.kind === 'node' && entity && (
            <div className="side-body">
              <span className="chip">{TYPE_LABELS[entity.type] ?? entity.type}</span>
              <h3 className="side-title">{entity.label}</h3>
              {entity.records.length > 1 && (
                <p className="small">Merged from {entity.records.length} records by an identity decision.</p>
              )}
              {entity.cases.length > 1 && <p className="small">Appears in cases: {entity.cases.join(', ')}</p>}
              <Attrs attrs={entity.records.reduce((a, r) => ({ ...a, ...r.attrs }), {} as Record<string, unknown>)} />
              <div className="row-actions">
                <button className="btn btn-small" onClick={() => setFocus(entity.id)}>
                  <Crosshair size={14} aria-hidden /> Focus here
                </button>
                {entity.document_file && (
                  <button
                    className="btn btn-small btn-ghost"
                    onClick={() => setSource({ evidenceId: entity.document_file!.evidence_id, filename: entity.document_file!.filename, spans: [] })}
                  >
                    <FileSearch size={14} aria-hidden /> Open document
                  </button>
                )}
              </div>
              {entity.mentions.length > 0 && (
                <>
                  <h4>
                    Where it appears ({entity.mention_total})
                  </h4>
                  <ul className="source-list">
                    {entity.mentions.slice(0, 25).map((m) => (
                      <li key={m.extraction_id}>
                        <button className="source-link" onClick={() => setSource({ evidenceId: m.evidence_id, filename: m.filename, spans: [m.span], title: entity.label })}>
                          <span className="small">
                            {m.case_id} · {m.filename}
                          </span>
                          <SnippetView s={m.snippet} />
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
          {selected?.kind === 'edge' && support && (
            <div className="side-body">
              <span className="chip">Relationship</span>
              <h3 className="side-title">
                {labelOf.get(selected.edge.source)} <span className="muted">{EDGE_LABELS[selected.edge.type] ?? selected.edge.type}</span>{' '}
                {labelOf.get(selected.edge.target)}
              </h3>
              <p className="small">
                {support.independent_sources} independent source{support.independent_sources === 1 ? '' : 's'} · {support.supports.length} supporting record
                {support.supports.length === 1 ? '' : 's'}
              </p>
              <p className="muted small">Copies of one record (a byte-identical file, or two statements showing one bank reference) count once.</p>
              <ul className="source-list">
                {support.supports.map((s, i) => (
                  <li key={i}>
                    <button className="source-link" onClick={() => setSource({ evidenceId: s.evidence_id, filename: s.filename, spans: [s.span] })}>
                      <span className="small">
                        {s.case_id} · {s.filename}
                        {s.source_group.startsWith('bankref:') && <span className="muted"> · bank ref {s.source_group.slice(8)}</span>}
                      </span>
                      <SnippetView s={s.snippet} />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>

      <section className="panel">
        <div className="panel-head">
          <h2>Timeline {graph?.focus ? `· ${labelOf.get(graph.focus) ?? ''}` : '· whole case'}</h2>
          <span className="muted small">Transfers from confirmed statement rows and calls from confirmed CDR rows</span>
        </div>
        {events && events.length === 0 && <p className="muted pad">No confirmed transactions or calls yet.</p>}
        {events && events.length > 0 && (
          <div className="table-wrap timeline">
            <table className="table table-dense">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Event</th>
                  <th>From</th>
                  <th>To</th>
                  <th className="num">Amount</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.id}>
                    <td className="nowrap">
                      {formatDateTime(ev.ts)}
                      {ev.ts_ambiguous && <span className="chip chip-warn" title="Day and month could be swapped">date ambiguous</span>}
                    </td>
                    <td>
                      <span className={`chip chip-ev-${ev.kind}`}>{ev.kind}</span> <span className="muted">{ev.channel}</span>
                    </td>
                    <td className="mono small">{label(ev.from)}</td>
                    <td className="mono small">
                      {label(ev.to)}
                      {ev.names.length > 0 && <div className="muted">{ev.names.join(', ')}</div>}
                    </td>
                    <td className="num">{ev.amount != null ? formatINR(ev.amount) : ''}</td>
                    <td className="nowrap">
                      {ev.sources.map((s, i) => (
                        <button key={i} className="btn btn-small btn-ghost" title={s.filename} onClick={() => setSource({ evidenceId: s.evidence_id, filename: s.filename, spans: [s.span] })}>
                          <FileSearch size={13} aria-hidden /> {i + 1}
                        </button>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {source && <SourceDrawer source={source} onClose={closeSource} />}
    </div>
  )
}

function Attrs({ attrs }: { attrs: Record<string, unknown> }) {
  const entries = Object.entries(attrs).filter(([k]) => k !== 'evidence_file_id')
  if (!entries.length) return null
  const flat: [string, string][] = []
  for (const [k, v] of entries) {
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      for (const [k2, v2] of Object.entries(v as Record<string, unknown>)) flat.push([k2, String(v2)])
    } else flat.push([k, Array.isArray(v) ? v.join(', ') : String(v)])
  }
  return (
    <dl className="attrs">
      {flat.map(([k, v]) => (
        <div key={k}>
          <dt>{k.replace(/_/g, ' ')}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  )
}
