import React from 'react'

/**
 * High-quality, zero-dependency Markdown renderer tailored for PRAMANA Forensic Intelligence.
 * Safely parses bold, italic, inline code, headings, lists, blockquotes, and tables.
 */
export default function FormattedMarkdown({ content }: { content: string }) {
  if (!content) return null

  // Clean out any accidental simulated memo preambles if present
  let clean = content
    .replace(/^\*\*(?:PRAMANA AI|UPAKARAKA) \/\/ [^\n]+\*\*\s*/i, '')
    .replace(/^\*\*TO:\*\*[^\n]+\n/i, '')
    .replace(/^\*\*SUBJECT:\*\*[^\n]+\n/i, '')
    .replace(/^\*\*DATE:\*\*[^\n]+\n/i, '')
    .trim()

  const lines = clean.split('\n')
  const elements: React.ReactNode[] = []

  let inList: 'ul' | 'ol' | null = null
  let listItems: React.ReactNode[] = []
  let inTable = false
  let tableRows: string[][] = []

  const flushList = (key: string) => {
    if (inList === 'ul') {
      elements.push(
        <ul key={`ul-${key}`} className="pramana-md-ul">
          {listItems}
        </ul>
      )
    } else if (inList === 'ol') {
      elements.push(
        <ol key={`ol-${key}`} className="pramana-md-ol">
          {listItems}
        </ol>
      )
    }
    inList = null
    listItems = []
  }

  const flushTable = (key: string) => {
    if (tableRows.length > 0) {
      const headers = tableRows[0]
      const bodyRows = tableRows.slice(1).filter((r) => !r.every((c) => /^[-:\s]+$/.test(c)))
      elements.push(
        <div key={`table-${key}`} className="pramana-md-table-wrap">
          <table className="pramana-md-table">
            <thead>
              <tr>
                {headers.map((h, i) => (
                  <th key={i}>{parseInline(h)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bodyRows.map((row, ri) => (
                <tr key={ri}>
                  {row.map((cell, ci) => (
                    <td key={ci}>{parseInline(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
      inTable = false
      tableRows = []
    }
  }

  lines.forEach((line, index) => {
    const trimmed = line.trim()

    // Table line
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      if (inList) flushList(`line-${index}`)
      inTable = true
      const cells = trimmed
        .slice(1, -1)
        .split('|')
        .map((c) => c.trim())
      tableRows.push(cells)
      return
    } else if (inTable) {
      flushTable(`line-${index}`)
    }

    // Horizontal Rule
    if (trimmed === '---' || trimmed === '***' || trimmed === '___') {
      if (inList) flushList(`line-${index}`)
      elements.push(<hr key={index} className="pramana-md-hr" />)
      return
    }

    // Headings
    if (trimmed.startsWith('#### ')) {
      if (inList) flushList(`line-${index}`)
      elements.push(
        <h5 key={index} className="pramana-md-h5">
          {parseInline(trimmed.replace('#### ', ''))}
        </h5>
      )
      return
    }
    if (trimmed.startsWith('### ')) {
      if (inList) flushList(`line-${index}`)
      elements.push(
        <h4 key={index} className="pramana-md-h4">
          {parseInline(trimmed.replace('### ', ''))}
        </h4>
      )
      return
    }
    if (trimmed.startsWith('## ')) {
      if (inList) flushList(`line-${index}`)
      elements.push(
        <h3 key={index} className="pramana-md-h3">
          {parseInline(trimmed.replace('## ', ''))}
        </h3>
      )
      return
    }
    if (trimmed.startsWith('# ')) {
      if (inList) flushList(`line-${index}`)
      elements.push(
        <h2 key={index} className="pramana-md-h2">
          {parseInline(trimmed.replace('# ', ''))}
        </h2>
      )
      return
    }

    // Unordered List item (* or -)
    if (/^[*\-]\s+/.test(trimmed)) {
      if (inList !== 'ul') {
        flushList(`line-${index}`)
        inList = 'ul'
      }
      const itemText = trimmed.replace(/^[*\-]\s+/, '')
      listItems.push(
        <li key={`li-${index}`} className="pramana-md-li">
          {parseInline(itemText)}
        </li>
      )
      return
    }

    // Ordered List item (1. 2. etc.)
    if (/^\d+\.\s+/.test(trimmed)) {
      if (inList !== 'ol') {
        flushList(`line-${index}`)
        inList = 'ol'
      }
      const itemText = trimmed.replace(/^\d+\.\s+/, '')
      listItems.push(
        <li key={`li-${index}`} className="pramana-md-li">
          {parseInline(itemText)}
        </li>
      )
      return
    }

    // Empty line
    if (!trimmed) {
      if (inList) flushList(`line-${index}`)
      elements.push(<div key={index} className="pramana-md-spacer" />)
      return
    }

    // Regular Paragraph
    if (inList) flushList(`line-${index}`)
    elements.push(
      <p key={index} className="pramana-md-p">
        {parseInline(trimmed)}
      </p>
    )
  })

  if (inList) flushList('end')
  if (inTable) flushTable('end')

  return <div className="pramana-formatted-markdown">{elements}</div>
}

/**
 * Parses inline formatting: **bold**, *italic*, `code`, [link](url).
 */
function parseInline(text: string): React.ReactNode[] {
  // Regex tokenizing **bold**, *italic*, `code`, and [label](url)
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g
  const parts = text.split(regex)

  return parts.map((part, i) => {
    if (!part) return null

    if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
      const inner = part.slice(2, -2)
      // Check if it's a key-value header like **KEY:**
      if (inner.endsWith(':')) {
        return (
          <strong key={i} className="pramana-md-key">
            {inner}{' '}
          </strong>
        )
      }
      return (
        <strong key={i} className="pramana-md-bold">
          {inner}
        </strong>
      )
    }

    if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
      return (
        <em key={i} className="pramana-md-italic">
          {part.slice(1, -1)}
        </em>
      )
    }

    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      return (
        <code key={i} className="pramana-md-code">
          {part.slice(1, -1)}
        </code>
      )
    }

    if (part.startsWith('[') && part.includes('](') && part.endsWith(')')) {
      const match = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
      if (match) {
        return (
          <a
            key={i}
            href={match[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="pramana-md-link"
          >
            {match[1]}
          </a>
        )
      }
    }

    return part
  })
}
