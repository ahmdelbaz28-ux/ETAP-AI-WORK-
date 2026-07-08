import { motion } from 'framer-motion'
import { Globe } from 'lucide-react'

interface LoginBackgroundProps {
  isRtl: boolean
  onLanguageToggle: () => void
}

export function LoginBackground({ isRtl, onLanguageToggle }: LoginBackgroundProps) {
  return (
    <>
      {/* Lang Selector */}
      <div className={`absolute top-6 ${isRtl ? 'left-6' : 'right-6'} z-50`}>
        <button
          onClick={onLanguageToggle}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-700/50 bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white transition-all text-xs font-semibold"
        >
          <Globe className="w-3.5 h-3.5" />
          <span>{isRtl ? 'English' : 'العربية'}</span>
        </button>
      </div>

      {/* Elite CAD Background - Power Diagram Animation */}
      <div className="absolute inset-0 pointer-events-none z-0">
        {/* Fine grid */}
        <div
          className="absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: `linear-gradient(#3b82f6 1px, transparent 1px), linear-gradient(90deg, #3b82f6 1px, transparent 1px)`,
            backgroundSize: '40px 40px',
          }}
        />

        {/* Dynamic single-line schematic flow simulation */}
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <defs>
            <linearGradient id="bus-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#1e293b" stopOpacity="0.2" />
              <stop offset="50%" stopColor="#3b82f6" stopOpacity="0.6" />
              <stop offset="100%" stopColor="#1e293b" stopOpacity="0.2" />
            </linearGradient>
          </defs>

          {/* High voltage main bus bar */}
          <path d="M100,180 L1340,180" stroke="url(#bus-grad)" strokeWidth="3" strokeLinecap="round" />
          <path d="M100,180 L1340,180" stroke="#00d4ff" strokeWidth="1" strokeLinecap="round" className="animate-pulse" opacity="0.8" />

          {/* Transformer circuit branch */}
          <path d="M400,180 L400,450" stroke="#1e293b" strokeWidth="2" opacity="0.4" />
          <path d="M400,180 L400,450" stroke="#00d4ff" strokeWidth="1.5" strokeDasharray="8 12" strokeDashoffset="0" style={{ animation: 'gridFlow 12s linear infinite' }} />

          {/* Transformer windings symbol */}
          <circle cx="400" cy="280" r="14" fill="none" stroke="#00d4ff" strokeWidth="1.5" />
          <circle cx="400" cy="302" r="14" fill="none" stroke="#3b82f6" strokeWidth="1.5" />

          {/* Lower distribution bus bar */}
          <path d="M250,450 L1190,450" stroke="url(#bus-grad)" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M250,450 L1190,450" stroke="#60a5fa" strokeWidth="1" strokeLinecap="round" className="animate-pulse" opacity="0.6" />

          {/* Generator branch */}
          <path d="M800,180 L800,90" stroke="#1e293b" strokeWidth="2" opacity="0.4" />
          <path d="M800,180 L800,90" stroke="#22c55e" strokeWidth="1.5" strokeDasharray="10 10" strokeDashoffset="0" style={{ animation: 'gridFlowRev 10s linear infinite' }} />
          <circle cx="800" cy="70" r="18" fill="#070b14" stroke="#22c55e" strokeWidth="1.5" />
          <text x="800" y="75" textAnchor="middle" fill="#22c55e" fontSize="14" fontWeight="bold" fontFamily="monospace">G</text>

          {/* Feeder load circuit */}
          <path d="M600,450 L600,580" stroke="#1e293b" strokeWidth="2" opacity="0.4" />
          <path d="M600,450 L600,580" stroke="#fbbf24" strokeWidth="1.5" strokeDasharray="8 10" strokeDashoffset="0" style={{ animation: 'gridFlow 8s linear infinite' }} />
          <polygon points="600,588 592,572 608,572" fill="#fbbf24" stroke="#fbbf24" strokeWidth="1" />

          {/* Network dynamic particle paths */}
          <circle r="3.5" fill="#00d4ff" opacity="0.8">
            <animateMotion dur="8s" repeatCount="indefinite" path="M800,90 L800,180 L400,180 L400,450 L600,450 L600,572" />
          </circle>
          <circle r="2.5" fill="#22c55e" opacity="0.8">
            <animateMotion dur="8s" begin="2.5s" repeatCount="indefinite" path="M800,90 L800,180 L400,180 L400,450 L600,450 L600,572" />
          </circle>
          <circle r="2.5" fill="#fbbf24" opacity="0.8">
            <animateMotion dur="8s" begin="5s" repeatCount="indefinite" path="M800,90 L800,180 L400,180 L400,450 L600,450 L600,572" />
          </circle>

          {/* Circuit breaker branch */}
          <path d="M1000,450 L1000,580" stroke="#1e293b" strokeWidth="2" opacity="0.4" />
          <path d="M1000,450 L1000,580" stroke="#a78bfa" strokeWidth="1.5" strokeDasharray="8 8" strokeDashoffset="0" style={{ animation: 'gridFlow 14s linear infinite' }} />
          <rect x="993" y="495" width="14" height="20" fill="#070b14" stroke="#a78bfa" strokeWidth="1.5" />
          <line x1="993" y1="505" x2="1007" y2="505" stroke="#a78bfa" strokeWidth="1.5" />

          <style>{`
            @keyframes gridFlow {
              to { stroke-dashoffset: -120; }
            }
            @keyframes gridFlowRev {
              to { stroke-dashoffset: 120; }
            }
          `}</style>
        </svg>

        {/* Ambient background aura */}
        <div className="absolute top-10 right-20 w-[600px] h-[600px] rounded-full bg-blue-500/[0.02] blur-[140px]" />
        <div className="absolute bottom-10 left-20 w-[500px] h-[500px] rounded-full bg-blue-600/[0.015] blur-[120px]" />
      </div>
    </>
  )
}