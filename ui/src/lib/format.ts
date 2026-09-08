/**
 * Canonical formatting utilities for dates, numbers, percentages, and bytes/sizes.
 */

export function formatDate(
  date: string | number | Date | null | undefined,
  locale = "en",
): string {
  if (!date) return "";
  const d = typeof date === "object" ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return String(date);
  return d.toLocaleDateString(locale === "ar" ? "ar-EG" : "en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatPercent(value: number, decimals = 1): string {
  if (Number.isNaN(value)) return "0%";
  return `${value.toFixed(decimals)}%`;
}

export function formatSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  if (Number.isNaN(bytes) || bytes < 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${Number.parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i] ?? "B"}`;
}

export const formatBytes = formatSize;
