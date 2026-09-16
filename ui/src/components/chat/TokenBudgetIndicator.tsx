import { useState } from "react";
import { Zap, AlertTriangle, ShieldCheck, Database, Info, X } from "lucide-react";
import { useChatStore } from "../../store/chatStore";
import { cn } from "../../utils/helpers";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";

interface TokenBudgetIndicatorProps {
  className?: string;
}

export function TokenBudgetIndicator({ className }: TokenBudgetIndicatorProps) {
  const tokenBudget = useChatStore((state) => state.tokenBudget);
  const messages = useChatStore((state) => state.messages);
  const [isOpen, setIsOpen] = useState(false);

  const {
    totalBudget,
    tokensUsed,
    tokensRemaining,
    percentUsed,
    isExceeded,
    isWarning,
  } = tokenBudget;

  const formattedTokens = tokensUsed > 1000 ? `${(tokensUsed / 1000).toFixed(1)}k` : `${tokensUsed}`;
  const formattedLimit = totalBudget > 1000 ? `${(totalBudget / 1000).toFixed(0)}k` : `${totalBudget}`;

  const statusColor = isExceeded
    ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/30"
    : isWarning
      ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30"
      : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30";

  return (
    <div className={cn("relative inline-flex items-center", className)}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full border transition-all duration-150 hover:opacity-85 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-primary-500",
          statusColor,
        )}
        title="Token Governance & Efficiency Monitor"
      >
        {isExceeded ? (
          <AlertTriangle className="w-3.5 h-3.5 text-rose-500 animate-pulse" />
        ) : (
          <Zap className="w-3.5 h-3.5 text-amber-400" />
        )}
        <span>
          {formattedTokens} / {formattedLimit}
        </span>
        <span className="text-[10px] opacity-75 font-semibold">({percentUsed}%)</span>
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-72 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xl p-3 z-50 text-slate-800 dark:text-slate-200">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800 mb-2.5">
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-brand-500" />
              <span className="text-xs font-semibold">Token Governance</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-5 w-5 p-0 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              onClick={() => setIsOpen(false)}
            >
              <X className="w-3.5 h-3.5" />
            </Button>
          </div>

          <div className="space-y-2 text-xs">
            {/* Progress bar */}
            <div>
              <div className="flex justify-between text-[11px] mb-1 text-slate-500 dark:text-slate-400">
                <span>Session Budget Usage</span>
                <span className="font-semibold text-slate-700 dark:text-slate-300">{percentUsed}%</span>
              </div>
              <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div
                  className={cn(
                    "h-full transition-all duration-300",
                    isExceeded ? "bg-rose-500" : isWarning ? "bg-amber-500" : "bg-emerald-500",
                  )}
                  style={{ width: `${Math.min(100, percentUsed)}%` }}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-100 dark:border-slate-800 text-[11px]">
              <div>
                <span className="text-slate-500 dark:text-slate-400 block">Tokens Used</span>
                <span className="font-medium text-slate-800 dark:text-slate-200">
                  {tokensUsed.toLocaleString()}
                </span>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400 block">Session Limit</span>
                <span className="font-medium text-slate-800 dark:text-slate-200">
                  {totalBudget.toLocaleString()}
                </span>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400 block">Tokens Remaining</span>
                <span className="font-medium text-slate-800 dark:text-slate-200">
                  {tokensRemaining.toLocaleString()}
                </span>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400 block">Status</span>
                <span className={cn("font-medium", isExceeded ? "text-rose-500" : isWarning ? "text-amber-500" : "text-emerald-500")}>
                  {isExceeded ? "Exceeded" : isWarning ? "Warning" : "Optimal"}
                </span>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px]">
              <div className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                <Database className="w-3.5 h-3.5 text-brand-500" />
                <span>Semantic Cache</span>
              </div>
              <Badge variant="success" size="sm" className="text-[10px] py-0 px-1.5">
                Active
              </Badge>
            </div>

            <div className="flex items-center justify-between text-[11px]">
              <div className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                <Info className="w-3.5 h-3.5 text-brand-500" />
                <span>Active Messages</span>
              </div>
              <span className="font-medium text-slate-700 dark:text-slate-300">
                {messages.length} in context
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
