import type { ReactNode } from "react";
import { cn } from "../../utils/helpers";

// ─── Glass Panel ────────────────────────────────────────────────────
interface GlassPanelProps {
  readonly children: ReactNode;
  readonly className?: string;
  readonly variant?: "default" | "elevated" | "subtle";
}

export function GlassPanel({ children, className, variant = "default" }: GlassPanelProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  const variants = {
    default: "bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)]",
    elevated: "bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)] shadow-xl",
    subtle: "bg-[var(--bg-card)]/50 backdrop-blur-md border border-[var(--border-primary)]",
  };
  return <div className={cn("rounded-xl", variants[variant], className)}>{children}</div>;
}

// ─── Animated Background ────────────────────────────────────────────
interface AnimatedBackgroundProps {
  readonly className?: string;
  readonly variant?: "gradient" | "mesh" | "radial";
}

export function AnimatedBackground({ className, variant = "gradient" }: AnimatedBackgroundProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  const variants = {
    gradient: (
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-1/2 -left-1/2 w-full h-full bg-gradient-to-br from-[var(--accent-primary)]/5 to-transparent rounded-full animate-spin-slow" />
        <div
          className="absolute -bottom-1/2 -right-1/2 w-full h-full bg-gradient-to-tl from-purple-500/5 to-transparent rounded-full animate-spin-slow"
          style={{ animationDirection: "reverse" }}
        />
      </div>
    ),
    mesh: (
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-[var(--accent-primary)]/3 rounded-full blur-3xl animate-float" />
        <div
          className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-500/3 rounded-full blur-3xl animate-float"
          style={{ animationDelay: "1s" }}
        />
        <div
          className="absolute top-1/2 left-1/2 w-64 h-64 bg-cyan-500/3 rounded-full blur-3xl animate-float"
          style={{ animationDelay: "2s" }}
        />
      </div>
    ),
    radial: (
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,var(--accent-primary)/5,transparent_70%)]" />
      </div>
    ),
  };

  return (
    <div className={cn("absolute inset-0 pointer-events-none", className)}>{variants[variant]}</div>
  );
}

// ─── Status Indicator ───────────────────────────────────────────────
type StatusType = "online" | "offline" | "warning" | "loading";

interface StatusIndicatorProps {
  readonly status: StatusType;
  readonly label?: string;
  readonly size?: "sm" | "md" | "lg";
  readonly showLabel?: boolean;
}

const statusConfig: Record<StatusType, { color: string; pulse: boolean; label: string }> = {
  online: { color: "bg-green-400", pulse: true, label: "Online" },
  offline: { color: "bg-red-400", pulse: false, label: "Offline" },
  warning: { color: "bg-amber-400", pulse: true, label: "Warning" },
  loading: { color: "bg-blue-400", pulse: true, label: "Loading" },
};

export function StatusIndicator({
  status,
  label,
  size = "md",
  showLabel = true,
}: StatusIndicatorProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  const config = statusConfig[status];
  const sizeClasses = { sm: "w-2 h-2", md: "w-2.5 h-2.5", lg: "w-3 h-3" };

  return (
    <div className="flex items-center gap-2">
      <div className="relative">
        <div className={cn(sizeClasses[size], "rounded-full", config.color)} />
        {config.pulse && (
          <div
            className={cn("absolute inset-0 rounded-full", config.color, "animate-ping opacity-50")}
          />
        )}
      </div>
      {showLabel && (
        <span className="text-xs text-[var(--text-muted)]">{label || config.label}</span>
      )}
    </div>
  );
}

// ─── Premium Empty State ────────────────────────────────────────────
interface PremiumEmptyStateProps {
  readonly icon: React.ElementType;
  readonly title: string;
  readonly description: string;
  readonly action?: { label: string; onClick: () => void; icon?: React.ElementType };
  readonly variant?: "default" | "illustration";
}

export function PremiumEmptyState({
  icon: Icon,
  title,
  description,
  action,
  variant = "default",
}: PremiumEmptyStateProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  return (
    <div className="flex flex-col items-center justify-center py-16 px-8 text-center">
      <div
        className={cn(
          "w-20 h-20 rounded-2xl flex items-center justify-center mb-6",
          variant === "illustration"
            ? "bg-gradient-to-br from-[var(--accent-primary)]/10 to-purple-500/10"
            : "bg-[var(--bg-elevated)]",
        )}
      >
        <Icon
          className={cn(
            "w-10 h-10",
            variant === "illustration"
              ? "text-[var(--accent-primary)]"
              : "text-[var(--text-muted)]",
          )}
        />
      </div>
      <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">{title}</h3>
      <p className="text-sm text-[var(--text-secondary)] max-w-sm leading-relaxed mb-6">
        {description}
      </p>
      {action && (
        <button
          onClick={action.onClick}
          className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium bg-[var(--accent-primary)] text-black rounded-lg hover:opacity-90 transition-all"
        >
          {action.icon && <action.icon className="w-4 h-4" />}
          {action.label}
        </button>
      )}
    </div>
  );
}

// ─── Premium Loading State ──────────────────────────────────────────
interface PremiumLoadingProps {
  readonly message?: string;
  readonly variant?: "spinner" | "skeleton" | "progress";
  readonly progress?: number;
}

export function PremiumLoading({
  message = "Loading...",
  variant = "spinner",
  progress,
}: PremiumLoadingProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  if (variant === "skeleton") {
    return (
      <div className="space-y-4 p-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex gap-4">
            <div className="w-10 h-10 rounded-lg skeleton shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-4 skeleton w-3/4 rounded" />
              <div className="h-3 skeleton w-1/2 rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (variant === "progress") {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-4">
        <div className="w-48 h-1.5 bg-[var(--bg-elevated)] rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-[var(--accent-secondary)] to-[var(--accent-primary)] rounded-full transition-all duration-500"
            style={{ width: `${progress ?? 0}%` }}
          />
        </div>
        <span className="text-xs text-[var(--text-muted)]">{message}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-12 gap-4">
      <div className="relative w-12 h-12">
        <div className="absolute inset-0 border-2 border-[var(--border-primary)] rounded-full" />
        <div className="absolute inset-0 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
      </div>
      <span className="text-sm text-[var(--text-secondary)]">{message}</span>
    </div>
  );
}

// ─── Gradient Text ──────────────────────────────────────────────────
interface GradientTextProps {
  readonly children: ReactNode;
  readonly className?: string;
  readonly from?: string;
  readonly to?: string;
}

export function GradientText({
  children,
  className,
  from = "var(--accent-primary)",
  to = "var(--accent-secondary)",
}: GradientTextProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  return (
    <span
      className={cn("bg-clip-text text-transparent", className)}
      style={{ backgroundImage: `linear-gradient(135deg, ${from}, ${to})` }}
    >
      {children}
    </span>
  );
}

// ─── Sparkline SVG Mini-Chart ─────────────────────────────────────
interface SparklineProps {
  readonly data: number[];
  readonly width?: number;
  readonly height?: number;
  readonly color?: string;
  readonly className?: string;
  readonly showArea?: boolean;
  readonly strokeWidth?: number;
}

/**
 * Sparkline — a tiny, inline SVG line chart trend visualization.
 * Perfect for dashboard stat cards to show data direction at a glance.
 */
export function Sparkline({
  data,
  width = 80,
  height = 28,
  color = "var(--accent-primary)",
  className,
  showArea = true,
  strokeWidth = 1.5,
}: SparklineProps) {
  if (!data.length) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const xStep = width / (data.length - 1);

  const points = data.map((val, i) => `${i * xStep},${height - ((val - min) / range) * (height - 4) - 2}`).join(" ");

  // Build area path
  const firstX = 0;
  const lastX = (data.length - 1) * xStep;
  const areaPath = `${points} L${lastX},${height + 2} L${firstX},${height + 2} Z`;

  const trend = data[data.length - 1] >= data[0];
  const trendColor = trend ? "var(--color-success, #22c55e)" : "var(--color-danger, #ef4444)";
  const lineColor = color || trendColor;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("overflow-visible shrink-0", className)}
      aria-hidden="true"
    >
      {showArea && (
        <defs>
          <linearGradient id={`spark-gradient-${trend ? "up" : "down"}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={lineColor} stopOpacity={0.25} />
            <stop offset="100%" stopColor={lineColor} stopOpacity={0.02} />
          </linearGradient>
        </defs>
      )}
      {showArea && (
        <path d={areaPath} fill={`url(#spark-gradient-${trend ? "up" : "down"})`} />
      )}
      <polyline
        points={points}
        fill="none"
        stroke={lineColor}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="drop-shadow-sm"
      />
      {/* End dot */}
      <circle
        cx={(data.length - 1) * xStep}
        cy={height - ((data[data.length - 1] - min) / range) * (height - 4) - 2}
        r={2.5}
        fill={lineColor}
        stroke="var(--bg-card, #1a2340)"
        strokeWidth={1.5}
      />
    </svg>
  );
}

// ─── Glow Card ──────────────────────────────────────────────────────
interface GlowCardProps {
  readonly children: ReactNode;
  readonly className?: string;
  readonly color?: "primary" | "success" | "warning" | "danger";
}

export function GlowCard({ children, className, color = "primary" }: GlowCardProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  const glowColors = {
    primary: "hover:shadow-[var(--glow-primary)] hover:border-[var(--accent-primary)]/30",
    success: "hover:shadow-[var(--glow-success)] hover:border-green-500/30",
    warning: "hover:shadow-[var(--glow-warning)] hover:border-amber-500/30",
    danger: "hover:shadow-[var(--glow-danger)] hover:border-red-500/30",
  };
  return (
    <div
      className={cn(
        "bg-[var(--bg-card)] border border-[var(--border-primary)] rounded-xl transition-all duration-300",
        glowColors[color],
        className,
      )}
    >
      {children}
    </div>
  );
}
