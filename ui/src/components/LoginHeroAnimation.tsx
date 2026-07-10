import { motion } from 'framer-motion'

export default function LoginHeroAnimation() {
  return (
    <div className="absolute inset-0 pointer-events-none z-0">
      {/* Subtle grid */}
      <div
        className="absolute inset-0 opacity-[0.06]"
        style={{
          backgroundImage:
            'linear-gradient(#3b82f6 1px, transparent 1px), linear-gradient(90deg, #3b82f6 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      {/* Ambient glow */}
      <div className="absolute top-10 right-20 w-[600px] h-[600px] rounded-full bg-blue-500/[0.07] blur-[140px]" />
      <div className="absolute bottom-10 left-20 w-[500px] h-[500px] rounded-full bg-blue-600/[0.05] blur-[120px]" />

      <svg
        className="absolute inset-0 w-full h-full"
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="streamGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#1e293b" stopOpacity="0.0" />
            <stop offset="50%" stopColor="#00d4ff" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#1e293b" stopOpacity="0.0" />
          </linearGradient>
          <radialGradient id="meetGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#00d4ff" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#00d4ff" stopOpacity="0" />
          </radialGradient>
          <filter id="softGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="18" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <marker id="dot" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <circle cx="5" cy="5" r="2.5" fill="#00d4ff" opacity="0.9" />
          </marker>
        </defs>

        <circle cx="720" cy="920" r="90" fill="url(#meetGlow)">
          <animate attributeName="opacity" values="0.4;0.7;0.4" dur="3s" repeatCount="indefinite" />
        </circle>
        <path
          d="M720,920 L320,620"
          stroke="url(#streamGrad)"
          strokeWidth="2"
          strokeDasharray="10 16"
          opacity="0.6"
        >
          <animate attributeName="stroke-dashoffset" from="0" to="-120" dur="2.8s" repeatCount="indefinite" />
        </path>
        <path
          d="M720,920 L1120,620"
          stroke="url(#streamGrad)"
          strokeWidth="2"
          strokeDasharray="10 16"
          opacity="0.6"
        >
          <animate attributeName="stroke-dashoffset" from="0" to="-120" dur="2.8s" begin="0.9s" repeatCount="indefinite" />
        </path>

        <motion.g
          animate={{ y: [0, -14, 0] }}
          transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
        >
          <path
            d="M320,620 C340,610 400,600 460,590 C490,586 510,588 520,595 C525,600 524,608 518,615 C500,632 460,640 420,645 C380,650 340,648 320,640 C316,638 316,624 320,620 Z"
            fill="#0b1220"
            stroke="#60a5fa"
            strokeWidth="2.2"
            opacity="0.85"
          />
          <path
            d="M460,590 C470,572 488,558 500,548 C508,541 516,538 520,545 C524,552 520,562 510,572 C498,584 478,590 460,590 Z"
            fill="#0b1220"
            stroke="#60a5fa"
            strokeWidth="2"
            opacity={0.95}
          />
          <circle cx="480" cy="576" r="3.5" fill="#00d4ff" opacity="0.9">
            <animate attributeName="opacity" values="0.9;0.3;0.9" dur="1.6s" repeatCount="indefinite" />
          </circle>
          <circle cx="496" cy="566" r="2.8" fill="#3b82f6" opacity="0.8">
            <animate attributeName="opacity" values="0.8;0.3;0.8" dur="1.6s" begin="0.4s" repeatCount="indefinite" />
          </circle>
        </motion.g>

        <motion.g
          animate={{ y: [0, -14, 0] }}
          transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut', delay: 0.15 }}
        >
          <path
            d="M1120,620 C1100,610 1040,600 980,590 C950,586 930,588 920,595 C915,600 916,608 922,615 C940,632 980,640 1020,645 C1060,650 1100,648 1120,640 C1124,638 1124,624 1120,620 Z"
            fill="#0b1220"
            stroke="#22d3ee"
            strokeWidth="2.2"
            opacity="0.85"
          />
          <path
            d="M980,590 C970,572 952,558 940,548 C932,541 924,538 920,545 C916,552 920,562 930,572 C942,584 962,590 980,590 Z"
            fill="#0b1220"
            stroke="#22d3ee"
            strokeWidth="2"
            opacity={0.95}
          />
          <line x1="948" y1="570" x2="966" y2="560" stroke="#a5f3fc" strokeWidth="3" opacity="0.7" />
          <line x1="935" y1="556" x2="952" y2="548" stroke="#a5f3fc" strokeWidth="3" opacity="0.7" />
          <circle cx="940" cy="548" r="4" fill="#00d4ff" opacity="0.9">
            <animate attributeName="opacity" values="0.9;0.3;0.9" dur="1.6s" begin="0.7s" repeatCount="indefinite" />
          </circle>
        </motion.g>

        <g filter="url(#softGlow)">
          <circle cx="720" cy="760" r="22" fill="#0b1220" stroke="#00d4ff" strokeWidth="2.2" />
          <motion.circle
            cx="720"
            cy="760"
            r="9"
            fill="#00d4ff"
            animate={{ opacity: [0.75, 1, 0.75], r: [9, 11, 9] }}
            transition={{ duration: 3, repeat: Infinity }}
          />
        </g>
        <circle cx="720" cy="760" r="34" fill="none" stroke="#00d4ff" strokeWidth="1.2" opacity="0.35">
          <animateTransform attributeName="transform" type="rotate" from="0 720 760" to="360 720 760" dur="12s" repeatCount="indefinite" />
        </circle>

        <circle cx="720" cy="760" r="3.2" fill="#ffffff" opacity="0.85" />
        <circle cx="580" cy="860" r="2.4" fill="#00d4ff" opacity="0.7" />
        <circle cx="860" cy="860" r="2.4" fill="#00d4ff" opacity="0.7" />
        <circle cx="640" cy="920" r="2" fill="#60a5fa" opacity="0.6" />
        <circle cx="800" cy="920" r="2" fill="#60a5fa" opacity="0.6" />

        <path d="M720,738 Q720,700 640,680" fill="none" stroke="#3b82f6" strokeWidth="1.4" opacity="0.35" strokeDasharray="4 5">
          <animate attributeName="stroke-dashoffset" from="0" to="-120" dur="2.8s" begin="0s" repeatCount="indefinite" />
        </path>
        <path d="M720,738 Q720,700 800,680" fill="none" stroke="#22d3ee" strokeWidth="1.4" opacity="0.35" strokeDasharray="4 5">
          <animate attributeName="stroke-dashoffset" from="0" to="-120" dur="2.8s" begin="1s" repeatCount="indefinite" />
        </path>
      </svg>
    </div>
  )
}