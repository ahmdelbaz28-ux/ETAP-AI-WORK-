/**
 * BrandLogo — The AhmedETAP logo as an inline SVG React component.
 *
 * Design concept: "Power Convergence Monogram"
 * ----------------------------------------------
 * The logo is an "A" formed by two converging transmission lines (like the
 * legs of a transmission tower) that meet at a bright apex node — symbolizing
 * the convergence of engineering disciplines into a single intelligent platform.
 *
 * The crossbar of the "A" is a horizontal power bus (single-line-diagram
 * notation) with three junction nodes — referencing the power-systems DNA of
 * the platform (Load Flow, Short Circuit, Arc Flash).
 *
 * A subtle hexagonal frame surrounds the mark, evoking engineering precision
 * and grid topology.
 *
 * Color language:
 *   - Brand blue → electric cyan gradient: the transmission lines (energy flow)
 *   - Amber: the power bus + junction nodes (high-voltage warning color)
 *   - White apex spark: the AI intelligence convergence point
 *
 * Usage:
 *   <BrandLogo size={64} />              // icon only
 *   <BrandLogo size={64} withWordmark /> // icon + "AhmedETAP" text
 *   <BrandLogo size={64} animated />     // entrance animation
 */
import { motion } from 'framer-motion'

interface BrandLogoProps {
  size?: number
  withWordmark?: boolean
  animated?: boolean
  className?: string
}

export function BrandLogo({  // NOSONAR — typescript:S6759: props read-only; refactor deferred
  size = 64,
  withWordmark = false,
  animated = false,
  className = '',
}: BrandLogoProps) {
  const Wrapper = animated ? motion.div : 'div'
  const wrapperProps = animated
    ? {
        initial: { opacity: 0, scale: 0.8, rotate: -8 },
        animate: { opacity: 1, scale: 1, rotate: 0 },
        transition: { duration: 0.8, ease: [0.22, 1, 0.36, 1] as const },
      }
    : {}

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      <Wrapper {...(wrapperProps as any)}>
        <svg
          width={size}
          height={size}
          viewBox="0 0 512 512"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-label="AhmedETAP logo"
          role="img"
        >
          <defs>
            <linearGradient id="etap-primary" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#3b82f6" />
              <stop offset="55%" stopColor="#1d4ed8" />
              <stop offset="100%" stopColor="#0a0e1a" />
            </linearGradient>
            <linearGradient id="etap-energy" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#60a5fa" />
              <stop offset="50%" stopColor="#00d4ff" />
              <stop offset="100%" stopColor="#06b6d4" />
            </linearGradient>
            <linearGradient id="etap-amber" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#fbbf24" />
              <stop offset="100%" stopColor="#f59e0b" />
            </linearGradient>
            <filter id="etap-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="etap-soft" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Background tile */}
          <rect width="512" height="512" rx="112" fill="url(#etap-primary)" />

          {/* Grid pattern */}
          <g opacity="0.06" stroke="#ffffff" strokeWidth="1" fill="none">
            <line x1="0" y1="128" x2="512" y2="128" />
            <line x1="0" y1="256" x2="512" y2="256" />
            <line x1="0" y1="384" x2="512" y2="384" />
            <line x1="128" y1="0" x2="128" y2="512" />
            <line x1="256" y1="0" x2="256" y2="512" />
            <line x1="384" y1="0" x2="384" y2="512" />
          </g>

          {/* Hexagonal frame */}
          <g opacity="0.18" stroke="#00d4ff" strokeWidth="2" fill="none" filter="url(#etap-soft)">
            <polygon points="256,72 416,164 416,348 256,440 96,348 96,164" />
          </g>
          <g opacity="0.10" stroke="#60a5fa" strokeWidth="1" fill="none">
            <polygon points="256,96 392,176 392,336 256,416 120,336 120,176" />
          </g>

          {/* The A: two converging transmission lines */}
          <line
            x1="160" y1="380" x2="256" y2="140"
            stroke="url(#etap-energy)" strokeWidth="14" strokeLinecap="round"
            filter="url(#etap-glow)"
          />
          <line
            x1="352" y1="380" x2="256" y2="140"
            stroke="url(#etap-energy)" strokeWidth="14" strokeLinecap="round"
            filter="url(#etap-glow)"
          />

          {/* Power bus (A crossbar) */}
          <line
            x1="195" y1="290" x2="317" y2="290"
            stroke="url(#etap-amber)" strokeWidth="6" strokeLinecap="round"
            filter="url(#etap-soft)"
          />
          <circle cx="195" cy="290" r="7" fill="#fbbf24" filter="url(#etap-soft)" />
          <circle cx="256" cy="290" r="9" fill="#f59e0b" filter="url(#etap-soft)" />
          <circle cx="317" cy="290" r="7" fill="#fbbf24" filter="url(#etap-soft)" />

          {/* Apex spark */}
          <circle cx="256" cy="140" r="14" fill="#00d4ff" filter="url(#etap-glow)" />
          <circle cx="256" cy="140" r="7" fill="#ffffff" opacity="0.95" />
          <path
            d="M 256 140 L 250 110 L 256 116 L 252 90 L 262 120 L 256 116 L 264 100 Z"
            fill="#ffffff" opacity="0.85" filter="url(#etap-soft)"
          />

          {/* Base nodes (transmission tower feet) */}
          <circle cx="160" cy="380" r="10" fill="#60a5fa" filter="url(#etap-soft)" />
          <circle cx="352" cy="380" r="10" fill="#60a5fa" filter="url(#etap-soft)" />
          <circle cx="160" cy="380" r="4" fill="#ffffff" opacity="0.9" />
          <circle cx="352" cy="380" r="4" fill="#ffffff" opacity="0.9" />

          {/* Ground line */}
          <line
            x1="120" y1="410" x2="392" y2="410"
            stroke="#00d4ff" strokeWidth="1.5" opacity="0.35"
            strokeDasharray="4 6"
          />

          {/* ET indicator */}
          <g opacity="0.6">
            <rect x="380" y="380" width="44" height="18" rx="3"
                  fill="none" stroke="#00d4ff" strokeWidth="1" />
            <text
              x="402" y="393"
              fontFamily="'JetBrains Mono', monospace"
              fontSize="11" fontWeight="700"
              fill="#00d4ff" textAnchor="middle" letterSpacing="1"
            >
              ET
            </text>
          </g>
        </svg>
      </Wrapper>

      {withWordmark && (
        <div className="flex flex-col leading-none">
          <span
            className="font-bold tracking-tight"
            style={{
              fontSize: size * 0.42,
              background: 'linear-gradient(135deg, #3b82f6, #00d4ff)',
              WebkitBackgroundClip: 'text',
              backgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            AhmedETAP
          </span>
          <span
            className="text-[var(--text-muted)] mt-1"
            style={{
              fontSize: size * 0.13,
              letterSpacing: '0.08em',
              fontWeight: 500,
            }}
          >
            POWER SYSTEMS ENGINEERING PLATFORM
          </span>
        </div>
      )}
    </div>
  )
}

export default BrandLogo
