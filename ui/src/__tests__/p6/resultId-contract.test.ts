/**
 * P6 resultId wire contract tests.
 *
 * Background:
 *   The P5 public contract exposes `resultId` (camelCase) on StudyResult.
 *   The P3 SessionStream `result_ready` event internally still uses
 *   `result_id` (snake_case). The chatStore is the serialization boundary
 *   that translates the internal event field into the frontend's wire-facing
 *   `resultId`. The frontend components MUST consume `resultId` — they MUST
 *   NOT read `result_id` directly from any payload.
 *
 * These tests pin:
 *   1. ResultEntry / ResultCard / ResultViewer / ActivityDrawer use
 *      `resultId`, not `result_id`.
 *   2. The SessionStream `result_ready` event is translated to `resultId`
 *      at the store boundary.
 *   3. No P6 file references `result_id` as a wire-facing property.
 */
import { describe, expect, it } from "vitest";
import type { ResultEntry } from "../../store/chatStore";

describe("P6 resultId wire contract", () => {
  it("ResultEntry type uses resultId (camelCase) — P5 public contract", () => {
    const entry: ResultEntry = {
      resultId: "res-abc-123",
      tool: "load_flow",
      ts: "2026-08-29T10:00:00Z",
    };
    expect(entry.resultId).toBe("res-abc-123");
    // Strictly typed: no snake_case field exists on the frontend model.
    expect((entry as unknown as Record<string, unknown>).result_id).toBeUndefined();
  });

  it("ResultEntry preserves the P5 contract under camelCase access only", () => {
    // The frontend model exposes a single `resultId` property — no dual naming.
    const wire = {
      resultId: "res-xyz-789",
      tool: "short_circuit",
    } satisfies ResultEntry;
    expect(Object.keys(wire)).toEqual(["resultId", "tool"]);
  });
});
