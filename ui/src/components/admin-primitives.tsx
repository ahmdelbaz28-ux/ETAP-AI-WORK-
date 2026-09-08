/**
 * Shared UI primitives for admin/debug pages.
 *
 * Replaces the per-page `StatRow` / `ErrorBanner` / `LoadingRow` /
 * `inputClass` / `labelClass` copies that were duplicated across
 * MagicLinks.tsx, Mfa.tsx, EmailOtp.tsx, EmailDigest.tsx.
 *
 * These are intentionally tiny and dependency-free (only lucide-react
 * for the icons) so they can be tree-shaken per-page without pulling
 * in the heavier `components/ui` index.
 *
 * Ref: fix/admin-pages-hardening (#4)
 */

import { AlertTriangle, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardSection } from "./ui/Card";

/**
 * A two-column key/value row used inside result cards. Label is
 * uppercased tracking-wider; value is monospaced right-aligned and
 * breaks long strings.
 */
export function StatRow({ label, value }: { readonly label: string; readonly value: ReactNode }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-[var(--border-primary)] last:border-0 gap-3">
      <span className="text-xs uppercase tracking-wider text-zinc-400 font-semibold shrink-0">
        {label}
      </span>
      <span className="text-sm text-zinc-100 font-mono text-right break-all">{value}</span>
    </div>
  );
}

/**
 * Inline error banner with `role="alert"` for screen-reader
 * announcement. Red-tinted to stand out from the surrounding
 * dark-on-dark admin card chrome.
 */
export function ErrorBanner({ message }: { readonly message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300"
    >
      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
      <span className="break-words">{message}</span>
    </div>
  );
}

/**
 * Inline loading row with a spinner. Used in result cards while a
 * request is in flight, before the response arrives.
 */
export function LoadingRow({ label }: { readonly label: string }) {
  return (
    <div className="flex items-center gap-2 py-2 text-sm text-zinc-400">
      <Loader2 className="w-4 h-4 animate-spin" />
      <span>{label}</span>
    </div>
  );
}

/**
 * Shared Tailwind class strings for admin form inputs and labels.
 * Kept as plain strings (not components) so callers can compose
 * them with additional classes via template literals.
 */
export const inputClass =
  "w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50";

export const labelClass = "block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1";

export function StatCard({
  label,
  value,
  sub,
  tone = "neutral",
  icon,
}: {
  readonly label: string;
  readonly value: ReactNode;
  readonly sub?: ReactNode;
  readonly tone?: "success" | "danger" | "warning" | "neutral";
  readonly icon?: ReactNode;
}) {
  const toneClass = {
    success: "text-green-400",
    danger: "text-red-400",
    warning: "text-amber-400",
    neutral: "text-zinc-100",
  }[tone];
  const iconBg = {
    success: "bg-green-500/10 text-green-400",
    danger: "bg-red-500/10 text-red-400",
    warning: "bg-amber-500/10 text-amber-400",
    neutral: "bg-zinc-500/10 text-zinc-300",
  }[tone];
  return (
    <Card>
      <CardSection className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] uppercase tracking-wider text-zinc-400 font-semibold">
              {label}
            </p>
            <p className={`mt-1 text-2xl font-bold ${toneClass}`}>{value}</p>
            {sub ? <p className="mt-1 text-xs text-zinc-500">{sub}</p> : null}
          </div>
          {icon ? <div className={`shrink-0 rounded-lg p-2 ${iconBg}`}>{icon}</div> : null}
        </div>
      </CardSection>
    </Card>
  );
}

export function LoadingInline({ label }: { readonly label: string }) {
  return (
    <div className="flex items-center gap-2 text-zinc-400">
      <Loader2 className="h-4 w-4 animate-spin" />
      <span>{label}</span>
    </div>
  );
}

export function JsonBlock({ data }: { readonly data: unknown }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-md border border-zinc-700 bg-zinc-900 p-3 text-xs text-zinc-200">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

