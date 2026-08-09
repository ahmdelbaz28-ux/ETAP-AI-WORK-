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
