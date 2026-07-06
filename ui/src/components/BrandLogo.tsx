/**
 * BrandLogo — AhmedETAP professional logo.
 *
 * Design: Clean monogram combining a power-systems one-line-diagram
 * motif with the letter "A". The design uses:
 * - A solid square tile with a deep blue gradient (professional, not flashy)
 * - Two converging lines forming an "A" (transmission tower silhouette)
 * - A horizontal power bus with junction nodes (single-line-diagram notation)
 * - A spark at the apex (energy convergence point)
 * - No glow filters, no animated effects — static and crisp like ETAP's logo
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
        <defs>
          <linearGradient id="tile-grad" x1="0" y1="0" x2="120" y2="120" gradientUnits="userSpaceOnUse">
            <stop stopColor="#1e3a8a" />
            <stop offset="1" stopColor="#0f172a" />
          </linearGradient>
        </defs>

        {/* Background tile — rounded square, deep blue */}
        <rect width="120" height="120" rx="24" fill="url(#tile-grad)" />

        {/* Subtle border ring */}
        <rect x="0.5" y="0.5" width="119" height="119" rx="23.5" stroke="#2563eb" strokeWidth="1" opacity="0.3" />

        {/* The "A" — two converging lines (transmission tower legs) */}
        <line x1="32" y1="92" x2="60" y2="28" stroke="#3b82f6" strokeWidth="4.5" strokeLinecap="round" />
        <line x1="88" y1="92" x2="60" y2="28" stroke="#3b82f6" strokeWidth="4.5" strokeLinecap="round" />

        {/* Crossbar — power bus with junction nodes */}
        <line x1="44" y1="64" x2="76" y2="64" stroke="#60a5fa" strokeWidth="3" strokeLinecap="round" />
        <circle cx="44" cy="64" r="3.5" fill="#60a5fa" />
        <circle cx="60" cy="64" r="4" fill="#93c5fd" />
        <circle cx="76" cy="64" r="3.5" fill="#60a5fa" />

        {/* Apex node */}
        <circle cx="60" cy="28" r="5" fill="#dbeafe" />

        {/* Base nodes — tower feet */}
        <circle cx="32" cy="92" r="4" fill="#3b82f6" />
        <circle cx="88" cy="92" r="4" fill="#3b82f6" />
      </svg>

      {withWordmark && (
        <div className="flex flex-col leading-none">
          <span
            className="font-bold tracking-tight text-white"
            style={{ fontSize: size * 0.45 }}
          >
            AhmedETAP
          </span>
          <span
            className="text-slate-500 mt-1 tracking-wide uppercase"
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
