/**
 * Sidebar.tsx — BAZSPARK V8.1 Production Sidebar
 *
 * Per V8.1 Stitch-Ready UI Prompt:
 *   Width: 260px, bg=Surface-2 (#1E293B), border-right Border
 *   Logo: Flame icon #E84040 + "BAZspark" 18px 700 + "v8.1" badge
 *
 *   Nav sections (3 groups):
 *     WORKSPACE: Dashboard, Projects, Detectors, Cable Routing, Conduit,
 *                Circuits, Safety Rules, BOQ & Reports
 *     MARINE ⚓:  Vessel Overview, Zone Mapping, Detector Grid, Gas/UGLD,
 *                PA/Alarm Zones, Class Compliance
 *     AI & SYSTEM: AI Agent, Digital Twin, BIM Import, Settings, Audit Log,
 *                  Self-Healing
 *
 *   Active state: bg=red/10, text=#E84040, left border 2px #E84040
 *   Marine active: bg=ocean/10, text=#0EA5E9
 *   AI active: bg=purple/10, text=#A78BFA
 *
 *   Bottom: User avatar (32px, initials, bg=#E84040) + name + role
 */
import {
        Activity,
        Anchor,
        BarChart3,
        BrainCircuit,
        Cable,
        ClipboardCheck,
        Flame,
        FolderOpen,
        LayoutDashboard,
        Map,
        Pickaxe,
        Radio,
        RotateCcw,
        Settings,
        ShieldCheck,
        Upload,
        Volume2,
        ChevronLeft,
        ChevronRight,
        Zap,
} from "lucide-react";
import type React from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";

type NavAccent = "red" | "ocean" | "purple";

interface NavItem {
        labelKey: string;
        defaultLabel: string;
        icon: React.ElementType;
        path: string;
        accent: NavAccent;
        shortcut?: string;
        badge?: string;
}

interface NavSection {
        headerKey: string;
        defaultHeader: string;
        items: NavItem[];
        accent: NavAccent;
}

const navSections: NavSection[] = [
        {
                headerKey: "nav.workspace",
                defaultHeader: "WORKSPACE",
                accent: "red",
                items: [
                        { labelKey: "nav.dashboard", defaultLabel: "Dashboard", icon: LayoutDashboard, path: "/dashboard", accent: "red", shortcut: "⌘1" },
                        { labelKey: "nav.projects", defaultLabel: "Projects", icon: FolderOpen, path: "/projects", accent: "red", shortcut: "⌘2" },
                        { labelKey: "nav.detectors", defaultLabel: "Detectors", icon: Radio, path: "/detectors", accent: "red", shortcut: "⌘3" },
                        { labelKey: "nav.cableRouting", defaultLabel: "Cable Routing", icon: Cable, path: "/cable-routing", accent: "red" },
                        { labelKey: "nav.conduit", defaultLabel: "Conduit", icon: Activity, path: "/conduit", accent: "red" },
                        { labelKey: "nav.circuits", defaultLabel: "Circuits", icon: Zap, path: "/circuits", accent: "red" },
                        { labelKey: "nav.safetyRules", defaultLabel: "Safety Rules", icon: ShieldCheck, path: "/safety-rules", accent: "red", badge: "NFPA 72" },
                        { labelKey: "nav.mining", defaultLabel: "Mining", icon: Pickaxe, path: "/mining", accent: "red" },
                        { labelKey: "nav.boqReports", defaultLabel: "BOQ & Reports", icon: BarChart3, path: "/reports", accent: "red" },
                ],
        },
        {
                headerKey: "nav.marine",
                defaultHeader: "MARINE ⚓",
                accent: "ocean",
                items: [
                        { labelKey: "nav.vesselOverview", defaultLabel: "Vessel Overview", icon: Anchor, path: "/marine", accent: "ocean" },
                        { labelKey: "nav.zoneMapping", defaultLabel: "Zone Mapping", icon: Map, path: "/marine/zones", accent: "ocean" },
                        { labelKey: "nav.detectorGrid", defaultLabel: "Detector Grid", icon: Radio, path: "/marine/detectors", accent: "ocean" },
                        { labelKey: "nav.gasUgld", defaultLabel: "Gas / UGLD", icon: Radio, path: "/marine/gas", accent: "ocean" },
                        { labelKey: "nav.paAlarmZones", defaultLabel: "PA / Alarm Zones", icon: Volume2, path: "/marine/pa", accent: "ocean" },
                        { labelKey: "nav.classCompliance", defaultLabel: "Class Compliance", icon: ClipboardCheck, path: "/marine/compliance", accent: "ocean" },
                ],
        },
        {
                headerKey: "nav.aiSystem",
                defaultHeader: "AI & SYSTEM",
                accent: "purple",
                items: [
                        { labelKey: "nav.aiAgent", defaultLabel: "AI Agent", icon: BrainCircuit, path: "/ai-agent", accent: "purple", badge: "Ask BAZspark" },
                        { labelKey: "nav.digitalTwin", defaultLabel: "Digital Twin", icon: RotateCcw, path: "/digital-twin", accent: "purple" },
                        { labelKey: "nav.bimImport", defaultLabel: "BIM Import", icon: Upload, path: "/bim-import", accent: "purple" },
                        { labelKey: "nav.facpDesign", defaultLabel: "FACP Design", icon: Zap, path: "/facp", accent: "purple" },
                        { labelKey: "nav.settings", defaultLabel: "Settings", icon: Settings, path: "/settings", accent: "purple", shortcut: "⌘," },
                        { labelKey: "nav.auditLog", defaultLabel: "Audit Log", icon: BarChart3, path: "/audit-log", accent: "purple" },
                        { labelKey: "nav.selfHealing", defaultLabel: "Self-Healing", icon: Activity, path: "/self-healing", accent: "purple" },
                ],
        },
];

const accentClasses: Record<NavAccent, { active: string; hover: string; icon: string }> = {
        red: {
                active: "bg-red-500/10 text-[#E84040] border-l-2 border-[#E84040]",
                hover: "text-slate-300 hover:bg-slate-700/50 hover:text-white",
                icon: "text-[#E84040]",
        },
        ocean: {
                active: "bg-sky-500/10 text-[#0EA5E9] border-l-2 border-[#0EA5E9]",
                hover: "text-slate-300 hover:bg-slate-700/50 hover:text-white",
                icon: "text-[#0EA5E9]",
        },
        purple: {
                active: "bg-purple-500/10 text-[#A78BFA] border-l-2 border-[#A78BFA]",
                hover: "text-slate-300 hover:bg-slate-700/50 hover:text-white",
                icon: "text-[#A78BFA]",
        },
};

const sectionHeaderColors: Record<NavAccent, string> = {
        red: "text-slate-500",
        ocean: "text-[#0EA5E9]",
        purple: "text-slate-500",
};

interface SidebarProps {
        compact?: boolean;
}

const Sidebar: React.FC<SidebarProps> = () => {
        const [collapsed, setCollapsed] = useState(false);
        const location = useLocation();
        const { t } = useTranslation();
        const isRTL = document.documentElement.dir === "rtl";

        const width = collapsed ? "w-16" : "w-[260px]";

        return (
                <aside
                        className={`${width} h-full bg-[#1E293B] border-r border-[#334155] flex flex-col transition-all duration-150 ${
                                isRTL ? "order-last" : "order-first"
                        }`}
                >
                        {/* Logo section (h=64px, border-bottom) */}
                        <div className="flex items-center gap-2.5 px-4 h-16 border-b border-[#334155] shrink-0">
                                <div className="h-8 w-8 rounded-md flex items-center justify-center shrink-0 bg-[#E84040]/10">
                                        <Flame className="h-5 w-5 text-[#E84040]" fill="currentColor" />
                                </div>
                                {!collapsed && (
                                        <div className="flex items-center gap-2">
                                                <span className="text-white font-bold text-[18px] tracking-tight">
                                                        BAZspark
                                                </span>
                                                <span className="text-caption text-[#38BDF8] bg-[#38BDF8]/10 px-2 py-0.5 rounded-full">
                                                        v8.1
                                                </span>
                                        </div>
                                )}
                        </div>

                        <nav
                                className="flex-1 py-3 px-3 overflow-y-auto overflow-x-hidden"
                                aria-label="Primary navigation"
                        >
                                {navSections.map((section, sectionIdx) => (
                                        <div key={section.headerKey} className={sectionIdx > 0 ? "mt-4" : ""}>
                                                {!collapsed && (
                                                        <h3
                                                                className={`px-3 py-2 text-caption font-semibold uppercase tracking-wider ${sectionHeaderColors[section.accent]}`}
                                                        >
                                                                {t(section.headerKey, section.defaultHeader)}
                                                        </h3>
                                                )}
                                                {section.items.map((item) => {
                                                        const isActive =
                                                                location.pathname === item.path ||
                                                                (item.path !== "/dashboard" &&
                                                                        item.path !== "/marine" &&
                                                                        location.pathname.startsWith(`${item.path}/`));
                                                        const labelText = t(item.labelKey, item.defaultLabel);
                                                        const accent = accentClasses[item.accent];
                                                        return (
                                                                <Link
                                                                        key={item.path}
                                                                        to={item.path}
                                                                        className={`flex items-center gap-3 px-3 h-10 rounded-md transition-all duration-150 mb-0.5 ${
                                                                                isActive ? accent.active : accent.hover
                                                                        }`}
                                                                        title={collapsed ? labelText : undefined}
                                                                >
                                                                        <item.icon
                                                                                className={`shrink-0 h-5 w-5 ${
                                                                                        isActive ? accent.icon : "text-slate-400"
                                                                                }`}
                                                                        />
                                                                        {!collapsed && (
                                                                                <>
                                                                                        <span className="flex-1 truncate text-sm font-medium">
                                                                                                {labelText}
                                                                                        </span>
                                                                                        {item.badge && (
                                                                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-300">
                                                                                                        {item.badge}
                                                                                                </span>
                                                                                        )}
                                                                                        {item.shortcut && (
                                                                                                <span className="text-[10px] text-slate-500 font-mono">
                                                                                                        {item.shortcut}
                                                                                                </span>
                                                                                        )}
                                                                                </>
                                                                        )}
                                                                </Link>
                                                        );
                                                })}
                                        </div>
                                ))}
                        </nav>

                        {/* Bottom: User profile section (border-top, padding 12px) */}
                        <div className="border-t border-[#334155] p-3 shrink-0">
                                <div className="flex items-center gap-3">
                                        <div className="h-8 w-8 rounded-full bg-[#E84040] flex items-center justify-center shrink-0">
                                                <span className="text-white text-xs font-bold">AE</span>
                                        </div>
                                        {!collapsed && (
                                                <div className="flex-1 min-w-0">
                                                        <div className="text-sm font-semibold text-white truncate">
                                                                Eng. Ahmed Elbaz
                                                        </div>
                                                        <div className="text-xs text-slate-400 truncate">
                                                                Fire Protection Engineer
                                                        </div>
                                                </div>
                                        )}
                                        {!collapsed && (
                                                <Link
                                                        to="/settings"
                                                        className="p-1.5 text-slate-400 hover:text-white transition-colors rounded"
                                                        aria-label="Settings"
                                                >
                                                        <Settings className="h-4 w-4" />
                                                </Link>
                                        )}
                                </div>
                        </div>

                        {/* Collapse toggle */}
                        <button
                                onClick={() => setCollapsed(!collapsed)}
                                className="flex items-center justify-center h-8 border-t border-[#334155] text-slate-400 hover:text-white hover:bg-slate-700/50 transition-all duration-150 shrink-0"
                                aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                                data-onboarding="sidebar-toggle"
                        >
                                {collapsed ? (
                                        isRTL ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />
                                ) : isRTL ? (
                                        <ChevronRight className="h-4 w-4" />
                                ) : (
                                        <ChevronLeft className="h-4 w-4" />
                                )}
                        </button>
                </aside>
        );
};

export default Sidebar;
