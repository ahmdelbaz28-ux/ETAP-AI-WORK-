/**
 * AskAiButton.tsx — Floating "Ask AI" button.
 *
 * V216 (V223 design restoration): Restored the original flat blue engineering
 * style from V223. Removed the glassmorphism / floating animation / gradient
 * blob that were added in V215 — they conflicted with the V223 engineering
 * identity (slate-900 navy + #2f81f7 calm blue + flat surfaces).
 *
 * Style: bg-primary (blue) + no shadow + rounded-md + no scale + h-10
 * Position: fixed bottom-right, appears on all protected routes
 *
 * Accessibility:
 *   - aria-label + title for screen readers
 *   - focus-visible ring for keyboard users
 *   - keyboard shortcut Ctrl+J (Windows/Linux) or Cmd+J (macOS)
 *
 * The button is rendered globally in App.tsx so it shows on EVERY
 * protected page — no per-page wiring needed.
 */
import { useTranslation } from "react-i18next";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface AskAiButtonProps {
        readonly onClick: () => void;
        readonly label?: string;
}

export function AskAiButton({ onClick, label }: AskAiButtonProps) {
        const { t, i18n } = useTranslation();
        const buttonText = label || t("ai.askButton", "Ask AI");
        const ariaLabel = t("ai.title", "Ask AI Copilot");
        // V215 fix (kept): In RTL layouts (Arabic), the button should anchor
        // to the left edge so it doesn't overlap the sidebar.
        const isRTL = i18n.language === "ar" || i18n.dir() === "rtl";
        const positionClass = isRTL ? "left-4" : "right-4";
        // V215 fix (kept): Show platform-appropriate keyboard shortcut hint.
        const isMac =
                typeof navigator !== "undefined" &&
                (navigator.platform.toLowerCase().includes("mac") ||
                        navigator.userAgent.toLowerCase().includes("mac"));
        const shortcutHint = isMac ? "⌘J" : "Ctrl+J";

        return (
                <Button
                        onClick={onClick}
                        aria-label={ariaLabel}
                        title={ariaLabel}
                        className={`fixed bottom-4 ${positionClass} z-50 h-10 px-4 gap-1.5 font-medium`}
                >
                        <Sparkles className="h-4 w-4" />
                        <span className="hidden sm:inline">{buttonText}</span>
                        <kbd
                                className="ml-1 hidden md:inline-flex items-center rounded border border-primary-foreground/20 bg-primary-foreground/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-primary-foreground/80"
                                aria-hidden="true"
                        >
                                {shortcutHint}
                        </kbd>
                </Button>
        );
}
