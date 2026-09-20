import { AlertCircle, Check, ChevronDown, FolderKanban, Loader2, RotateCcw, Search } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "../../lib/api";
import { useChatStore } from "../../store/chatStore";
import { cn } from "../../utils/helpers";

export interface ProjectItem {
  id: string;
  name: string;
  status: string;
  description?: string | null;
  updated_at?: string | null;
  tenant_id?: string | null;
}

export function ProjectSelector() {
  const projectId = useChatStore((s) => s.projectId);
  const setProjectId = useChatStore((s) => s.setProjectId);

  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await request<{ projects: ProjectItem[] }>("/api/v1/projects");
      const list = res?.projects || [];
      setProjects(list);

      // Auto-select first active project if none selected and valid projects exist
      const currentSelected = useChatStore.getState().projectId;
      if (!currentSelected && list.length > 0) {
        const firstActive = list.find((p) => p.status === "active") || list[0];
        setProjectId(firstActive.id);
      }
    } catch {
      // Fail-closed: Never fabricate projects. Report error to the user and prompt to retry.
      setProjects([]);
      setError("تعذر تحميل المشاريع — أعد المحاولة (Failed to load projects)");
    } finally {
      setLoading(false);
    }
  }, [setProjectId]);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  // Click outside to close
  useEffect(() => {
    if (!open) return;
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  const selectedProject = projects.find((p) => p.id === projectId) ?? null;

  const filtered = projects.filter((p) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q);
  });

  return (
    <div className="relative" ref={dropdownRef} data-testid="project-selector">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={cn(
          "flex items-center gap-2 px-2.5 py-1.5 rounded-lg border text-xs transition-all",
          "bg-[var(--bg-elevated)] border-[var(--border-primary)] text-[var(--text-primary)]",
          "hover:border-slate-500 hover:bg-[var(--bg-muted)] active:scale-[0.98]",
          open && "ring-1 ring-brand-500 border-brand-500",
        )}
        aria-haspopup="listbox"
        aria-expanded={open}
        data-testid="project-selector-trigger"
      >
        <div className="w-5 h-5 rounded bg-brand-500/10 border border-brand-500/20 text-brand-400 flex items-center justify-center shrink-0">
          <FolderKanban className="w-3.5 h-3.5" />
        </div>
        <div className="text-left max-w-[160px] truncate">
          <div className={cn("font-medium truncate leading-tight", error && "text-rose-400")}>
            {error ? "تعذر تحميل المشاريع" : selectedProject ? selectedProject.name : "Select Project"}
          </div>
          <div className="text-[10px] text-[var(--text-tertiary)] font-mono truncate leading-none mt-0.5">
            {error ? "Failed to load" : selectedProject ? selectedProject.id : "No project active"}
          </div>
        </div>
        {loading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--text-tertiary)] ml-1" />
        ) : (
          <ChevronDown
            className={cn(
              "w-3.5 h-3.5 text-[var(--text-tertiary)] transition-transform duration-200 ml-1",
              open && "rotate-180",
            )}
          />
        )}
      </button>

      {open && (
        <div
          className={cn(
            "absolute left-0 mt-1.5 w-72 rounded-xl shadow-2xl z-50 overflow-hidden",
            "bg-[#1A1F26] border border-[#334155] backdrop-blur-md",
            "animate-in fade-in-50 zoom-in-95 duration-150",
          )}
          role="listbox"
          data-testid="project-selector-dropdown"
        >
          <div className="p-2 border-b border-[#334155] bg-[#14181F]">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search projects by name / ID…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-[#20262E] text-xs text-slate-200 placeholder:text-slate-500 rounded-md pl-8 pr-2.5 py-1.5 border border-[#334155] focus:outline-none focus:border-brand-500 font-mono"
                autoFocus
              />
            </div>
          </div>

          <div className="max-h-60 overflow-y-auto p-1.5 space-y-1">
            {error ? (
              <div className="p-4 text-center space-y-2.5" data-testid="project-selector-error">
                <div className="w-8 h-8 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-400 mx-auto flex items-center justify-center">
                  <AlertCircle className="w-4 h-4" />
                </div>
                <p className="text-xs text-rose-300 font-medium leading-relaxed">
                  تعذر تحميل المشاريع — أعد المحاولة
                </p>
                <p className="text-[10px] text-slate-400">
                  Failed to load projects from server.
                </p>
                <button
                  type="button"
                  onClick={() => void loadProjects()}
                  className="px-3 py-1.5 rounded-lg bg-rose-600/30 hover:bg-rose-600/50 border border-rose-500/40 text-white text-xs font-semibold inline-flex items-center gap-1.5 transition-colors cursor-pointer"
                  data-testid="retry-load-projects"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  إعادة المحاولة (Retry)
                </button>
              </div>
            ) : filtered.length === 0 ? (
              <div className="py-6 text-center text-xs text-slate-500">
                No matching projects found
              </div>
            ) : (
              filtered.map((proj) => {
                const isSelected = proj.id === projectId;
                return (
                  <button
                    key={proj.id}
                    type="button"
                    onClick={() => {
                      setProjectId(proj.id);
                      setOpen(false);
                    }}
                    role="option"
                    aria-selected={isSelected}
                    className={cn(
                      "w-full flex items-start gap-2.5 p-2 rounded-lg text-left transition-colors text-xs",
                      isSelected
                        ? "bg-brand-600/20 border border-brand-500/40 text-white"
                        : "hover:bg-[#20262E] text-slate-300",
                    )}
                    data-testid={`project-option-${proj.id}`}
                  >
                    <div className="mt-0.5 shrink-0">
                      <span
                        className={cn(
                          "w-2 h-2 rounded-full inline-block",
                          proj.status === "active" ? "bg-emerald-400" : "bg-slate-500",
                        )}
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-slate-100 truncate">{proj.name}</div>
                      <div className="font-mono text-[10px] text-slate-400 truncate">{proj.id}</div>
                      {proj.description && (
                        <p className="text-[10px] text-slate-500 truncate mt-0.5">
                          {proj.description}
                        </p>
                      )}
                    </div>
                    {isSelected && (
                      <Check className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
                    )}
                  </button>
                );
              })
            )}
          </div>

          <div className="px-3 py-2 bg-[#14181F] border-t border-[#334155] flex items-center justify-between text-[11px] text-slate-400">
            <span>Total Projects: {projects.length}</span>
            <span className="font-mono text-[10px] text-emerald-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Active Project Context
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProjectSelector;
