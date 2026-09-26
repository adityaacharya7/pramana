const IST = 'Asia/Kolkata'

const dateTime = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST,
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

const dateOnly = new Intl.DateTimeFormat('en-IN', { timeZone: IST, day: '2-digit', month: 'short', year: 'numeric' })

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : `${dateTime.format(d)} IST`
}

export function formatDate(isoDate: string | null | undefined): string {
  if (!isoDate) return '—'
  const d = new Date(`${isoDate}T00:00:00+05:30`)
  return Number.isNaN(d.getTime()) ? isoDate : dateOnly.format(d)
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export function shortHash(h: string, head = 10, tail = 6): string {
  return h.length > head + tail + 1 ? `${h.slice(0, head)}…${h.slice(-tail)}` : h
}

export const KIND_LABELS: Record<string, string> = {
  complaint: 'Complaint',
  witness_statement: 'Witness statement',
  supplementary_statement: 'Supplementary statement',
  bank_statement: 'Bank statement',
  kyc_response: 'KYC response',
  cdr: 'Call detail record',
  chat_log: 'Chat log',
  other: 'Other',
  unclassified: 'Unclassified',
}

export const TYPE_LABELS: Record<string, string> = {
  person: 'Person',
  organisation: 'Organisation',
  phone: 'Phone',
  bank_account: 'Bank account',
  upi: 'UPI ID',
  imei: 'IMEI',
  crypto_wallet: 'Crypto wallet',
  bank_branch: 'Bank branch',
  bank_official: 'Bank official',
  location: 'Place',
  document: 'Document',
  id_document: 'ID document',
}

export const EDGE_LABELS: Record<string, string> = {
  transferred: 'transferred to',
  owns: 'holds',
  uses: 'uses',
  called: 'contacted',
  registered_to: 'registered to',
  opened_at: 'held at branch',
  opened_by: 'opened by',
  appears_in: 'appears in',
}

/** Who proposed a mention: deterministic rules, or the statistical model. */
export function extractorLabel(extractor: string): { label: string; model: boolean } {
  if (extractor.startsWith('spacy')) return { label: 'NER model', model: true }
  if (extractor.startsWith('csv')) return { label: 'Spreadsheet column', model: false }
  if (extractor.startsWith('pattern')) return { label: 'Role pattern', model: false }
  return { label: 'Identifier rule', model: false }
}

export const DETERMINISTIC = ['regex-v1', 'pattern-v1', 'csv-v1']

const inr = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })
export const formatINR = (n: number) => `₹ ${inr.format(n)}`

export function guessKind(filename: string): string {
  const f = filename.toLowerCase()
  if (f.includes('witness')) return 'witness_statement'
  if (f.includes('supplementary')) return 'supplementary_statement'
  if (f.includes('complaint') || f.includes('fir')) return 'complaint'
  if (f.includes('statement') || f.includes('passbook')) return 'bank_statement'
  if (f.includes('kyc')) return 'kyc_response'
  if (f.includes('cdr')) return 'cdr'
  if (f.includes('chat') || f.includes('whatsapp')) return 'chat_log'
  return 'unclassified'
}

/** Minimal RFC 4180 CSV parser (quoted fields, embedded commas and quotes). */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"'
        i++
      } else if (c === '"') quoted = false
      else field += c
    } else if (c === '"') quoted = true
    else if (c === ',') {
      row.push(field)
      field = ''
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++
      row.push(field)
      rows.push(row)
      row = []
      field = ''
    } else field += c
  }
  if (field || row.length) {
    row.push(field)
    rows.push(row)
  }
  return rows
}
