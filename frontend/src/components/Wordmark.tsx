/** PRAMANA mark: a seal with a check - "proof" - in the brand navy and saffron. */
export function Seal({ size = 28 }: { size?: number }) {
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} aria-hidden className="seal">
      <path d="M16 2.5 27.5 7v8.4c0 7-4.9 12.1-11.5 14.1C9.4 27.5 4.5 22.4 4.5 15.4V7L16 2.5Z" fill="var(--seal-bg)" />
      <path d="M16 5.6 25 9.1v6.3c0 5.6-3.8 9.7-9 11.4-5.2-1.7-9-5.8-9-11.4V9.1l9-3.5Z" fill="none" stroke="var(--accent)" strokeWidth="1.1" opacity="0.55" />
      <path d="m10.8 16.2 3.6 3.6 7.2-8" fill="none" stroke="var(--accent)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export default function Wordmark({ large = false, sub = false }: { large?: boolean; sub?: boolean }) {
  return (
    <span className={large ? 'wordmark wordmark-lg' : 'wordmark'}>
      <Seal size={large ? 44 : 28} />
      <span className="wordmark-text">
        <span className="wordmark-name">PRAMANA</span>
        {sub && <span className="wordmark-sub">प्रमाण · Investigation review</span>}
      </span>
    </span>
  )
}
