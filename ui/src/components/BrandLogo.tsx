/**
 * BrandLogo — AhmedETAP simplified enterprise mark.
 *
 * Design Concept: "AE Seal + Busbar"
 * A flat navy seal ring carrying a bold "AE" monogram above a sky busbar.
 * Two flat colors only, no gradients, no glow — legible from 16px favicon
 * up to large report headers.
 */
interface BrandLogoProps {
  readonly size?: number;
  readonly withWordmark?: boolean;
  readonly className?: string;
}

const NAVY = "#0A2E5C";
const SKY = "#38BDF8";

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
        {/* Seal ring — thick flat stroke survives small sizes */}
        <circle cx="256" cy="256" r="224" stroke={NAVY} strokeWidth="36" fill="#FFFFFF" />
        {/* AE monogram */}
        <text
          x="256"
          y="302"
          textAnchor="middle"
          fontFamily="Arial Black, Arial, sans-serif"
          fontWeight="900"
          fontSize="172"
          fill={NAVY}
        >
          AE
        </text>
        {/* Busbar */}
        <rect x="116" y="322" width="280" height="30" rx="15" fill={SKY} />
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
