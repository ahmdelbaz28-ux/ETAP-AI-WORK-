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

// ─── Primitive extractor helpers (avoids S3358, S6551, reduces S3776) ───────

function getFieldString(record: Record<string, unknown>, keys: readonly string[]): string | null {
  for (const k of keys) {
    const val = record[k];
    if (typeof val === "string" && val.trim() !== "") {
      return val;
    }
    if (typeof val === "number" && !Number.isNaN(val)) {
      return String(val);
    }
  }
  return null;
}

function getFieldNumber(record: Record<string, unknown>, keys: readonly string[]): number | null {
  for (const k of keys) {
    const val = record[k];
    if (typeof val === "number" && !Number.isNaN(val)) {
      return val;
    }
  }
  return null;
}

// ─── Table row extraction helpers ──────────────────────────────────────────

/** A flat row for the Table tab – keys are column names, values are primitives. */
export type TableRow = Record<string, string | number | boolean | null>;

function toRows(arr: unknown): TableRow[] | null {
  if (!Array.isArray(arr)) return null;
  const rows: TableRow[] = arr
    .filter((item) => item !== null && typeof item === "object" && !Array.isArray(item))
    .map((item) => flattenObject(item as Record<string, unknown>));
  return rows.length > 0 ? rows : null;
}

function extractSnapshotRows(snap: unknown): TableRow[] | null {
  if (!snap || typeof snap !== "object") return null;
  if (Array.isArray(snap)) return toRows(snap);
  const snapRecord = snap as Record<string, unknown>;
  return toRows(snapRecord.buses) ?? toRows(snapRecord.branches);
}

function extractScalarRow(summary: Record<string, unknown>): TableRow {
  const scalarRow: TableRow = {};
  for (const [k, v] of Object.entries(summary)) {
    if (v === null || typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
      scalarRow[k] = isSecretKey(k) ? "[REDACTED]" : v;
    }
  }
  return scalarRow;
}

function buildResult(rows: TableRow[]): { rows: TableRow[]; columns: string[] } {
  const columnSet = new Set<string>();
  for (const row of rows) {
    for (const k of Object.keys(row)) {
      columnSet.add(k);
    }
  }
  return { rows, columns: Array.from(columnSet) };
}

/**
 * Attempt to extract tabular rows from a result summary.
 *
 * Strategy (in priority order — never invents data):
 * 1. summary.results (array of objects)
 * 2. summary.network_snapshot.buses or branches
 * 3. summary.network_snapshot (if array)
 * 4. Flatten scalar top-level summary keys into a single row.
 */
export function extractTableData(summary: Record<string, unknown> | null | undefined): {
  rows: TableRow[];
  columns: string[];
} {
  if (!summary) return { rows: [], columns: [] };

  const fromResults = toRows(summary.results);
  if (fromResults) return buildResult(fromResults);

  const fromSnap = extractSnapshotRows(summary.network_snapshot);
  if (fromSnap) return buildResult(fromSnap);

  const scalarRow = extractScalarRow(summary);
  if (Object.keys(scalarRow).length > 0) return buildResult([scalarRow]);

  return { rows: [], columns: [] };
}

/** Flatten one level deep (nested objects become "parent.child" keys). */
function flattenObject(obj: Record<string, unknown>, prefix = ""): TableRow {
  const result: TableRow = {};
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (isSecretKey(k)) {
      result[key] = "[REDACTED]";
    } else if (v !== null && typeof v === "object" && !Array.isArray(v)) {
      Object.assign(result, flattenObject(v as Record<string, unknown>, key));
    } else if (
      typeof v === "string" ||
      typeof v === "number" ||
      typeof v === "boolean" ||
      v === null
    ) {
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

const BUS_KEYS = ["bus", "name", "id"] as const;
const VOLTAGE_KEYS = ["voltage_pu", "v_pu", "voltage"] as const;
const BRANCH_KEYS = ["branch", "name", "id"] as const;
const LOADING_KEYS = ["loading_pct", "loading", "utilization_pct"] as const;

function parseVoltagePoint(item: unknown): VoltagePoint | null {
  if (!item || typeof item !== "object" || Array.isArray(item)) return null;
  const r = item as Record<string, unknown>;
  const bus = getFieldString(r, BUS_KEYS);
  const v = getFieldNumber(r, VOLTAGE_KEYS);
  if (bus !== null && v !== null) {
    return { bus, voltage_pu: v };
  }
  return null;
}

function extractVoltageFromArray(arr: unknown): VoltagePoint[] {
  if (!Array.isArray(arr)) return [];
  const points: VoltagePoint[] = [];
  for (const item of arr) {
    const pt = parseVoltagePoint(item);
    if (pt) points.push(pt);
  }
  return points;
}

/**
 * Extract voltage profile data from summary.
 * Reads `results` array or `network_snapshot.buses` — never invents values.
 */
export function extractVoltageProfile(
  summary: Record<string, unknown> | null | undefined,
): VoltagePoint[] {
  if (!summary) return [];

  const fromResults = extractVoltageFromArray(summary.results);
  if (fromResults.length > 0) return fromResults;

  const snap = summary.network_snapshot;
  if (snap && typeof snap === "object" && !Array.isArray(snap)) {
    return extractVoltageFromArray((snap as Record<string, unknown>).buses);
  }
  return [];
}

function parseLoadingPoint(item: unknown): LoadingPoint | null {
  if (!item || typeof item !== "object" || Array.isArray(item)) return null;
  const r = item as Record<string, unknown>;
  const branch = getFieldString(r, BRANCH_KEYS);
  const pct = getFieldNumber(r, LOADING_KEYS);
  if (branch !== null && pct !== null) {
    return { branch, loading_pct: pct };
  }
  return null;
}

function extractLoadingFromArray(arr: unknown): LoadingPoint[] {
  if (!Array.isArray(arr)) return [];
  const points: LoadingPoint[] = [];
  for (const item of arr) {
    const pt = parseLoadingPoint(item);
    if (pt) points.push(pt);
  }
  return points;
}

/**
 * Extract branch loading data from summary.
 */
export function extractLoadingProfile(
  summary: Record<string, unknown> | null | undefined,
): LoadingPoint[] {
  if (!summary) return [];

  const fromResults = extractLoadingFromArray(summary.results);
  if (fromResults.length > 0) return fromResults;

  const snap = summary.network_snapshot;
  if (snap && typeof snap === "object" && !Array.isArray(snap)) {
    return extractLoadingFromArray((snap as Record<string, unknown>).branches);
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

const ID_NAME_KEYS = ["id", "name"] as const;
const NAME_ID_KEYS = ["name", "id"] as const;
const FROM_KEYS = ["from_bus", "from"] as const;
const TO_KEYS = ["to_bus", "to"] as const;

function parseDiagramNodes(buses: unknown): DiagramNode[] {
  if (!Array.isArray(buses)) return [];
  const nodes: DiagramNode[] = [];
  for (const bus of buses) {
    if (!bus || typeof bus !== "object" || Array.isArray(bus)) continue;
    const r = bus as Record<string, unknown>;
    const id = getFieldString(r, ID_NAME_KEYS);
    if (!id) continue;
    const label = getFieldString(r, NAME_ID_KEYS) ?? id;
    const v = getFieldNumber(r, ["voltage_pu"]);
    nodes.push({
      id,
      type: "bus",
      label,
      voltage_pu: v ?? undefined,
    });
  }
  return nodes;
}

function parseDiagramEdges(branches: unknown): DiagramEdge[] {
  if (!Array.isArray(branches)) return [];
  const edges: DiagramEdge[] = [];
  for (const br of branches) {
    if (!br || typeof br !== "object" || Array.isArray(br)) continue;
    const r = br as Record<string, unknown>;
    const from = getFieldString(r, FROM_KEYS);
    const to = getFieldString(r, TO_KEYS);
    if (!from || !to) continue;
    const id = getFieldString(r, ID_NAME_KEYS) ?? `${from}-${to}`;
    const label = getFieldString(r, NAME_ID_KEYS) ?? undefined;
    edges.push({ id, from, to, label });
  }
  return edges;
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
  return {
    nodes: parseDiagramNodes(snapRecord.buses),
    edges: parseDiagramEdges(snapRecord.branches),
  };
}
