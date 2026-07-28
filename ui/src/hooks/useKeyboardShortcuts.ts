// UI components are intentionally complex for feature-rich DX
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

// ============================================================================
// Keyboard Shortcuts System
// ============================================================================
// Centralized keyboard shortcut handler for the entire application.
// All shortcuts are defined here and activated globally.
// ============================================================================

export interface ShortcutDef {
  keys: string; // e.g. 'ctrl+k', 'f1', 'shift+/'
  action: () => void;
  description: string;
  category: "navigation" | "actions" | "help" | "view";
  global?: boolean; // true = works even when typing in inputs
}

// G-then-letter navigation routes (extracted to keep handleKeyDown simple).
const G_SEQUENCE_ROUTES: Record<string, string> = {
  d: "/dashboard",
  p: "/projects",
  s: "/studies",
  a: "/assistant",
  r: "/reports",
  e: "/settings",
  t: "/digital-twin",
  i: "/diagnostics",
  l: "/logs",
};

// Build the lowercased key-combo string from a KeyboardEvent (e.g. "ctrl+k").
function buildCombo(e: KeyboardEvent): string {
  const parts: string[] = [];
  if (e.ctrlKey || e.metaKey) parts.push("ctrl");
  if (e.shiftKey) parts.push("shift");
  if (e.altKey) parts.push("alt");
  let key = e.key.toLowerCase();
  if (key === " ") key = "space";
  parts.push(key);
  return parts.join("+");
}

// Returns true if the event target is an input/textarea/contenteditable element.
function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable;
}

// Begin the G-then-letter navigation sequence: dispatch the marker event and
// listen for the next key (within 1.5s) to route to the matching page.
function beginGSequence(navigate: (path: string) => void): void {
  globalThis.dispatchEvent(new CustomEvent("shortcut-g-sequence"));
  const sequenceHandler = (ev: KeyboardEvent) => {
    const seqKey = ev.key.toLowerCase();
    const route = G_SEQUENCE_ROUTES[seqKey];
    if (route) {
      ev.preventDefault();
      navigate(route);
    }
    globalThis.removeEventListener("keydown", sequenceHandler);
  };
  setTimeout(() => globalThis.removeEventListener("keydown", sequenceHandler), 1500);
  globalThis.addEventListener("keydown", sequenceHandler, { once: true });
}

export function useKeyboardShortcuts() {
  const navigate = useNavigate();
  const [shortcutsPanelOpen, setShortcutsPanelOpen] = useState(false);

  const openShortcutsPanel = useCallback(() => setShortcutsPanelOpen(true), []);
  const closeShortcutsPanel = useCallback(() => setShortcutsPanelOpen(false), []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if the user is typing in an input/textarea AND the
      // shortcut isn't explicitly global. Exception: Ctrl/Cmd combos and F-keys
      // always work (they don't conflict with normal typing).
      const isTyping = isTypingTarget(e.target);
      const isModKey = e.ctrlKey || e.metaKey;
      const isFunctionKey = e.key.startsWith("F");

      if (isTyping && !isModKey && !isFunctionKey) return;

      const combo = buildCombo(e);

      // ─── Navigation Shortcuts (G then letter) ───────────────────────
      if (combo === "g" && !isTyping) {
        e.preventDefault();
        beginGSequence(navigate);
        return;
      }

      // ─── Direct Shortcuts ───────────────────────────────────────────
      switch (combo) {
        // Command palette - handled by CommandPalette's own listener
        case "ctrl+k":
          // Do nothing here — CommandPalette.tsx has its own Ctrl+K listener
          // that toggles its open state. Dispatching a synthetic keydown here
          // would cause an infinite loop (stack overflow).
          break;

        // Help
        // SonarCloud typescript:S1871: 'f1' and 'ctrl+h' share the same
        // body — fall through intentionally.
        case "f1":
        case "ctrl+h":
          e.preventDefault();
          globalThis.dispatchEvent(new CustomEvent("toggle-smart-help"));
          break;

        // Magic Help Inspector
        case "ctrl+shift+h":
          e.preventDefault();
          globalThis.dispatchEvent(new CustomEvent("start-magic-help-inspect"));
          break;

        // Shortcuts panel
        case "ctrl+/":
          e.preventDefault();
          setShortcutsPanelOpen((prev) => !prev);
          break;
        case "shift+/": // ? on most keyboards
          if (!isTyping) {
            e.preventDefault();
            setShortcutsPanelOpen((prev) => !prev);
          }
          break;

        // New study / new project
        case "ctrl+n":
          e.preventDefault();
          navigate("/studies");
          break;

        // Save (dispatches a global event that pages can listen for)
        case "ctrl+s":
          e.preventDefault();
          globalThis.dispatchEvent(new CustomEvent("shortcut-save"));
          break;

        // Export
        case "ctrl+e":
          e.preventDefault();
          globalThis.dispatchEvent(new CustomEvent("shortcut-export"));
          break;

        // Close any open modal/drawer
        case "escape":
          // Only dispatch if not already handled by a modal
          if (!isTyping) {
            globalThis.dispatchEvent(new CustomEvent("shortcut-escape"));
          }
          break;

        // Toggle fullscreen
        case "f11":
          e.preventDefault();
          if (document.fullscreenElement) {
            document.exitFullscreen();
          } else {
            document.documentElement.requestFullscreen();
          }
          break;

        // Toggle theme (Ctrl+Shift+L)
        case "ctrl+shift+l":
          e.preventDefault();
          globalThis.dispatchEvent(new CustomEvent("toggle-theme"));
          break;

        // Toggle language (Ctrl+Shift+G)
        case "ctrl+shift+g":
          e.preventDefault();
          globalThis.dispatchEvent(new CustomEvent("toggle-language"));
          break;
      }
    };

    globalThis.addEventListener("keydown", handleKeyDown);
    return () => globalThis.removeEventListener("keydown", handleKeyDown);
  }, [navigate]);

  return { shortcutsPanelOpen, openShortcutsPanel, closeShortcutsPanel };
}

// ============================================================================
// Shortcut definitions for display in the ShortcutsPanel
// ============================================================================
export const SHORTCUT_DEFINITIONS = [
  // Navigation
  { keys: ["G", "D"], description: "Go to Dashboard", category: "navigation" },
  { keys: ["G", "P"], description: "Go to Projects", category: "navigation" },
  { keys: ["G", "S"], description: "Go to Studies", category: "navigation" },
  { keys: ["G", "A"], description: "Go to AI Assistant", category: "navigation" },
  { keys: ["G", "R"], description: "Go to Reports", category: "navigation" },
  { keys: ["G", "E"], description: "Go to Settings", category: "navigation" },
  { keys: ["G", "T"], description: "Go to Digital Twin", category: "navigation" },
  { keys: ["G", "I"], description: "Go to Diagnostics", category: "navigation" },
  { keys: ["G", "L"], description: "Go to Logs", category: "navigation" },

  // Actions
  { keys: ["Ctrl", "K"], description: "Open Command Palette", category: "actions" },
  { keys: ["Ctrl", "N"], description: "New Study", category: "actions" },
  { keys: ["Ctrl", "S"], description: "Save Current Work", category: "actions" },
  { keys: ["Ctrl", "E"], description: "Export Data", category: "actions" },
  { keys: ["Esc"], description: "Close Modal / Drawer", category: "actions" },

  // Help
  { keys: ["F1"], description: "Open Smart Help", category: "help" },
  { keys: ["Ctrl", "H"], description: "Toggle Help Panel", category: "help" },
  { keys: ["Ctrl", "Shift", "H"], description: "Magic Help Inspector", category: "help" },
  { keys: ["Ctrl", "/"], description: "Show Keyboard Shortcuts", category: "help" },
  { keys: ["?"], description: "Show Keyboard Shortcuts", category: "help" },

  // View
  { keys: ["F11"], description: "Toggle Fullscreen", category: "view" },
  { keys: ["Ctrl", "Shift", "L"], description: "Toggle Theme", category: "view" },
  { keys: ["Ctrl", "Shift", "G"], description: "Toggle Language (EN/AR)", category: "view" },
] as const;

export type ShortcutCategory = "navigation" | "actions" | "help" | "view";
