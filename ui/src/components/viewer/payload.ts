/**
 * Payload display helpers for P6 viewers.
 *
 * We never invent wire schemas. These helpers only format whatever data the
 * backend actually delivered — redacting values whose key looks secret so a
 * raw JSON pane can never leak API keys, tokens, or passwords.
 */

const SECRET_KEY_RE = /(api[_-]?key|secret|token|password|authorization|credential)/i;

export function isSecretKey(key: string): boolean {
  return SECRET_KEY_RE.test(key);
}

/** Recursively mask secret-looking values (max depth guard). */
export function redactSecrets(value: unknown, depth = 0): unknown {
  if (depth > 8) return "[depth-limit]";
  if (Array.isArray(value)) return value.map((item) => redactSecrets(item, depth + 1));
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, child]) => [
        key,
        isSecretKey(key) ? "[REDACTED]" : redactSecrets(child, depth + 1),
      ]),
    );
  }
  return value;
}

export function toRedactedJson(value: unknown): string {
  try {
    return JSON.stringify(redactSecrets(value), null, 2);
  } catch {
    return String(value);
  }
}

// ─── Table row extraction helpers ──────────────────────────────────────────

/** A flat row for the Table tab – keys are column names, values are primitives. */
export type TableRow = Record<string, string | number | boolean | null>;

/**
 * Attempt to extract tabular rows from a result summary.
 *
 * Strategy (in priority order — never invents data):
 * 1. summary.results  (array of objects)
 * 2. summary.network_snapshot.buses  (array of objects)
 * 3. summary.network_snapshot.branches  (array of objects)
 * 4. summary.network_snapshot (if it is an array)
 * 5. Flatten scalar top-level summary keys into a single row.
 *
 * Returns { rows, columns } or { rows: [], columns: [] } when no table found.
 */
export function extractTableData(summary: Record<string, unknown> | null | undefined): {
  rows: TableRow[];
  columns: string[];
} {
  if (!summary) return { rows: [], columns: [] };

  // Helper: convert array of objects → flat rows
  const toRows = (arr: unknown): TableRow[] | null => {
    if (!Array.isArray(arr)) return null;
    const rows: TableRow[] = arr
      .filter((item) => item !== null && typeof item === "object" && !Array.isArray(item))
      .map((item) => flattenObject(item as Record<string, unknown>));
    return rows.length > 0 ? rows : null;
  };

  // 1. summary.results
  const fromResults = toRows(summary.results);
  if (fromResults) return buildResult(fromResults);

  // 2. summary.network_snapshot.buses
  const snap = summary.network_snapshot;
  if (snap && typeof snap === "object" && !Array.isArray(snap)) {
    const snapRecord = snap as Record<string, unknown>;
    const fromBuses = toRows(snapRecord.buses);
    if (fromBuses) return buildResult(fromBuses);
    const fromBranches = toRows(snapRecord.branches);
    if (fromBranches) return buildResult(fromBranches);
  }

  // 3. network_snapshot itself is an array
  const fromSnapArray = toRows(snap);
  if (fromSnapArray) return buildResult(fromSnapArray);

  // 4. Scalar keys at summary level → single row
  const scalarRow: TableRow = {};
  for (const [k, v] of Object.entries(summary)) {
    if (v === null || typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
      scalarRow[k] = isSecretKey(k) ? "[REDACTED]" : v;
    }
  }
  if (Object.keys(scalarRow).length > 0) return buildResult([scalarRow]);

  return { rows: [], columns: [] };
}

function buildResult(rows: TableRow[]): { rows: TableRow[]; columns: string[] } {
  const columnSet = new Set<string>();
  rows.forEach((row) => Object.keys(row).forEach((k) => columnSet.add(k)));
  return { rows, columns: Array.from(columnSet) };
}

/** Flatten one level deep (nested objects become "parent.child" keys). */
function flattenObject(obj: Record<string, unknown>, prefix = ""): TableRow {
  const result: TableRow = {};
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (isSecretKey(k)) {
      result[key] = "[REDACTED]";
    } else if (v !== null && typeof v === "object" && !Array.isArray(v)) {
      // One level of nesting only
      Object.assign(result, flattenObject(v as Record<string, unknown>, key));
    } else if (typeof v === "string" || typeof v === "number" || typeof v === "boolean" || v === null) {
      result[key] = v;
    }
  }
  return result;
}

// ─── Chart data extraction ──────────────────────────────────────────────────

export interface VoltagePoint {
  bus: string;
  voltage_pu: number;
}

export interface LoadingPoint {
  branch: string;
  loading_pct: number;
}

/**
 * Extract voltage profile data from summary.
 * Reads `results` array or `network_snapshot.buses` — never invents values.
 */
export function extractVoltageProfile(
  summary: Record<string, unknown> | null | undefined,
): VoltagePoint[] {
  if (!summary) return [];

  const tryArray = (arr: unknown): VoltagePoint[] => {
    if (!Array.isArray(arr)) return [];
    const points: VoltagePoint[] = [];
    for (const item of arr) {
      if (!item || typeof item !== "object") continue;
      const r = item as Record<string, unknown>;
      const bus =
        typeof r.bus === "string"
          ? r.bus
          : typeof r.name === "string"
            ? r.name
            : typeof r.id === "string"
              ? r.id
              : null;
      const v =
        typeof r.voltage_pu === "number"
          ? r.voltage_pu
          : typeof r.v_pu === "number"
            ? r.v_pu
            : typeof r.voltage === "number"
              ? r.voltage
              : null;
      if (bus && v !== null) points.push({ bus, voltage_pu: v });
    }
    return points;
  };

  const fromResults = tryArray(summary.results);
  if (fromResults.length > 0) return fromResults;

  const snap = summary.network_snapshot;
  if (snap && typeof snap === "object" && !Array.isArray(snap)) {
    const from = tryArray((snap as Record<string, unknown>).buses);
    if (from.length > 0) return from;
  }
  return [];
}

/**
 * Extract branch loading data from summary.
 */
export function extractLoadingProfile(
  summary: Record<string, unknown> | null | undefined,
): LoadingPoint[] {
  if (!summary) return [];

  const tryArray = (arr: unknown): LoadingPoint[] => {
    if (!Array.isArray(arr)) return [];
    const points: LoadingPoint[] = [];
    for (const item of arr) {
      if (!item || typeof item !== "object") continue;
      const r = item as Record<string, unknown>;
      const branch =
        typeof r.branch === "string"
          ? r.branch
          : typeof r.name === "string"
            ? r.name
            : typeof r.id === "string"
              ? r.id
              : null;
      const pct =
        typeof r.loading_pct === "number"
          ? r.loading_pct
          : typeof r.loading === "number"
            ? r.loading
            : typeof r.utilization_pct === "number"
              ? r.utilization_pct
              : null;
      if (branch && pct !== null) points.push({ branch, loading_pct: pct });
    }
    return points;
  };

  const fromResults = tryArray(summary.results);
  if (fromResults.length > 0) return fromResults;

  const snap = summary.network_snapshot;
  if (snap && typeof snap === "object" && !Array.isArray(snap)) {
    const from = tryArray((snap as Record<string, unknown>).branches);
    if (from.length > 0) return from;
  }
  return [];
}

// ─── Diagram node/edge extraction ──────────────────────────────────────────

export interface DiagramNode {
  id: string;
  type: "bus" | "gen" | "load";
  label: string;
  voltage_pu?: number;
}

export interface DiagramEdge {
  id: string;
  from: string;
  to: string;
  label?: string;
}

/** Extract simplified one-line diagram nodes + edges from network_snapshot. */
export function extractDiagram(summary: Record<string, unknown> | null | undefined): {
  nodes: DiagramNode[];
  edges: DiagramEdge[];
} {
  if (!summary) return { nodes: [], edges: [] };

  const snap = summary.network_snapshot;
  if (!snap || typeof snap !== "object" || Array.isArray(snap)) return { nodes: [], edges: [] };

  const snapRecord = snap as Record<string, unknown>;

  const nodes: DiagramNode[] = [];
  const edges: DiagramEdge[] = [];

  const buses = snapRecord.buses;
  if (Array.isArray(buses)) {
    for (const bus of buses) {
      if (!bus || typeof bus !== "object") continue;
      const r = bus as Record<string, unknown>;
      const id = String(r.id ?? r.name ?? "");
      if (!id) continue;
      nodes.push({
        id,
        type: "bus",
        label: String(r.name ?? r.id ?? id),
        voltage_pu: typeof r.voltage_pu === "number" ? r.voltage_pu : undefined,
      });
    }
  }

  const branches = snapRecord.branches;
  if (Array.isArray(branches)) {
    for (const br of branches) {
      if (!br || typeof br !== "object") continue;
      const r = br as Record<string, unknown>;
      const from = String(r.from_bus ?? r.from ?? "");
      const to = String(r.to_bus ?? r.to ?? "");
      const id = String(r.id ?? r.name ?? `${from}-${to}`);
      if (!from || !to) continue;
      edges.push({ id, from, to, label: String(r.name ?? r.id ?? "") || undefined });
    }
  }

  return { nodes, edges };
}