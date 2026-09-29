import type { SVGProps } from 'react'

/**
 * PRAMANA Official System Logo
 * Displays the official PRAMANA brandmark with light and dark mode support.
 */
export function PramanaLogo({ size = 44, className = '', height }: { size?: number; className?: string; height?: number }) {
  const h = height || size
  return (
    <span className={`pramana-logo-wrap ${className}`} style={{ display: 'inline-flex', alignItems: 'center' }}>
      <img
        src="/pramana-logo-transparent.png"
        alt="PRAMANA"
        className="gov-emblem-light"
        style={{ height: h, width: 'auto', maxHeight: '100%', objectFit: 'contain' }}
      />
      <img
        src="/pramana-logo-dark.png"
        alt="PRAMANA"
        className="gov-emblem-dark"
        style={{ height: h, width: 'auto', maxHeight: '100%', objectFit: 'contain' }}
      />
    </span>
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
