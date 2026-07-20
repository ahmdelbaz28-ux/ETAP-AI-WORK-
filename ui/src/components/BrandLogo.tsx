/**
 * BrandLogo — AhmedETAP premium, minimal, enterprise-grade logo.
 *
 * Design Concept: "Isometric Power Node Cube"
 * It depicts a 3D isometric network hub. The three visible planes represent the
 * three phases of AC power (A, B, C) and a centralized system matrix.
 * Clean, high-contrast, schematic vector overlay representing generation, distribution, and grounding.
 */
interface BrandLogoProps {
  size?: number;
  withWordmark?: boolean;
  className?: string;
}

export function BrandLogo({ size = 44, withWordmark = false, className = "" }: BrandLogoProps) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 512 512"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label="AhmedETAP"
      >
        <defs>
          {/* Premium Gradients */}
          <linearGradient id="brandLeftGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#1e3a8a" />
            <stop offset="100%" stopColor="#3b82f6" />
          </linearGradient>
          <linearGradient id="brandRightGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#0f766e" />
            <stop offset="100%" stopColor="#0d9488" />
          </linearGradient>
          <linearGradient id="brandTopGrad" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#1d4ed8" />
            <stop offset="100%" stopColor="#00d4ff" />
          </linearGradient>
          <linearGradient id="brandGlowGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#00d4ff" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Ambient Glow Background */}
        <circle cx="256" cy="256" r="220" fill="url(#brandGlowGrad)" />

        {/* Isometric 3D Hexagonal Node Base */}
        {/* Left Side: Indigo to Blue (representing generation / inputs) */}
        <path
          d="M256,70 L256,256 L90,352 L90,166 Z"
          fill="url(#brandLeftGrad)"
          stroke="#070b14"
          strokeWidth="6"
          strokeLinejoin="round"
        />

        {/* Right Side: Dark Teal to Emerald (representing output / distribution) */}
        <path
          d="M256,256 L422,352 L422,166 L256,70 Z"
          fill="url(#brandRightGrad)"
          stroke="#070b14"
          strokeWidth="6"
          strokeLinejoin="round"
        />

        {/* Top/Base Plane: Blue to Cyan (representing system matrix & grounding) */}
        <path
          d="M90,352 L256,256 L422,352 L256,448 Z"
          fill="url(#brandTopGrad)"
          stroke="#070b14"
          strokeWidth="6"
          strokeLinejoin="round"
        />

        {/* High-Precision Schematic Overlay (futuristic HUD wireframe) */}
        <line x1="90" y1="352" x2="256" y2="256" stroke="#ffffff" strokeWidth="3" opacity="0.3" />
        <line x1="422" y1="352" x2="256" y2="256" stroke="#ffffff" strokeWidth="3" opacity="0.3" />
        <line x1="256" y1="70" x2="256" y2="256" stroke="#ffffff" strokeWidth="3" opacity="0.3" />

        {/* Left plane node track */}
        <path
          d="M150,210 L256,256"
          stroke="#ffffff"
          strokeWidth="4"
          strokeLinecap="round"
          opacity="0.85"
        />
        <circle cx="150" cy="210" r="12" fill="#00d4ff" stroke="#ffffff" strokeWidth="3" />

        {/* Right plane node track */}
        <path
          d="M362,210 L256,256"
          stroke="#ffffff"
          strokeWidth="4"
          strokeLinecap="round"
          opacity="0.85"
        />
        <circle cx="362" cy="210" r="12" fill="#0d9488" stroke="#ffffff" strokeWidth="3" />

        {/* Ground node track */}
        <path
          d="M256,370 L256,256"
          stroke="#ffffff"
          strokeWidth="4"
          strokeLinecap="round"
          opacity="0.85"
        />
        <circle cx="256" cy="370" r="12" fill="#00d4ff" stroke="#ffffff" strokeWidth="3" />

        {/* Central hub connection */}
        <circle cx="256" cy="256" r="16" fill="#ffffff" stroke="#00d4ff" strokeWidth="6" />
        <circle cx="256" cy="256" r="6" fill="#070b14" />
      </svg>

      {withWordmark && (
        <div className="flex flex-col leading-none">
          <span className="font-bold tracking-tight text-white" style={{ fontSize: size * 0.42 }}>
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
  );
}

export default BrandLogo;
