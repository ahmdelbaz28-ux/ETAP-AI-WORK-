/**
 * AskAiButton.tsx - Floating "Ask AI" button.
 *
 * V216: Restored EXACT V223 design — flat blue, no borders, no shadow glow,
 * clean engineering style. No kbd hint, no RTL branching, no frosted effects.
 * The V215 additions (kbd hint, RTL, frosted effects, ambient blob) were
 * well-intentioned but deviated from the V223 engineering identity.
 * This version matches V223 exactly.
 *
 * The keyboard shortcut Ctrl+J (Windows/Linux) and Cmd+J (macOS) is still
 * handled in App.tsx — the hint chip was removed because V223 didn't have it.
 */
import { useTranslation } from "react-i18next";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface AskAiButtonProps {
        readonly onClick: () => void;
        readonly label?: string;
}

export function AskAiButton({ onClick, label }: AskAiButtonProps) {
        const { t } = useTranslation();

        return (
                <Button
                        onClick={onClick}
                        className="fixed bottom-6 right-6 z-50 h-10 px-4 rounded-md bg-primary hover:bg-primary/90 text-primary-foreground transition-colors gap-1.5 font-medium"
                        title={t("ai.title", "Ask AI Copilot")}
                >
                        <Sparkles className="w-4 h-4" />
                        <span className="hidden sm:inline">
                                {label || t("ai.askButton", "Ask AI")}
                        </span>
                </Button>
        );
}
