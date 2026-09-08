/**
 * Canonical power system file validation and import preview helpers.
 * Consolidates file size boundaries (10 MiB), allowed extensions, and risk badge variants.
 */

export const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024; // 10 MiB canonical limit

export const ALLOWED_EXTENSIONS = [
  ".json",
  ".xml",
  ".cim",
  ".raw",
  ".m",
  ".csv",
  ".tsv",
  ".etap",
] as const;

export type AllowedExtension = (typeof ALLOWED_EXTENSIONS)[number];

export interface FileValidationResult {
  valid: boolean;
  error?: string;
}

/**
 * Validates file size (max 10 MiB) and power-system extension.
 */
export function validatePowerFile(file: File): FileValidationResult {
  if (file.size > MAX_ATTACHMENT_BYTES) {
    return {
      valid: false,
      error: `File exceeds maximum allowed size of 10 MB (${(file.size / (1024 * 1024)).toFixed(1)} MB)`,
    };
  }

  const ext = "." + (file.name.split(".").pop()?.toLowerCase() ?? "");
  if (!ALLOWED_EXTENSIONS.includes(ext as AllowedExtension)) {
    return {
      valid: false,
      error: `Unsupported file type "${ext}". Supported: ${ALLOWED_EXTENSIONS.join(", ")}`,
    };
  }

  return { valid: true };
}

/**
 * Canonical risk variant mapping for import previews.
 * Maps 'low' -> 'success', 'medium' -> 'warning', 'high' / 'danger' -> 'danger', otherwise 'info'.
 */
export function riskVariant(riskLevel: string): "success" | "warning" | "danger" | "info" {
  const normalized = riskLevel?.toLowerCase();
  if (normalized === "low") return "success";
  if (normalized === "medium") return "warning";
  if (normalized === "high" || normalized === "danger") return "danger";
  return "info";
}

/**
 * Unified schema for import preview data returned from the server.
 */
export interface ImportPreviewData {
  success?: boolean;
  preview_id: string;
  format: string;
  filename: string;
  file_size_bytes?: number;
  records_count: number;
  buses_count: number;
  branches_count: number;
  affected_tables?: string[];
  risk_level: "low" | "medium" | "high" | string;
  requires_approval?: boolean;
  warnings?: string[];
  errors?: string[];
  created_at?: string;
}

export type ImportPreviewResponse = ImportPreviewData;
