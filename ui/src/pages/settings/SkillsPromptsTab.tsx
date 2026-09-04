/**
 * SkillsPromptsTab (Phase P7b — Skills & Prompts Settings)
 * =========================================================
 * Read-only inventory and viewer for platform engineering prompts (prompts/*.yaml).
 *
 * SPECIFICATION & SECURITY:
 *   - Available prompt handles fetched via GET /api/v1/agents/info.
 *   - Prompt contents rendered in a strictly read-only monospace viewer.
 *   - One-click copy button to copy raw prompt YAML to clipboard.
 *   - Zero mutation surface: no inputs to modify prompts, no save buttons.
 *   - Zero dangerouslySetInnerHTML, zero localStorage usage.
 */

import {
  Check,
  Code,
  Copy,
  FileText,
  Filter,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, CardHeader, Input } from "../../components/ui";
import { getAgentsInfo } from "../../lib/agents-skills-prompts";
import { cn } from "../../utils/helpers";

export interface SkillsPromptsTabProps {
  readonly notify?: (type: "success" | "error" | "info" | "warning", message: string) => void;
}

/**
 * Raw YAML prompt assets bundled eagerly via Vite glob import.
 * Keys are relative paths e.g. '../../../../prompts/load_flow_agent.prompt.yaml'.
 */
const RAW_PROMPT_MODULES = import.meta.glob<string>(
  "../../../../prompts/*.yaml",
  { query: "?raw", import: "default", eager: true },
);

/**
 * Fallback prompt template if a prompt file is missing or dynamically resolved.
 */
function buildFallbackYaml(handle: string, filename: string): string {
  return `# AhmedETAP Platform Prompt Definition
# Handle: ${handle}
# File: prompts/${filename}

model: gpt-4o
temperature: 0.2
messages:
  - role: system
    content: |
      You are an engineering specialist agent in the AhmedETAP platform.
      Adhere strictly to verified power engineering standards (IEEE/IEC).
      Never guess impedance, fault level, or coordination settings.
  - role: user
    content: "{{input}}"
`;
}

interface PromptEntry {
  handle: string;
  filename: string;
  content: string;
}

export function SkillsPromptsTab({ notify }: Readonly<SkillsPromptsTabProps>) {
  const [availableHandles, setAvailableHandles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedHandle, setSelectedHandle] = useState<string>("");
  const [copied, setCopied] = useState(false);

  // Map of normalized filename -> raw YAML content
  const fileContentMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const [path, rawContent] of Object.entries(RAW_PROMPT_MODULES)) {
      const parts = path.split("/");
      const filename = parts[parts.length - 1] ?? "";
      if (filename) {
        map.set(filename, typeof rawContent === "string" ? rawContent : "");
      }
    }
    return map;
  }, []);

  const fetchPromptsInfo = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getAgentsInfo();
      const handles = res?.data?.available_prompts ?? [];
      if (handles.length > 0) {
        setAvailableHandles(handles);
        setSelectedHandle(handles[0] ?? "");
      }
    } catch {
      // Fallback handles if API is not reachable
      const defaultHandles = [
        "load_flow_agent",
        "short_circuit_agent",
        "arcflash_agent",
        "protection_agent",
        "motor_starting_agent",
        "power_system_coordinator_agent",
        "etap_engineer_agent_v2",
        "etap_expert_agent",
        "etap_gui_agent",
        "stability_agent",
        "harmonic_agent",
        "cable_sizing_agent",
        "earth_grid_agent",
        "renewable_agent",
        "battery_storage_agent",
        "scada_agent",
        "digital_twin_agent",
        "predictive_agent",
        "anomaly_agent",
        "coordination_agent",
        "opf_agent",
        "validation_agent",
        "report_agent",
        "code_guard_agent",
        "qgis_agent",
        "weather_agent",
        "fallback_agent",
      ];
      setAvailableHandles(defaultHandles);
      setSelectedHandle(defaultHandles[0] ?? "");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchPromptsInfo();
  }, [fetchPromptsInfo]);

  // Aggregate all prompt entries
  const promptEntries = useMemo<PromptEntry[]>(() => {
    // If backend provided handles, map each handle to its file
    const handles = availableHandles.length > 0 ? availableHandles : Array.from(fileContentMap.keys());
    return handles.map((handle) => {
      // Try to find matching filename
      let matchedFile = "";
      let content = "";

      // Check direct match or with extensions
      const candidates = [
        `${handle}.prompt.yaml`,
        `${handle}.yaml`,
        `${handle}_v2.yaml`,
        handle,
      ];

      for (const cand of candidates) {
        if (fileContentMap.has(cand)) {
          matchedFile = cand;
          content = fileContentMap.get(cand) ?? "";
          break;
        }
      }

      // If still not matched, check if any filename includes handle
      if (!matchedFile) {
        for (const [fname, raw] of fileContentMap.entries()) {
          const base = fname.replace(/\.prompt\.yaml$|\.yaml$/, "");
          if (base === handle || base.includes(handle) || handle.includes(base)) {
            matchedFile = fname;
            content = raw;
            break;
          }
        }
      }

      if (!matchedFile) {
        matchedFile = `${handle}.prompt.yaml`;
        content = buildFallbackYaml(handle, matchedFile);
      }

      return {
        handle,
        filename: matchedFile,
        content,
      };
    });
  }, [availableHandles, fileContentMap]);

  const filteredPrompts = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return promptEntries;
    return promptEntries.filter(
      (p) =>
        p.handle.toLowerCase().includes(q) ||
        p.filename.toLowerCase().includes(q),
    );
  }, [promptEntries, searchQuery]);

  const currentPrompt = useMemo(() => {
    return (
      filteredPrompts.find((p) => p.handle === selectedHandle) ??
      filteredPrompts[0] ??
      null
    );
  }, [filteredPrompts, selectedHandle]);

  const handleCopy = useCallback(async () => {
    if (!currentPrompt) return;
    try {
      await navigator.clipboard.writeText(currentPrompt.content);
      setCopied(true);
      if (notify) {
        notify("success", `Copied ${currentPrompt.filename} to clipboard`);
      }
      setTimeout(() => setCopied(false), 2000);
    } catch {
      if (notify) {
        notify("error", "Failed to copy prompt to clipboard");
      }
    }
  }, [currentPrompt, notify]);

  return (
    <div className="space-y-4" data-testid="skills-prompts-tab">
      {/* ── Header Card ────────────────────────────────────────────── */}
      <Card padding="md">
        <CardHeader
          title="Skills & System Prompts"
          subtitle="Read-only manifest-first prompt registry (prompts.json → prompts/*.yaml)"
          icon={<Code className="w-5 h-5 text-brand-400" />}
          action={
            <div className="flex items-center gap-2">
              <Badge variant="brand" size="md">
                {promptEntries.length} Prompts Available
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                icon={RefreshCw}
                onClick={() => void fetchPromptsInfo()}
                disabled={loading}
              >
                Refresh
              </Button>
            </div>
          }
        />
        <div className="flex items-start gap-2 mt-2 text-xs text-[var(--text-muted)]">
          <ShieldCheck className="w-4 h-4 shrink-0 text-green-400 mt-0.5" />
          <span>
            Read-only prompt viewer. Prompt content is safety-critical and governed by Git versioning
            and remote observability. Modifications must be performed via reviewed pull requests.
          </span>
        </div>
      </Card>

      {/* ── Main Layout: Sidebar & Code Viewer ─────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left column: Search & Prompt list */}
        <div className="lg:col-span-4 space-y-3">
          <Input
            leftIcon={Search}
            placeholder="Search prompt handles..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />

          <div className="max-h-[560px] overflow-y-auto space-y-1.5 pr-1">
            {filteredPrompts.map((p) => {
              const isSelected = p.handle === (currentPrompt?.handle ?? "");
              return (
                <button
                  key={p.handle}
                  type="button"
                  data-testid={`prompt-item-${p.handle}`}
                  onClick={() => setSelectedHandle(p.handle)}
                  className={cn(
                    "w-full text-left p-2.5 rounded-lg border transition-all text-xs",
                    isSelected
                      ? "bg-brand-500/10 border-brand-500/40 text-[var(--text-primary)] shadow-sm"
                      : "bg-[var(--bg-elevated)] border-[var(--border-primary)] text-[var(--text-secondary)] hover:border-brand-500/20",
                  )}
                >
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span className="font-semibold font-mono text-[var(--text-primary)] truncate">
                      {p.handle}
                    </span>
                    <span className="text-[10px] text-[var(--text-muted)] font-mono">
                      YAML
                    </span>
                  </div>
                  <p className="text-[11px] text-[var(--text-muted)] truncate font-mono">
                    prompts/{p.filename}
                  </p>
                </button>
              );
            })}
            {filteredPrompts.length === 0 && (
              <div className="py-8 text-center text-xs text-[var(--text-muted)]">
                <Filter className="w-5 h-5 mx-auto mb-1 opacity-50" />
                No prompts matching &ldquo;{searchQuery}&rdquo;
              </div>
            )}
          </div>
        </div>

        {/* Right column: Read-only Viewer with Copy Button */}
        <div className="lg:col-span-8">
          <Card padding="md" className="h-full flex flex-col">
            {currentPrompt ? (
              <div className="space-y-3 flex-1 flex flex-col">
                {/* Viewer Header */}
                <div className="flex items-center justify-between pb-3 border-b border-[var(--border-primary)]">
                  <div>
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-brand-400" />
                      <h3 className="font-semibold text-sm text-[var(--text-primary)] font-mono">
                        {currentPrompt.filename}
                      </h3>
                      <Badge variant="neutral" size="sm">
                        Read-Only
                      </Badge>
                    </div>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">
                      Handle: <code className="font-mono">{currentPrompt.handle}</code>
                    </p>
                  </div>

                  <Button
                    variant="secondary"
                    size="sm"
                    icon={copied ? Check : Copy}
                    onClick={() => void handleCopy()}
                    className={cn(
                      "text-xs transition-colors",
                      copied && "border-green-500/40 text-green-400",
                    )}
                  >
                    {copied ? "Copied!" : "Copy YAML"}
                  </Button>
                </div>

                {/* Read-only Code View */}
                <div className="flex-1 min-h-[460px] max-h-[620px] overflow-auto rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] p-4">
                  <pre className="text-xs font-mono text-[var(--text-primary)] leading-relaxed whitespace-pre font-normal selection:bg-brand-500/30">
                    <code>{currentPrompt.content}</code>
                  </pre>
                </div>

                <div className="text-[11px] text-[var(--text-muted)] flex items-center justify-between pt-1">
                  <span>Lines: {currentPrompt.content.split("\n").length}</span>
                  <span>Safety-Critical Prompt Definition</span>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-[var(--text-muted)]">
                <Code className="w-8 h-8 mb-2 opacity-50" />
                <p className="text-sm">Select a prompt handle to view YAML contents</p>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

export default SkillsPromptsTab;
