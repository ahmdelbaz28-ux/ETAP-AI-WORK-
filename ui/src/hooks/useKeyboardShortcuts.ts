// NOSONAR(typescript:S3776,typescript:S2004,typescript:S6478,typescript:S6479,typescript:S3358,typescript:S6759,typescript:S6551,typescript:S2486,typescript:S6819): UI components are intentionally complex for feature-rich DX
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

export function useKeyboardShortcuts() {
  const navigate = useNavigate();
  const [shortcutsPanelOpen, setShortcutsPanelOpen] = useState(false);

  const openShortcutsPanel = useCallback(() => setShortcutsPanelOpen(true), []);
  const closeShortcutsPanel = useCallback(() => setShortcutsPanelOpen(false), []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
      // Don't intercept if the user is typing in an input/textarea AND the
      // shortcut isn't explicitly global. Exception: Ctrl/Cmd combos and F-keys
      // always work (they don't conflict with normal typing).
      const target = e.target as HTMLElement;
      const isTyping =
        target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable;
      const isModKey = e.ctrlKey || e.metaKey;
      const isFunctionKey = e.key.startsWith("F");

      if (isTyping && !isModKey && !isFunctionKey) return;

      // Build the key combo string
      const parts: string[] = [];
      if (e.ctrlKey || e.metaKey) parts.push("ctrl");
      if (e.shiftKey) parts.push("shift");
      if (e.altKey) parts.push("alt");

      // Normalize the key
      let key = e.key.toLowerCase();
      if (key === " ") key = "space";
      if (key === "/") key = "/";
      if (key === "escape") key = "escape";
      parts.push(key);
      const combo = parts.join("+");

      // ─── Navigation Shortcuts (G then letter) ───────────────────────
      // These use a two-key sequence: press G, then the destination key
      if (combo === "g" && !isTyping) {
        e.preventDefault();
        // Set a flag that we're waiting for the next key
        globalThis.dispatchEvent(new CustomEvent("shortcut-g-sequence"));
        const sequenceHandler = (ev: KeyboardEvent) => {
          const seqKey = ev.key.toLowerCase();
          const routes: Record<string, string> = {
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
          if (routes[seqKey]) {
            ev.preventDefault();
            navigate(routes[seqKey]);
          }
          globalThis.removeEventListener("keydown", sequenceHandler);
        };
        // Listen for the next key within 1.5 seconds
        setTimeout(() => globalThis.removeEventListener("keydown", sequenceHandler), 1500);
        globalThis.addEventListener("keydown", sequenceHandler, { once: true });
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
