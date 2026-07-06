/**
 * BrandLogo — AhmedETAP professional logo v2.
 *
 * Design: "Power Grid Node" — a simplified one-line diagram (single-line
 * diagram notation used in power systems engineering) forming the
 * visual identity. It depicts a 3-bus system with a generator, a
 * transformer, and a load — the most fundamental power system topology.
 *
 * Visual elements:
 * - Top node (generator): amber circle with "G" — represents generation
 * - Middle bus: horizontal bar with 3 junctions — the main busbar
 * - Bottom nodes: blue circles — represent loads/feeders
 * - Connecting lines: thin, precise — like schematic drawings
 *
 * Colors are drawn from the application's CSS variable system:
 * - Background: #0f172a (--bg-primary, deep navy)
 * - Bus/lines: #3b82f6 (brand blue)
 * - Junctions: #60a5fa (light blue)
 * - Generator: #f59e0b (amber — represents active energy)
 *
 * No glow filters, no animations, no gradients on shapes — just clean
 * geometric lines like ETAP's actual schematic notation.
 */
interface BrandLogoProps {
  size?: number
  withWordmark?: boolean
  animated?: boolean
  className?: string
}

export function BrandLogo({
  size = 44,
  withWordmark = false,
  className = '',
}: BrandLogoProps) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 120 120"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label="AhmedETAP"
      >
        {/* Background — deep navy rounded square */}
        <rect width="120" height="120" rx="26" fill="#0f172a" />
        {/* Subtle top-edge highlight (like ETAP's dark UI panels) */}
        <rect x="1" y="1" width="118" height="118" rx="25" stroke="#1e3a5f" strokeWidth="1" />

        {/* === One-line diagram (schematic) === */}

        {/* Top: Generator node (amber) */}
        <circle cx="60" cy="22" r="9" fill="#f59e0b" />
        <text
          x="60" y="26"
          textAnchor="middle"
          fontFamily="system-ui, -apple-system, sans-serif"
          fontSize="9"
          fontWeight="700"
          fill="#0f172a"
        >
          G
        </text>

        {/* Line from generator to bus */}
        <line x1="60" y1="31" x2="60" y2="50" stroke="#3b82f6" strokeWidth="2.5" />

        {/* Transformer symbol (two overlapping circles) between gen and bus */}
        <circle cx="60" cy="40" r="6" fill="none" stroke="#3b82f6" strokeWidth="2" />
        <circle cx="60" cy="46" r="6" fill="none" stroke="#3b82f6" strokeWidth="2" />

        {/* Main busbar — horizontal line with 3 junction nodes */}
        <line x1="28" y1="62" x2="92" y2="62" stroke="#3b82f6" strokeWidth="3" strokeLinecap="round" />

        {/* Bus junction nodes */}
        <circle cx="28" cy="62" r="4" fill="#60a5fa" />
        <circle cx="60" cy="62" r="5" fill="#60a5fa" />
        <circle cx="92" cy="62" r="4" fill="#60a5fa" />

        {/* Feeder lines going down from each bus junction */}
        <line x1="28" y1="66" x2="28" y2="86" stroke="#3b82f6" strokeWidth="2" />
        <line x1="60" y1="67" x2="60" y2="86" stroke="#3b82f6" strokeWidth="2" />
        <line x1="92" y1="66" x2="92" y2="86" stroke="#3b82f6" strokeWidth="2" />

        {/* Load nodes (bottom) */}
        {/* Left: Motor load */}
        <circle cx="28" cy="92" r="6" fill="none" stroke="#60a5fa" strokeWidth="2" />
        <text x="28" y="95" textAnchor="middle" fontFamily="system-ui" fontSize="7" fontWeight="600" fill="#60a5fa">M</text>

        {/* Center: Load arrow */}
        <path d="M 55 86 L 60 96 L 65 86 Z" fill="#60a5fa" />

        {/* Right: Capacitor load */}
        <line x1="88" y1="86" x2="96" y2="86" stroke="#60a5fa" strokeWidth="2" />
        <line x1="88" y1="90" x2="96" y2="90" stroke="#60a5fa" strokeWidth="2" />
        <line x1="92" y1="84" x2="92" y2="86" stroke="#60a5fa" strokeWidth="2" />
        <line x1="92" y1="90" x2="92" y2="92" stroke="#60a5fa" strokeWidth="2" />
      </svg>

      {withWordmark && (
        <div className="flex flex-col leading-none">
          <span
            className="font-bold tracking-tight text-white"
            style={{ fontSize: size * 0.42 }}
          >
            AhmedETAP
          </span>
          <span
            className="text-slate-500 mt-0.5 tracking-wide uppercase"
            style={{ fontSize: size * 0.13, fontWeight: 500 }}
          >
            Power Systems Engineering
          </span>
        </div>
      )}
    </div>
  )
}

export default BrandLogo
