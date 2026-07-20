/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from "vitest";
import arData from "../locales/ar.json";
import enData from "../locales/en.json";

// ── Helpers ────────────────────────────────────────────────────────────────────

/**
 * Recursively collect all leaf-key paths from a nested object.
 * e.g. { app: { name: "...", version: "..." } } → ["app.name", "app.version"]
 */
function collectKeyPaths(obj: Record<string, unknown>, prefix = ""): string[] {
  const paths: string[] = [];
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      paths.push(...collectKeyPaths(value as Record<string, unknown>, fullKey));
    } else {
      paths.push(fullKey);
    }
  }
  return paths;
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe("i18n translations", () => {
  it("has valid English translation data", () => {
    expect(enData).toBeDefined();
    expect(typeof enData).toBe("object");
    expect(enData.app).toBeDefined();
    expect(enData.app.name).toBe("Ahmed etap");
  });

  it("has valid Arabic translation data", () => {
    expect(arData).toBeDefined();
    expect(typeof arData).toBe("object");
    expect(arData.app).toBeDefined();
    expect(arData.app.name).toBe("Ahmed etap");
  });

  it("has the same top-level keys in both locales", () => {
    const enKeys = Object.keys(enData).sort();
    const arKeys = Object.keys(arData).sort();
    expect(arKeys).toEqual(enKeys);
  });

  it("has the same leaf-level keys in both locales", () => {
    const enPaths = new Set(collectKeyPaths(enData as Record<string, unknown>));
    const arPaths = new Set(collectKeyPaths(arData as Record<string, unknown>));

    const missingInAr = [...enPaths].filter((p) => !arPaths.has(p));
    const missingInEn = [...arPaths].filter((p) => !enPaths.has(p));

    expect(missingInAr).toEqual([]);
    expect(missingInEn).toEqual([]);
  });

  it("contains Arabic text (RTL language) in the Arabic locale", () => {
    const arValues = Object.values(arData.sidebar || {}).join(" ");
    const hasArabicChars = /[\u0600-\u06FF]/.test(arValues);
    expect(hasArabicChars).toBe(true);
  });

  it("English locale uses LTR-appropriate text", () => {
    const enValues = Object.values(enData.sidebar || {}).join(" ");
    const hasArabicChars = /[\u0600-\u06FF]/.test(enValues);
    expect(hasArabicChars).toBe(false);
  });

  it("has critical navigation keys in both locales", () => {
    const requiredSidebarKeys = [
      "dashboard",
      "studies",
      "assistant",
      "settings",
      "administration",
      "diagnostics",
    ];
    for (const key of requiredSidebarKeys) {
      expect(enData.sidebar[key as keyof typeof enData.sidebar]).toBeDefined();
      expect(arData.sidebar[key as keyof typeof arData.sidebar]).toBeDefined();
    }
  });

  it("has study type keys in both locales", () => {
    const studyTypeKeys = [
      "load_flow",
      "short_circuit",
      "arc_flash",
      "harmonic_analysis",
      "protection_coordination",
      "motor_starting",
      "transient_stability",
    ];
    for (const key of studyTypeKeys) {
      expect(enData.studyTypes[key as keyof typeof enData.studyTypes]).toBeDefined();
      expect(arData.studyTypes[key as keyof typeof arData.studyTypes]).toBeDefined();
    }
  });

  it("has status keys in both locales", () => {
    const statusKeys = ["pending", "running", "completed", "failed", "cancelled"];
    for (const key of statusKeys) {
      expect(enData.statuses[key as keyof typeof enData.statuses]).toBeDefined();
      expect(arData.statuses[key as keyof typeof arData.statuses]).toBeDefined();
    }
  });

  it("has common action keys in both locales", () => {
    const commonKeys = ["loading", "error", "retry", "cancel", "save", "delete", "search"];
    for (const key of commonKeys) {
      expect(enData.common[key as keyof typeof enData.common]).toBeDefined();
      expect(arData.common[key as keyof typeof arData.common]).toBeDefined();
    }
  });

  it("Arabic dashboard translations are correct", () => {
    expect(arData.dashboard.title).toBe("لوحة التحكم");
    expect(arData.dashboard.online).toBe("متصل");
    expect(arData.dashboard.offline).toBe("غير متصل");
  });

  it("English dashboard translations are correct", () => {
    expect(enData.dashboard.title).toBe("Dashboard");
    expect(enData.dashboard.online).toBe("Online");
    expect(enData.dashboard.offline).toBe("Offline");
  });
});
