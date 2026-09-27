import { useMemo } from 'react'
import type { TrailMethod } from '../api3'
import { formatINR } from '../format'

export const CASE_COLORS = ['#2350b8', '#0d9488', '#c2410c', '#7c3aed', '#be185d', '#4d7c0f']

type Node = { id: string; col: number; inflow: number; outflow: number; held: number; exit: boolean; victim: boolean; y: number; h: number; inOff: number; outOff: number }
type Link = { from: string; to: string; caseId: string; amount: number; exit: string | null }

const W = 1120
const NODE_W = 12
const LABEL_W = 210
const MAX_H = 250
const PER_NODE_H = 46
const MIN_SLOT = 34
const GAP = 12
const TOP = 34

/** Layered flow of victim money: victims on the left, hops to the right, exits in the last column.
 *  Ribbon width is proportional to the attributed amount under the selected method. */
export default function FlowDiagram({ t, label, cases }: { t: TrailMethod; label: (p: string) => string; cases: string[] }) {
  const layout = useMemo(() => {
    const nodes = new Map<string, Node>()
    const node = (id: string, col: number) => {
      let n = nodes.get(id)
      if (!n) {
        n = { id, col, inflow: 0, outflow: 0, held: 0, exit: false, victim: false, y: 0, h: 0, inOff: 0, outOff: 0 }
        nodes.set(id, n)
      } else n.col = Math.min(n.col, col)
      return n
    }
    const agg = new Map<string, Link>()
    for (const f of t.flows) {
      const caseId = f.tag.split(':')[1] ?? ''
      const key = `${f.from}|${f.to}|${caseId}`
      const l = agg.get(key) ?? { from: f.from, to: f.to, caseId, amount: 0, exit: f.exit }
      l.amount += f.amount
      agg.set(key, l)
      node(f.from, f.layer - 1)
      const to = node(f.to, f.layer)
      if (f.exit) to.exit = true
    }
    for (const s of t.seeds) node(s.victim, 0).victim = true
    for (const h of t.holdings) if (nodes.has(h.party)) nodes.get(h.party)!.held += h.uncertain ? 0 : h.amount
    const links = [...agg.values()]
    for (const l of links) {
      nodes.get(l.from)!.outflow += l.amount
      nodes.get(l.to)!.inflow += l.amount
    }
    // Exits collect in one final column so "left the trail" reads as a single destination.
    const maxCol = Math.max(1, ...[...nodes.values()].filter((n) => !n.exit).map((n) => n.col)) + 1
    for (const n of nodes.values()) if (n.exit && n.outflow === 0) n.col = maxCol
    const cols: Node[][] = Array.from({ length: maxCol + 1 }, () => [])
    for (const n of nodes.values()) cols[n.col].push(n)
    const value = (n: Node) => Math.max(n.inflow, n.outflow)
    const maxTotal = Math.max(...cols.map((c) => c.reduce((s, n) => s + value(n), 0)), 1)
    // Scale ribbons to the busiest column, so a short chain does not become a solid block.
    const densest = Math.max(...cols.map((c) => c.length))
    const k = Math.min(MAX_H, Math.max(110, densest * PER_NODE_H)) / maxTotal
    let height = 0
    for (const col of cols) {
      col.sort((a, b) => value(b) - value(a))
      let y = TOP
      for (const n of col) {
        n.h = Math.max(value(n) * k, 3)
        n.y = y
        y += Math.max(n.h, MIN_SLOT) + GAP
      }
      height = Math.max(height, y)
    }
    const colW = (W - LABEL_W - NODE_W) / maxCol
    const x = (n: Node) => n.col * colW
    links.sort((a, b) => nodes.get(a.from)!.y - nodes.get(b.from)!.y || nodes.get(a.to)!.y - nodes.get(b.to)!.y)
    const paths = links.map((l) => {
      const s = nodes.get(l.from)!
      const d = nodes.get(l.to)!
      const w = Math.max(l.amount * k, 1.5)
      const sy = s.y + s.outOff + w / 2
      const ty = d.y + d.inOff + w / 2
      s.outOff += l.amount * k
      d.inOff += l.amount * k
      const x0 = x(s) + NODE_W
      const x1 = x(d)
      const xm = (x0 + x1) / 2
      return { l, w, d: `M${x0},${sy} C${xm},${sy} ${xm},${ty} ${x1},${ty}` }
    })
    return { nodes: [...nodes.values()], paths, height: height + 6, colW, maxCol, x }
  }, [t])

  const color = (c: string) => CASE_COLORS[Math.max(cases.indexOf(c), 0) % CASE_COLORS.length]
  const colTitle = (i: number) => (i === 0 ? 'Victims' : i === layout.maxCol ? 'Left the trail' : `Layer ${i}`)

  return (
    <div className="flow-wrap">
      <svg className="flow" viewBox={`0 0 ${W} ${layout.height}`} width="100%" role="img" aria-label="Money flow from victims through each layer to exit points">
        {Array.from({ length: layout.maxCol + 1 }, (_, i) => (
          <text key={i} className="flow-col" x={i * layout.colW} y={14}>
            {colTitle(i)}
          </text>
        ))}
        {layout.paths.map((p, i) => (
          <path key={i} className={`flow-link${p.l.exit ? ' flow-link-exit' : ''}`} d={p.d} strokeWidth={p.w} style={{ stroke: p.l.exit ? undefined : color(p.l.caseId) }}>
            <title>
              {label(p.l.from)} → {label(p.l.to)}: {formatINR(p.l.amount)} of {p.l.caseId} money{p.l.exit ? ` (${p.l.exit})` : ''}
            </title>
          </path>
        ))}
        {layout.nodes.map((n) => {
          const full = label(n.id)
          const m = full.match(/^(.*?)\s*\((.+)\)$/)
          const name = m ? m[2] : full
          const sub = m ? m[1] : ''
          const cls = n.victim ? 'flow-node flow-node-victim' : n.exit ? 'flow-node flow-node-exit' : n.held > 0 ? 'flow-node flow-node-hold' : 'flow-node'
          const tx = layout.x(n) + NODE_W + 7
          const ty = n.y + Math.min(n.h, MIN_SLOT) / 2
          return (
            <g key={n.id}>
              <rect className={cls} x={layout.x(n)} y={n.y} width={NODE_W} height={n.h} rx={3} strokeWidth={1.5}>
                <title>{full}</title>
              </rect>
              <text className="flow-label" x={tx} y={ty - 2} style={{ paintOrder: 'stroke', stroke: 'var(--surface)', strokeWidth: 4 }}>
                {name.length > 26 ? name.slice(0, 25) + '…' : name}
              </text>
              <text className="flow-amt" x={tx} y={ty + 12} style={{ paintOrder: 'stroke', stroke: 'var(--surface)', strokeWidth: 4 }}>
                {sub && sub !== name ? `${sub.length > 16 ? sub.slice(0, 15) + '…' : sub} · ` : ''}
                {formatINR(Math.max(n.inflow, n.outflow))}
                {n.held > 0 ? ` · holds ${formatINR(n.held)}` : ''}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
