export default function Wordmark({ large = false }: { large?: boolean }) {
  return (
    <span className={large ? 'wordmark wordmark-lg' : 'wordmark'}>
      <svg viewBox="0 0 32 32" aria-hidden className="wordmark-icon">
        <rect width="32" height="32" rx="7" fill="var(--brand)" />
        <path d="M8 21l8-9 8 9" fill="none" stroke="var(--brand-accent)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="16" cy="12" r="2.2" fill="#fff" />
      </svg>
      PRAMANA
    </span>
  )
}
