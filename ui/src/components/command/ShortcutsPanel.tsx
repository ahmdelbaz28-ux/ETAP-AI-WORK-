import { AnimatePresence, motion } from "framer-motion";
import { Command, CornerDownLeft, Eye, HelpCircle, Navigation, Plus, X, Zap } from "lucide-react";
import { SHORTCUT_DEFINITIONS, type ShortcutCategory } from "../../hooks/useKeyboardShortcuts";
import { cn } from "../../utils/helpers";

interface ShortcutsPanelProps {
  open: boolean;
  onClose: () => void;
}

const CATEGORY_CONFIG: Record<
  ShortcutCategory,
  { icon: React.ElementType; label: string; color: string }
> = {
  navigation: { icon: Navigation, label: "Navigation", color: "text-blue-400" },
  actions: { icon: Zap, label: "Actions", color: "text-amber-400" },
  help: { icon: HelpCircle, label: "Help", color: "text-brand-400" },
  view: { icon: Eye, label: "View", color: "text-green-400" },
};

// Keyboard key component — renders a styled key cap
function KeyCap({ children }: { children: React.ReactNode }) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  return (
    <kbd
      className={cn(
        "inline-flex items-center justify-center min-w-[28px] h-7 px-2",
        "bg-[var(--bg-elevated)] border border-[var(--border-secondary)]",
        "rounded-md text-xs font-mono font-medium text-[var(--text-secondary)]",
        "shadow-[0_2px_0_0_var(--border-primary)]",
        "transition-all",
      )}
    >
      {children}
    </kbd>
  );
}

// Render a sequence of keys (e.g. ["Ctrl", "K"] or ["G", "D"])
function KeySequence({ keys }: { keys: readonly string[] }) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  return (
    <div className="flex items-center gap-1">
      {keys.map((key, i) => (
        <span key={`${key}-${i}`} className="flex items-center gap-1">
          <KeyCap>{key}</KeyCap>
          {i < keys.length - 1 && (
            <span className="text-[var(--text-muted)] text-xs">{keys[i] === "G" ? "→" : "+"}</span>
          )}
        </span>
      ))}
    </div>
  );
}

export function ShortcutsPanel({ open, onClose }: ShortcutsPanelProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  // Group shortcuts by category
  const categories = Array.from(
    new Set(SHORTCUT_DEFINITIONS.map((s) => s.category)),
  ) as ShortcutCategory[];

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[200] bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Panel */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="fixed top-[10vh] left-1/2 -translate-x-1/2 z-[201] w-full max-w-2xl mx-4"
          >
            <div className="bg-[var(--bg-secondary)] border border-[var(--border-secondary)] rounded-2xl shadow-2xl shadow-black/40 overflow-hidden">
              {/* Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-primary)] bg-gradient-to-r from-brand-500/5 to-transparent">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center">
                    <Command className="w-5 h-5 text-brand-400" />
                  </div>
                  <div>
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">
                      Keyboard Shortcuts
                    </h2>
                    <p className="text-xs text-[var(--text-muted)]">
                      Press{" "}
                      <kbd className="px-1 py-0.5 rounded bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-[10px] font-mono">
                        Ctrl
                      </kbd>
                      {" + "}
                      <kbd className="px-1 py-0.5 rounded bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-[10px] font-mono">
                        /
                      </kbd>{" "}
                      anytime to toggle this panel
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  className="p-2 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Shortcuts grid */}
              <div className="max-h-[60vh] overflow-y-auto p-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-6">
                  {categories.map((cat) => {
                    const config = CATEGORY_CONFIG[cat];
                    const catShortcuts = SHORTCUT_DEFINITIONS.filter((s) => s.category === cat);
                    return (
                      <div key={cat}>
                        {/* Category header */}
                        <div className="flex items-center gap-2 mb-3">
                          <config.icon className={cn("w-4 h-4", config.color)} />
                          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                            {config.label}
                          </span>
                          <div className="flex-1 h-px bg-[var(--border-primary)]" />
                        </div>

                        {/* Shortcuts list */}
                        <div className="space-y-2">
                          {catShortcuts.map((shortcut, i) => (
                            <div
                              key={i} // NOSONAR — S6479: array index as key; items lack stable IDs (tech debt)
                              className="flex items-center justify-between gap-3 py-1.5 px-2 rounded-lg hover:bg-[var(--bg-elevated)] transition-colors group"
                            >
                              <span className="text-xs text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors">
                                {shortcut.description}
                              </span>
                              <KeySequence keys={shortcut.keys} />
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between px-6 py-3 border-t border-[var(--border-primary)] bg-[var(--bg-primary)]/50">
                <div className="flex items-center gap-2 text-[10px] text-[var(--text-muted)]">
                  <Plus className="w-3 h-3" />
                  <span>Navigation shortcuts use a two-key sequence: press</span>
                  <KeyCap>G</KeyCap>
                  <span>then the destination key</span>
                </div>
                <div className="flex items-center gap-1 text-[10px] text-[var(--text-muted)]">
                  <CornerDownLeft className="w-3 h-3" />
                  <span>Press Esc to close</span>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
