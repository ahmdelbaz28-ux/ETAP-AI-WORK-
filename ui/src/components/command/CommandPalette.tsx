// UI components are intentionally complex for feature-rich DX
import {
  Activity,
  ArrowRight,
  Bot,
  Bug,
  Command,
  Download,
  FileText,
  FlaskConical,
  FolderPlus,
  HelpCircle,
  Layers,
  LayoutDashboard,
  Map,
  ScrollText,
  Search,
  Settings,
  ShieldCheck,
  Upload,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { cn } from "../../utils/helpers";

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon: React.ElementType;
  shortcut?: string;
  section: string;
  action: () => void;
}

// --- Module-scope static command catalog (extracted from the inline useMemo
// callback to keep S3776 cognitive complexity below the threshold). ---
// Each entry stores bilingual label/description/section plus an action factory
// so the runtime `lang` decision stays a single property pick per field.

type Lang = "en" | "ar";

interface BilingualText {
  readonly en: string;
  readonly ar: string;
}

interface CommandDef {
  readonly id: string;
  readonly label: BilingualText;
  readonly description?: BilingualText;
  readonly icon: React.ElementType;
  readonly shortcut?: string;
  readonly section: BilingualText;
  readonly buildAction: (navigate: ReturnType<typeof useNavigate>) => () => void;
}

const NAV_SECTION: BilingualText = { en: "Navigation", ar: "التنقل" };
const ENG_SECTION: BilingualText = { en: "Engineering", ar: "الهندسة" };
const ACTION_SECTION: BilingualText = { en: "Actions", ar: "إجراءات" };

const COMMAND_DEFS: ReadonlyArray<CommandDef> = [
  // Navigation
  {
    id: "nav-dashboard",
    label: { en: "Dashboard", ar: "لوحة التحكم" },
    description: { en: "Go to main dashboard", ar: "الذهاب للوحة الرئيسية" },
    icon: LayoutDashboard,
    shortcut: "G D",
    section: NAV_SECTION,
    buildAction: (navigate) => () => navigate("/dashboard"),
  },
  {
    id: "nav-studies",
    label: { en: "Studies", ar: "الدراسات" },
    description: { en: "Engineering studies", ar: "نظرة عامة على الدراسات" },
    icon: FlaskConical,
    shortcut: "G S",
    section: NAV_SECTION,
    buildAction: (navigate) => () => navigate("/studies"),
  },
  {
    id: "nav-assistant",
    label: { en: "AI Assistant", ar: "المساعد الذكي" },
    description: { en: "Chat with AI agents", ar: "الدردشة مع الوكلاء" },
    icon: Bot,
    shortcut: "G A",
    section: NAV_SECTION,
    buildAction: (navigate) => () => navigate("/assistant"),
  },
  {
    id: "nav-projects",
    label: { en: "Projects", ar: "المشاريع" },
    description: { en: "Manage projects", ar: "إدارة المشاريع" },
    icon: FolderPlus,
    shortcut: "G P",
    section: NAV_SECTION,
    buildAction: (navigate) => () => navigate("/projects"),
  },
  {
    id: "nav-asset-management",
    label: { en: "Asset Management", ar: "إدارة الأصول" },
    description: { en: "Power system assets", ar: "أصول النظام" },
    icon: Activity,
    section: NAV_SECTION,
    buildAction: (navigate) => () => navigate("/asset-management"),
  },
  {
    id: "nav-reports",
    label: { en: "Reports", ar: "التقارير" },
    description: { en: "View reports", ar: "عرض التقارير" },
    icon: FileText,
    section: NAV_SECTION,
    buildAction: (navigate) => () => navigate("/reports"),
  },
  {
    id: "nav-settings",
    label: { en: "Settings", ar: "الإعدادات" },
    description: { en: "App settings", ar: "إعدادات التطبيق" },
    icon: Settings,
    shortcut: "G ,",
    section: NAV_SECTION,
    buildAction: (navigate) => () => navigate("/settings"),
  },
  {
    id: "nav-diagnostics",
    label: { en: "Diagnostics", ar: "التشخيص" },
    description: { en: "System checks", ar: "فحوصات النظام" },
    icon: Bug,
    section: NAV_SECTION,
    buildAction: (navigate) => () => navigate("/diagnostics"),
  },
  {
    id: "nav-logs",
    label: { en: "Logs", ar: "السجلات" },
    description: { en: "Audit log", ar: "سجل التدقيق" },
    icon: ScrollText,
    section: NAV_SECTION,
    buildAction: (navigate) => () => navigate("/logs"),
  },
  {
    id: "nav-admin",
    label: { en: "Administration", ar: "الإدارة" },
    description: { en: "System admin", ar: "إدارة النظام" },
    icon: ShieldCheck,
    section: NAV_SECTION,
    buildAction: (navigate) => () => navigate("/admin"),
  },
  // Engineering
  {
    id: "nav-etap",
    label: { en: "ETAP Integration", ar: "تكامل ETAP" },
    icon: Zap,
    section: ENG_SECTION,
    buildAction: (navigate) => () => navigate("/etap"),
  },
  {
    id: "nav-gis",
    label: { en: "GIS Integration", ar: "تكامل GIS" },
    icon: Map,
    section: ENG_SECTION,
    buildAction: (navigate) => () => navigate("/gis"),
  },
  {
    id: "nav-digital-twin",
    label: { en: "Digital Twin", ar: "التوأم الرقمي" },
    icon: Layers,
    section: ENG_SECTION,
    buildAction: (navigate) => () => navigate("/digital-twin"),
  },
  {
    id: "nav-code-guard",
    label: { en: "Code Guard", ar: "حارس الكود" },
    icon: ShieldCheck,
    section: ENG_SECTION,
    buildAction: (navigate) => () => navigate("/code-guard"),
  },
  // Actions
  {
    id: "act-import",
    label: { en: "Import Data", ar: "استيراد البيانات" },
    icon: Upload,
    section: ACTION_SECTION,
    buildAction: (navigate) => () => navigate("/data-import"),
  },
  {
    id: "act-export",
    label: { en: "Export Data", ar: "تصدير البيانات" },
    icon: Download,
    section: ACTION_SECTION,
    buildAction: (navigate) => () => navigate("/data-export"),
  },
  {
    id: "act-help",
    label: { en: "Smart Help", ar: "المساعدة الذكية" },
    icon: HelpCircle,
    shortcut: "F1",
    section: ACTION_SECTION,
    buildAction: () => () => globalThis.dispatchEvent(new CustomEvent("toggle-smart-help")),
  },
  {
    id: "act-magic-help",
    label: { en: "✨ Magic Help Inspector", ar: "✨ فاحص المساعدة" },
    icon: Zap,
    section: ACTION_SECTION,
    buildAction: () => () => globalThis.dispatchEvent(new CustomEvent("start-magic-help-inspect")),
  },
];

function buildStaticCommands(lang: Lang, navigate: ReturnType<typeof useNavigate>): CommandItem[] {
  return COMMAND_DEFS.map((def) => ({
    id: def.id,
    label: def.label[lang],
    description: def.description?.[lang],
    icon: def.icon,
    shortcut: def.shortcut,
    section: def.section[lang],
    action: def.buildAction(navigate),
  }));
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const lang: Lang = i18n.language === "ar" ? "ar" : "en";

  // ─── Static commands (always available) ──────────────────────────────
  const staticCommands: CommandItem[] = useMemo(
    () => buildStaticCommands(lang, navigate),
    [lang, navigate],
  );

  // ─── Filter by query ────────────────────────────────────────────────
  const filtered = useMemo(() => {
    if (!query.trim()) return staticCommands;
    const q = query.toLowerCase();
    return staticCommands.filter((c) => {
      const haystack = `${c.label} ${c.description || ""} ${c.section} ${c.id}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [query, staticCommands]);

  const sections = useMemo(() => {
    const set = new Set<string>();
    filtered.forEach((c) => set.add(c.section));
    return Array.from(set);
  }, [filtered]);

  const executeCommand = useCallback((cmd: CommandItem) => {
    cmd.action();
    setOpen(false);
    setQuery("");
    setSelectedIndex(0);
  }, []);

  // Toggle with Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    globalThis.addEventListener("keydown", handleKeyDown);
    return () => globalThis.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Focus input on open
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setSelectedIndex(0);
    }
  }, [open]);

  // Reset selection on query change
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Keyboard navigation (only when open)
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        executeCommand(filtered[selectedIndex]);
      } else if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        setQuery("");
      }
    };
    globalThis.addEventListener("keydown", handleKeyDown);
    return () => globalThis.removeEventListener("keydown", handleKeyDown);
  }, [open, filtered, selectedIndex, executeCommand]);

  // Scroll selected item into view
  useEffect(() => {
    if (listRef.current) {
      const item = listRef.current.querySelector(`[data-index="${selectedIndex}"]`);
      item?.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]">
      {/* NOSONAR — typescript:S6819: native <button type="button"> for backdrop accessibility */}
      <button
        type="button"
        className="absolute inset-0 bg-black/60 backdrop-blur-sm cursor-default border-0 p-0"
        aria-label="Close command palette"
        onClick={() => {
          setOpen(false);
          setQuery("");
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            setOpen(false);
            setQuery("");
          }
        }}
      />

import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, LayoutDashboard, FolderPlus, Radio, FileText, ShieldCheck,
  HelpCircle, Settings, Activity, Zap, FlaskConical, Bot, Map,
  Layers, Bug, ScrollText, Download, Upload, ArrowRight, Command,
} from 'lucide-react'
import { cn } from '../../utils/helpers'

interface Command {
  id: string
  label: string
  description?: string
  icon: React.ElementType
  shortcut?: string
  section: string
  action: () => void
}

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  const commands: Command[] = [
    // Navigation
    { id: 'dashboard', label: 'Open Dashboard', description: 'Go to the main dashboard', icon: LayoutDashboard, shortcut: 'G D', section: 'Navigation', action: () => navigate('/dashboard') },
    { id: 'studies', label: 'Open Studies', description: 'Engineering studies overview', icon: FlaskConical, shortcut: 'G S', section: 'Navigation', action: () => navigate('/studies') },
    { id: 'assistant', label: 'Open AI Assistant', description: 'Chat with AI agents', icon: Bot, shortcut: 'G A', section: 'Navigation', action: () => navigate('/assistant') },
    { id: 'projects', label: 'Open Projects', description: 'Manage projects', icon: FolderPlus, shortcut: 'G P', section: 'Navigation', action: () => navigate('/projects') },
    { id: 'reports', label: 'Open Reports', description: 'View generated reports', icon: FileText, section: 'Navigation', action: () => navigate('/reports') },
    { id: 'settings', label: 'Open Settings', description: 'Application settings', icon: Settings, shortcut: 'G ,', section: 'Navigation', action: () => navigate('/settings') },
    { id: 'diagnostics', label: 'Open Diagnostics', description: 'System health checks', icon: Bug, section: 'Navigation', action: () => navigate('/diagnostics') },
    { id: 'logs', label: 'Open Logs', description: 'Audit log viewer', icon: ScrollText, section: 'Navigation', action: () => navigate('/logs') },

    // Engineering
    { id: 'etap', label: 'ETAP Integration', description: 'Connect to ETAP software', icon: Zap, section: 'Engineering', action: () => navigate('/etap') },
    { id: 'gis', label: 'GIS Integration', description: 'Geographic information system', icon: Map, section: 'Engineering', action: () => navigate('/gis') },
    { id: 'digital-twin', label: 'Digital Twin', description: 'Network digital twin', icon: Layers, section: 'Engineering', action: () => navigate('/digital-twin') },
    { id: 'assets', label: 'Asset Management', description: 'Power system assets', icon: Activity, section: 'Engineering', action: () => navigate('/asset-management') },
    { id: 'code-guard', label: 'Code Guard', description: 'Security code review', icon: ShieldCheck, section: 'Engineering', action: () => navigate('/code-guard') },

    // Actions
    { id: 'import', label: 'Import Data', description: 'Import project data files', icon: Upload, section: 'Actions', action: () => navigate('/data-import') },
    { id: 'export', label: 'Export Data', description: 'Export results and reports', icon: Download, section: 'Actions', action: () => navigate('/data-export') },
    { id: 'help', label: 'Smart Help', description: 'Open the help panel', icon: HelpCircle, shortcut: 'F1', section: 'Actions', action: () => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'F1' })) },
    { id: 'status', label: 'Check Backend Status', description: 'Verify API connectivity', icon: Activity, section: 'Actions', action: () => navigate('/diagnostics') },
  ]

  const filtered = query
    ? commands.filter(c =>
        c.label.toLowerCase().includes(query.toLowerCase()) ||
        c.description?.toLowerCase().includes(query.toLowerCase()) ||
        c.section.toLowerCase().includes(query.toLowerCase())
      )
    : commands

  const sections = [...new Set(filtered.map(c => c.section))]

  const executeCommand = useCallback((cmd: Command) => {
    cmd.action()
    setOpen(false)
    setQuery('')
    setSelectedIndex(0)
  }, [])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(prev => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
      setSelectedIndex(0)
    }
  }, [open])

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  useEffect(() => {
    if (!open) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, filtered.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
      } else if (e.key === 'Enter' && filtered[selectedIndex]) {
        executeCommand(filtered[selectedIndex])
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, filtered, selectedIndex, executeCommand])

  useEffect(() => {
    if (listRef.current) {
      const item = listRef.current.querySelector(`[data-index="${selectedIndex}"]`)
      item?.scrollIntoView({ block: 'nearest' })
    }
  }, [selectedIndex])

  if (!open) return null

  let globalIndex = -1

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setOpen(false)} />

      <div className="relative z-[101] w-full max-w-xl mx-4 bg-[var(--bg-secondary)] border border-[var(--border-secondary)] rounded-xl shadow-2xl overflow-hidden">
        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--border-primary)]">
          <Search className="w-5 h-5 text-[var(--text-muted)] shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              lang === "ar"
                ? `ابحث في ${filtered.length} عنصر...`
                : `Search ${filtered.length} items...`
            }
            className="flex-1 bg-transparent text-[var(--text-primary)] text-sm placeholder:text-[var(--text-muted)] outline-none"
          />
          <kbd className="px-1.5 py-0.5 text-[10px] font-mono text-[var(--text-muted)] bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded">
            ESC
          </kbd>
        </div>

        {/* Command List */}
        <div ref={listRef} className="max-h-[50vh] overflow-y-auto py-2">
          {filtered.length > 0 ? (
            sections.map((section) => {
              const sectionCommands = filtered
                .map((cmd, idx) => ({ cmd, idx }))
                .filter(({ cmd }) => cmd.section === section);
              return (
                <div key={section}>
                  <div className="px-4 py-1.5 text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                    {section}
                  </div>
                  {sectionCommands.map(({ cmd, idx }) => {
                    const isSelected = idx === selectedIndex;
                    return (
                      <button
                        key={cmd.id}
                        data-index={idx}
                        onClick={() => executeCommand(cmd)}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        className={cn(
                          "w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors",
                          isSelected
                            ? "bg-[var(--accent-glow)] text-[var(--accent-primary)]"
                            : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]",
                        )}
                        type="button"
                      >
                        <cmd.icon
                          className={cn(
                            "w-4 h-4 shrink-0",
                            isSelected
                              ? "text-[var(--accent-primary)]"
                              : "text-[var(--text-muted)]",
                          )}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">{cmd.label}</div>
                          {cmd.description && (
                            <div className="text-xs text-[var(--text-muted)] truncate">
                              {cmd.description}
                            </div>
                          )}
                        </div>
                        {cmd.shortcut && (
                          <div className="flex gap-1">
                            {cmd.shortcut.split(" ").map((k) => (
                              <kbd
                                key={k}
                                className="px-1.5 py-0.5 text-[10px] font-mono text-[var(--text-muted)] bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded"
                              >
                                {k}
                              </kbd>
                            ))}
                          </div>
                        )}
                        {isSelected && (
                          <ArrowRight className="w-3.5 h-3.5 text-[var(--accent-primary)] shrink-0" />
                        )}
                      </button>
                    );
                  })}
                </div>
              );
            })
          ) : (
            <div className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">
              {lang === "ar" ? `لا توجد نتائج لـ "${query}"` : `No results for "${query}"`}

          {sections.map(section => (
            <div key={section}>
              <div className="px-4 py-1.5 text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                {section}
              </div>
              {filtered.filter(c => c.section === section).map(cmd => {
                globalIndex++
                const idx = globalIndex
                const isSelected = idx === selectedIndex
                return (
                  <button
                    key={cmd.id}
                    data-index={idx}
                    onClick={() => executeCommand(cmd)}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={cn(
                      'w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors',
                      isSelected
                        ? 'bg-[var(--accent-glow)] text-[var(--accent-primary)]'
                        : 'text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'
                    )}
                  >
                    <cmd.icon className={cn('w-4 h-4 shrink-0', isSelected ? 'text-[var(--accent-primary)]' : 'text-[var(--text-muted)]')} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{cmd.label}</div>
                      {cmd.description && (
                        <div className="text-xs text-[var(--text-muted)] truncate">{cmd.description}</div>
                      )}
                    </div>
                    {cmd.shortcut && (
                      <div className="flex gap-1">
                        {cmd.shortcut.split(' ').map(k => (
                          <kbd key={k} className="px-1.5 py-0.5 text-[10px] font-mono text-[var(--text-muted)] bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded">
                            {k}
                          </kbd>
                        ))}
                      </div>
                    )}
                    {isSelected && <ArrowRight className="w-3.5 h-3.5 text-[var(--accent-primary)] shrink-0" />}
                  </button>
                )
              })}
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">
              No commands found for "{query}"
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-4 px-4 py-2.5 border-t border-[var(--border-primary)] text-[10px] text-[var(--text-muted)]">
          <span className="flex items-center gap-1">
            <Command className="w-3 h-3" /> K to toggle
          </span>
          <span>↑↓ navigate</span>
          <span>↵ select</span>
          <span>esc close</span>
          <span className="ml-auto">{filtered.length} commands</span>
        </div>
      </div>
    </div>
  );
}
