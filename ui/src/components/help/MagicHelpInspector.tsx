import { Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { resolveContext } from "../../help/contextRegistry";

// --- Module-scope helpers (extracted from handleClick to keep S3776 cognitive complexity low) ---

const INTERACTIVE_SELECTOR =
  '[data-help-context], button, a, select, input, textarea, .card, [role="button"], h1, h2, h3, h4, li, label';

const OVERLAY_SELECTOR = String.raw`.fixed.z-\[100\], .magic-inspector-overlay, .magic-inspector-banner`;

// Bilingual text-content → contextId heuristics (order matters: more specific first).
const TEXT_CONTEXT_RULES: ReadonlyArray<{
  readonly contextId: string;
  readonly keywords: readonly string[];
}> = [
  { contextId: "dashboard.overview", keywords: ["dashboard", "لوحة التحكم", "التحكم"] },
  { contextId: "studies.load-flow", keywords: ["load flow", "تدفق الحمل"] },
  { contextId: "studies.short-circuit", keywords: ["short circuit", "دائرة قصيرة", "قصر"] },
  { contextId: "studies.arc-flash", keywords: ["arc flash", "شرارة", "قوس"] },
  { contextId: "studies.overview", keywords: ["studies", "دراسات"] },
  { contextId: "projects.create", keywords: ["project", "مشروع"] },
  { contextId: "reports.generate", keywords: ["report", "تقرير"] },
  { contextId: "digital-twin.overview", keywords: ["twin", "توأم"] },
  { contextId: "settings.backend", keywords: ["settings", "إعدادات"] },
  { contextId: "ai-assistant.overview", keywords: ["assistant", "مساعد", "ذكاء"] },
  { contextId: "asset-management.overview", keywords: ["asset", "أصول", "أصل"] },
  { contextId: "etap-integration.overview", keywords: ["etap", "إيتاب"] },
  { contextId: "gis-integration.overview", keywords: ["gis", "جغرافي"] },
  { contextId: "code-guard.overview", keywords: ["code", "كود", "حارس"] },
  { contextId: "administration.overview", keywords: ["admin", "إدارة", "مسؤول"] },
  { contextId: "diagnostics.overview", keywords: ["diagnostic", "تشخيص"] },
  { contextId: "logs.overview", keywords: ["logs", "سجلات"] },
  { contextId: "data-import.overview", keywords: ["import", "استيراد"] },
  { contextId: "data-export.overview", keywords: ["export", "تصدير"] },
  { contextId: "settings.external-services", keywords: ["test", "اختبار", "اتصال"] },
];

// URL-path → contextId heuristics (order matters: longer paths first to avoid false matches).
const PATH_CONTEXT_RULES: ReadonlyArray<{ readonly contextId: string; readonly path: string }> = [
  { contextId: "dashboard.overview", path: "dashboard" },
  { contextId: "projects.create", path: "projects" },
  { contextId: "studies.overview", path: "studies" },
  { contextId: "ai-assistant.overview", path: "assistant" },
  { contextId: "asset-management.overview", path: "asset" },
  { contextId: "etap-integration.overview", path: "etap" },
  { contextId: "gis-integration.overview", path: "gis" },
  { contextId: "reports.generate", path: "reports" },
  { contextId: "digital-twin.overview", path: "digital-twin" },
  { contextId: "settings.backend", path: "settings" },
  { contextId: "code-guard.overview", path: "code-guard" },
  { contextId: "data-import.overview", path: "data-import" },
  { contextId: "data-export.overview", path: "data-export" },
  { contextId: "administration.overview", path: "admin" },
  { contextId: "diagnostics.overview", path: "diagnostics" },
  { contextId: "logs.overview", path: "logs" },
];

function resolveContextFromText(text: string): string | null {
  const lowered = text.toLowerCase();
  for (const rule of TEXT_CONTEXT_RULES) {
    if (rule.keywords.some((kw) => lowered.includes(kw))) {
      return rule.contextId;
    }
  }
  return null;
}

function resolveContextFromPath(path: string): string {
  for (const rule of PATH_CONTEXT_RULES) {
    if (path.includes(rule.path)) {
      return rule.contextId;
    }
  }
  return "dashboard.overview";
}

function findContextFromAncestors(el: HTMLElement): string | null {
  let parent: HTMLElement | null = el.parentElement;
  let depth = 0;
  while (parent && depth < 5) {
    const attr = parent.dataset.helpContext;
    if (attr) return attr;
    parent = parent.parentElement;
    depth++;
  }
  return null;
}

function isInspectorOverlay(el: HTMLElement): boolean {
  return Boolean(el.closest(OVERLAY_SELECTOR));
}

/**
 * MagicHelpInspector
 *
 * When activated (via the ✨ Sparkles button in the navbar, or via the
 * "Magic Inspect" button inside the Smart Help drawer), the inspector:
 *
 * 1. Changes the cursor to a help cursor
 * 2. Highlights any interactive element under the mouse with a dashed cyan border
 * 3. Listens for a click — but in CAPTURE mode and with preventDefault so the
 *    underlying button/link does NOT fire its normal action
 * 4. Resolves the clicked element's `data-help-context` attribute (or falls
 *    back to text/path heuristics) to a topic ID
 * 5. Dispatches an `open-smart-help` CustomEvent with that contextId
 * 6. Deactivates itself
 *
 * The user can press Esc at any time to exit inspector mode without clicking.
 */
export function MagicHelpInspector() {
  const { i18n } = useTranslation();
  const lang = (i18n.language === "ar" ? "ar" : "en") as "en" | "ar";
  const [isActive, setIsActive] = useState(false);
  const [hoveredRect, setHoveredRect] = useState<DOMRect | null>(null);
  const [hoveredLabel, setHoveredLabel] = useState<string>("");

  useEffect(() => {
    const startInspect = () => {
      setIsActive(true);
      document.body.style.cursor = "help";
    };

    globalThis.addEventListener("start-magic-help-inspect", startInspect);
    return () => {
      globalThis.removeEventListener("start-magic-help-inspect", startInspect);
    };
  }, []);

  useEffect(() => {
    if (!isActive) return;

    const handleMouseMove = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target) return;

      // Find the closest interactive or semantic element. Prefer elements
      // with `data-help-context` attribute (these are guaranteed to have docs).
      const interactiveEl = target.closest(INTERACTIVE_SELECTOR) as HTMLElement | null;

      if (interactiveEl && !isInspectorOverlay(interactiveEl)) {
        setHoveredRect(interactiveEl.getBoundingClientRect());
        // Build a label for the floating tooltip
        const ctx = interactiveEl.dataset.helpContext ?? null;
        const text = (interactiveEl.textContent || "").trim().slice(0, 40);
        const tag = interactiveEl.tagName.toLowerCase();
        setHoveredLabel(ctx ? `📋 ${ctx}` : `🔍 <${tag}> "${text}"`);
      } else {
        setHoveredRect(null);
        setHoveredLabel("");
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        deactivate();
      }
    };

    const handleClick = (e: MouseEvent) => {
      // ALWAYS prevent the default action and stop propagation — we want
      // the click to be interpreted as "show me docs for this element",
      // not as a normal button press.
      e.preventDefault();
      e.stopPropagation();

      const target = e.target as HTMLElement;
      if (!target) {
        deactivate();
        return;
      }

      const interactiveEl = target.closest(INTERACTIVE_SELECTOR) as HTMLElement | null;

      // Resolve contextId through the four documented fallback layers:
      // 1. explicit data-help-context on the clicked element,
      // 2. ancestor data-help-context (walk up to 5 levels),
      // 3. text-content bilingual heuristics,
      // 4. URL-path heuristics (ultimate fallback to dashboard.overview).
      let contextId: string | null = null;
      if (interactiveEl) {
        contextId = interactiveEl.dataset.helpContext ?? null;
        if (!contextId) contextId = findContextFromAncestors(interactiveEl);
        if (!contextId) {
          contextId = resolveContextFromText(interactiveEl.textContent || "");
        }
      }
      if (!contextId) {
        const path = globalThis.location.hash || globalThis.location.pathname;
        contextId = resolveContextFromPath(path);
      }

      // Validate the contextId resolves to an actual topic in the registry.
      // (if not, the SmartHelpDrawer will show the dashboard default.)
      const resolvedTopicId = resolveContext(contextId);
      if (!resolvedTopicId) {
        // contextId is not in registry — log a warning so devs can fix it
        console.warn(
          `[MagicHelpInspector] contextId "${contextId}" is not in the contextRegistry. Falling back to dashboard.overview. Add an entry to contextRegistry.ts to fix.`,
        );
      }

      // Open the help drawer with this context.
      globalThis.dispatchEvent(
        new CustomEvent("open-smart-help", {
          detail: { contextId },
        }),
      );

      deactivate();
    };

    const deactivate = () => {
      setIsActive(false);
      setHoveredRect(null);
      setHoveredLabel("");
      document.body.style.cursor = "default";
    };

    globalThis.addEventListener("mousemove", handleMouseMove);
    // capture: true so we catch the event before any button's onClick fires
    globalThis.addEventListener("click", handleClick, true);
    globalThis.addEventListener("keydown", handleKeyDown);

    return () => {
      globalThis.removeEventListener("mousemove", handleMouseMove);
      globalThis.removeEventListener("click", handleClick, true);
      globalThis.removeEventListener("keydown", handleKeyDown);
      document.body.style.cursor = "default";
    };
  }, [isActive]);

  if (!isActive) return null;

  return (
    <>
      {/* Glow Highlight Box Overlay */}
      {hoveredRect && (
        <div
          className="magic-inspector-overlay fixed border-2 border-dashed border-[var(--accent-primary)] bg-[var(--accent-glow)] rounded-lg pointer-events-none transition-all duration-75 ease-out shadow-[0_0_15px_rgba(0,212,255,0.4)]"
          style={{
            top: hoveredRect.top - 2,
            left: hoveredRect.left - 2,
            width: hoveredRect.width + 4,
            height: hoveredRect.height + 4,
            zIndex: 99999,
          }}
        />
      )}

      {/* Floating tooltip next to the cursor showing what will be selected */}
      {hoveredRect && hoveredLabel && (
        <div
          className="magic-inspector-banner fixed px-2.5 py-1 rounded-md bg-[rgba(15,21,37,0.95)] border border-[var(--accent-primary)] text-[10px] text-[var(--text-primary)] font-mono pointer-events-none"
          style={{
            top: hoveredRect.bottom + 6,
            left: hoveredRect.left,
            zIndex: 99999,
            maxWidth: "300px",
          }}
        >
          {hoveredLabel}
        </div>
      )}

      {/* Floating Instructions Banner at Top */}
      <div
        className="magic-inspector-banner fixed top-6 left-1/2 -translate-x-1/2 px-5 py-3 rounded-full bg-[rgba(15,21,37,0.95)] border border-[var(--accent-primary)] shadow-2xl backdrop-blur-md flex items-center gap-3"
        style={{ zIndex: 100000 }}
      >
        <div className="w-6 h-6 rounded-full bg-brand-500/20 border border-brand-500/30 flex items-center justify-center animate-pulse">
          <Sparkles className="w-3.5 h-3.5 text-brand-400" />
        </div>
        <div className="text-xs font-medium text-[var(--text-primary)]">
          {lang === "ar" ? (
            <span>
              ✨ <strong>وضع فحص المساعدة نشط</strong> — اضغط على أي عنصر أو بطاقة في الصفحة لشرح
              كيفية عملها. اضغط <strong>ESC</strong> للخروج.
            </span>
          ) : (
            <span>
              ✨ <strong>Help Inspector Active</strong> — Click any element or card on the screen to
              see how it works. Press <strong>ESC</strong> to exit.
            </span>
          )}
        </div>
        <button
          onClick={() => setIsActive(false)}
          className="ml-2 p-1 rounded hover:bg-white/10 transition-colors"
          title={lang === "ar" ? "إغلاق" : "Close"}
          type="button"
        >
          <X className="w-3.5 h-3.5 text-[var(--text-muted)]" />
        </button>
      </div>
    </>
  );
}
