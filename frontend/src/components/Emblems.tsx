import type { SVGProps } from 'react'

/**
 * PRAMANA Official Project Crest
 * Government-grade institutional insignia featuring the scales of evidence and justice,
 * analytical verification pillar, and security shield.
 * Designed for SIH 2026 Prototype in compliance with
 * The State Emblem of India (Prohibition of Improper Use) Act, 2005.
 */
export function PramanaLogo({ size = 44, className = '' }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="PRAMANA System Emblem"
    >
      <defs>
        <linearGradient id="pramana-shield-grad" x1="12" y1="6" x2="52" y2="58" gradientUnits="userSpaceOnUse">
          <stop stopColor="#0B2545" />
          <stop offset="1" stopColor="#07192F" />
        </linearGradient>
        <linearGradient id="pramana-gold-grad" x1="16" y1="16" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop stopColor="#F59E0B" />
          <stop offset="0.5" stopColor="#D97706" />
          <stop offset="1" stopColor="#B45309" />
        </linearGradient>
      </defs>

      {/* Outer shield structure */}
      <path
        d="M32 4L54 12V27C54 43.5 44 54.5 32 60C20 54.5 10 43.5 10 27V12L32 4Z"
        fill="url(#pramana-shield-grad)"
        stroke="url(#pramana-gold-grad)"
        strokeWidth="2.5"
        strokeLinejoin="round"
      />

      {/* Inner subtle institutional border line */}
      <path
        d="M32 8.5L49.5 15V26.5C49.5 40.5 41 50.5 32 55.5C23 50.5 14.5 40.5 14.5 26.5V15L32 8.5Z"
        stroke="#1E3A8A"
        strokeWidth="1.2"
        fill="none"
        opacity="0.8"
      />

      {/* Central Axis / Column of Truth */}
      <line x1="32" y1="16" x2="32" y2="46" stroke="#FBBF24" strokeWidth="2.5" strokeLinecap="round" />

      {/* Balance beam / Scales of Evidence */}
      <path d="M20 23.5C24.5 22 39.5 22 44 23.5" stroke="#FBBF24" strokeWidth="2.2" strokeLinecap="round" />

      {/* Central Fulcrum Diamond */}
      <polygon points="32,20 35,23.5 32,27 29,23.5" fill="#FBBF24" />

      {/* Left scale cords & pan (Evidence Weight) */}
      <line x1="20" y1="23.5" x2="16" y2="33" stroke="#93C5FD" strokeWidth="1.2" />
      <line x1="20" y1="23.5" x2="24" y2="33" stroke="#93C5FD" strokeWidth="1.2" />
      <path d="M14 33C14 37.5 26 37.5 26 33Z" fill="url(#pramana-gold-grad)" />

      {/* Right scale cords & pan (Verification Weight) */}
      <line x1="44" y1="23.5" x2="40" y2="33" stroke="#93C5FD" strokeWidth="1.2" />
      <line x1="44" y1="23.5" x2="48" y2="33" stroke="#93C5FD" strokeWidth="1.2" />
      <path d="M38 33C38 37.5 50 37.5 50 33Z" fill="url(#pramana-gold-grad)" />

      {/* Base Pedestal */}
      <path d="M24 46H40L37 49.5H27L24 46Z" fill="#FBBF24" />
      <line x1="21" y1="52" x2="43" y2="52" stroke="#FBBF24" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  )
}

/**
 * State Emblem of India (Lion Capital of Ashoka) with "सत्यमेव जयते"
 * NOTE: Restricted under The State Emblem of India (Prohibition of Improper Use) Act, 2005.
 * Not for use in unauthorized student prototypes. Retained only for authorized government deployments.
 */
export function AshokaEmblem({ size = 52, className = '' }: { size?: number; className?: string }) {
  const width = Math.round(size * 0.63)
  return (
    <div
      className={`gov-emblem-img-wrap ${className}`}
      style={{
        width,
        height: size,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
      aria-label="State Emblem of India"
    >
      <img
        src="/emblem.png"
        alt="State Emblem of India"
        className="gov-emblem-light"
        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
      />
      <img
        src="/emblem-dark.png"
        alt="State Emblem of India"
        className="gov-emblem-dark"
        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
      />
    </div>
  )
}

/**
 * Official Digital India Logo with tricolor swoosh and typography
 */
export function DigitalIndiaLogo({ height = 38, className = '' }: { height?: number; className?: string }) {
  return (
    <div
      className={`digital-india-logo ${className}`}
      style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', height }}
    >
      <svg
        width={Math.round(height * 1.2)}
        height={height}
        viewBox="0 0 60 50"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden
      >
        {/* Tricolor dynamic wave ribbon */}
        <path
          d="M6 35 C18 35, 26 12, 54 8 C44 14, 30 38, 12 40 Z"
          fill="#FF671F"
        />
        <path
          d="M10 39 C24 39, 32 18, 56 14 C48 20, 34 42, 16 44 Z"
          fill="#FFFFFF"
          stroke="#E2E8F0"
          strokeWidth="0.5"
        />
        <path
          d="M14 43 C28 43, 36 24, 58 20 C50 26, 38 46, 20 48 Z"
          fill="#046A38"
        />
        {/* Ashoka blue dot / spark */}
        <circle cx="48" cy="18" r="2.5" fill="#0B2545" />
      </svg>
      <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.05 }}>
        <span
          style={{
            fontFamily: "'Segoe UI', Roboto, system-ui, sans-serif",
            fontWeight: 800,
            fontSize: `${Math.round(height * 0.38)}px`,
            color: '#0B2545',
            letterSpacing: '-0.02em',
          }}
        >
          Digital India
        </span>
        <span
          style={{
            fontFamily: "'Segoe UI', Roboto, system-ui, sans-serif",
            fontWeight: 500,
            fontSize: `${Math.round(height * 0.22)}px`,
            color: '#1E293B',
            letterSpacing: '0.02em',
          }}
        >
          Power To Empower
        </span>
      </div>
    </div>
  )
}

/**
 * Parliament House / Rashtrapati Bhavan delicate architectural watermark
 */
export function ParliamentWatermark({ className = '', style }: { className?: string; style?: SVGProps<SVGSVGElement>['style'] }) {
  return (
    <svg
      viewBox="0 0 400 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={style}
      aria-hidden
    >
      <g stroke="#B45309" strokeWidth="0.9" opacity="0.35" fill="none">
        {/* Central Dome */}
        <path d="M185 45 C185 22, 215 22, 215 45 Z" fill="#FDE68A" fillOpacity="0.2" />
        <path d="M190 22 L200 6 L210 22" />
        <line x1="200" y1="6" x2="200" y2="2" />
        <circle cx="200" cy="2" r="1.5" fill="#B45309" />
        <rect x="180" y="45" width="40" height="12" rx="1" />
        <line x1="184" y1="45" x2="184" y2="57" />
        <line x1="192" y1="45" x2="192" y2="57" />
        <line x1="200" y1="45" x2="200" y2="57" />
        <line x1="208" y1="45" x2="208" y2="57" />
        <line x1="216" y1="45" x2="216" y2="57" />

        {/* Central Portico / Pediment */}
        <polygon points="170,57 230,57 200,48" fill="#FDE68A" fillOpacity="0.3" />
        <rect x="172" y="57" width="56" height="48" />
        {/* Pillars */}
        {Array.from({ length: 8 }, (_, i) => (
          <line key={i} x1={176 + i * 7} y1="57" x2={176 + i * 7} y2="105" strokeWidth="1.2" />
        ))}

        {/* Left Wing Colonnade */}
        <rect x="60" y="62" width="112" height="43" />
        <rect x="56" y="58" width="120" height="4" />
        {Array.from({ length: 15 }, (_, i) => (
          <line key={`lw-${i}`} x1={64 + i * 7.4} y1="62" x2={64 + i * 7.4} y2="105" strokeWidth="0.8" />
        ))}
        {/* Left Pavilion Dome */}
        <path d="M50 58 C50 42, 70 42, 70 58 Z" />
        <line x1="60" y1="42" x2="60" y2="38" />

        {/* Right Wing Colonnade */}
        <rect x="228" y="62" width="112" height="43" />
        <rect x="224" y="58" width="120" height="4" />
        {Array.from({ length: 15 }, (_, i) => (
          <line key={`rw-${i}`} x1={232 + i * 7.4} y1="62" x2={232 + i * 7.4} y2="105" strokeWidth="0.8" />
        ))}
        {/* Right Pavilion Dome */}
        <path d="M330 58 C330 42, 350 42, 350 58 Z" />
        <line x1="340" y1="42" x2="340" y2="38" />

        {/* Plinth Base Steps */}
        <rect x="20" y="105" width="360" height="4" fill="#FDE68A" fillOpacity="0.2" />
        <rect x="10" y="109" width="380" height="4" />
        <rect x="0" y="113" width="400" height="5" />
      </g>
    </svg>
  )
}
