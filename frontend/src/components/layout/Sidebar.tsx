/**
 * Sidebar.tsx — BAZspark V8.1 Production Sidebar
 *
 * Organized into 3 sections matching the reference design:
 *   WORKSPACE: Dashboard, Projects, Detectors, Cable Routing, Conduit,
 *              Circuits, Safety Rules, BOQ & Reports
 *   AI & SYSTEM: AI Agent, Digital Twin, BIM Import, FACP Design, Reports
 *   Settings: Settings, Audit Log, Self-Healing
 *
 * Colors:
 *   - Sidebar bg: #1e293b (slate-800)
 *   - Active item: red accent #ef4444 (red-500)
 *   - Logo: orange #f97316 (orange-500) hexagon with flame
 *   - Section headers: muted gray, uppercase, small
 */
import {
	AlertTriangle,
	BarChart,
	Brain,
	Cable,
	CircuitBoard,
	FileText,
	FolderOpen,
	Flame,
	Globe,
	Heart,
	LayoutDashboard,
	Settings,
	Shield,
	Upload,
	Wrench,
	Zap,
	ChevronLeft,
	ChevronRight,
} from "lucide-react";
import type React from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";

interface NavItem {
	labelKey: string;
	defaultLabel: string;
	icon: React.ElementType;
	path: string;
	dataOnboarding?: string;
}

interface NavSection {
	headerKey: string;
	defaultHeader: string;
	items: NavItem[];
}

// V8.1: Three-section layout matching the reference design
const navSections: NavSection[] = [
	{
		headerKey: "nav.workspace",
		defaultHeader: "WORKSPACE",
		items: [
			{
				labelKey: "nav.dashboard",
				defaultLabel: "Dashboard",
				icon: LayoutDashboard,
				path: "/dashboard",
				dataOnboarding: "nav-dashboard",
			},
			{
				labelKey: "nav.projects",
				defaultLabel: "Projects",
				icon: FolderOpen,
				path: "/projects",
				dataOnboarding: "nav-projects",
			},
			{
				labelKey: "nav.detectors",
				defaultLabel: "Detectors",
				icon: AlertTriangle,
				path: "/detectors",
			},
			{
				labelKey: "nav.cableRouting",
				defaultLabel: "Cable Routing",
				icon: Cable,
				path: "/cable-routing",
			},
			{
				labelKey: "nav.conduit",
				defaultLabel: "Conduit",
				icon: Wrench,
				path: "/conduit",
			},
			{
				labelKey: "nav.circuits",
				defaultLabel: "Circuits",
				icon: Zap,
				path: "/circuits",
			},
			{
				labelKey: "nav.safetyRules",
				defaultLabel: "Safety Rules",
				icon: Shield,
				path: "/safety-rules",
			},
			{
				labelKey: "nav.boqReports",
				defaultLabel: "BOQ & Reports",
				icon: FileText,
				path: "/reports",
				dataOnboarding: "nav-reports",
			},
		],
	},
	{
		headerKey: "nav.aiSystem",
		defaultHeader: "AI & SYSTEM",
		items: [
			{
				labelKey: "nav.aiAgent",
				defaultLabel: "AI Agent",
				icon: Brain,
				path: "/ai-agent",
			},
			{
				labelKey: "nav.digitalTwin",
				defaultLabel: "Digital Twin",
				icon: Globe,
				path: "/digital-twin",
			},
			{
				labelKey: "nav.bimImport",
				defaultLabel: "BIM Import",
				icon: Upload,
				path: "/bim-import",
			},
			{
				labelKey: "nav.facpDesign",
				defaultLabel: "FACP Design",
				icon: CircuitBoard,
				path: "/facp",
			},
			{
				labelKey: "nav.reports",
				defaultLabel: "Reports",
				icon: BarChart,
				path: "/reports-generator",
			},
		],
	},
	{
		headerKey: "nav.settingsSection",
		defaultHeader: "SETTINGS",
		items: [
			{
				labelKey: "nav.settings",
				defaultLabel: "Settings",
				icon: Settings,
				path: "/settings",
				dataOnboarding: "nav-settings",
			},
			{
				labelKey: "nav.auditLog",
				defaultLabel: "Audit Log",
				icon: FileText,
				path: "/audit-log",
			},
			{
				labelKey: "nav.selfHealing",
				defaultLabel: "Self-Healing",
				icon: Heart,
				path: "/self-healing",
				dataOnboarding: "nav-self-healing",
			},
		],
	},
];

interface SidebarProps {
	compact?: boolean;
}

const Sidebar: React.FC<SidebarProps> = () => {
	const [collapsed, setCollapsed] = useState(false);
	const location = useLocation();
	const { t } = useTranslation();
	const isRTL = document.documentElement.dir === "rtl";

	const width = collapsed ? "w-16" : "w-60";

	return (
		<aside
			className={`${width} h-full bg-slate-800 border-${
				isRTL ? "l" : "r"
			} border-slate-700/50 flex flex-col transition-all duration-300 ${
				isRTL ? "order-last" : "order-first"
			}`}
		>
			{/* Logo header — orange hexagon with flame + BAZspark text */}
			<div className="flex items-center gap-2.5 px-4 py-3 border-b border-slate-700/50 shrink-0">
				<div className="h-8 w-8 rounded-md bg-orange-500/20 border border-orange-500/40 flex items-center justify-center shrink-0">
					<Flame className="h-4 w-4 text-orange-500" fill="currentColor" />
				</div>
				{!collapsed && (
					<div className="flex flex-col leading-tight">
						<span className="text-orange-500 font-bold text-sm tracking-tight">
							BAZspark
						</span>
						<span className="text-[10px] text-slate-400 uppercase tracking-wider">
							V8.1 Production
						</span>
					</div>
				)}
			</div>

			<nav
				className="flex-1 py-2 overflow-y-auto overflow-x-hidden"
				aria-label="Primary navigation"
			>
				{navSections.map((section) => (
					<div key={section.headerKey} className="mb-4">
						{!collapsed && (
							<h3 className="px-4 py-1 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
								{t(section.headerKey, section.defaultHeader)}
							</h3>
						)}
						{section.items.map((item) => {
							const isActive =
								location.pathname === item.path ||
								(item.path !== "/dashboard" &&
									location.pathname.startsWith(`${item.path}/`));
							const labelText = t(item.labelKey, item.defaultLabel);
							return (
								<div key={item.path} className="px-2 mb-0.5">
									<Link
										to={item.path}
										className={`flex items-center gap-3 px-3 py-2 rounded-md transition-all duration-150 ${
											isActive
												? "bg-slate-900/60 text-red-500 border-l-2 border-red-500"
												: "text-slate-300 hover:bg-slate-700/50 hover:text-white"
										}`}
										title={collapsed ? labelText : undefined}
										data-onboarding={item.dataOnboarding}
									>
										<item.icon
											className={`shrink-0 h-4 w-4 ${
												isActive ? "text-red-500" : "text-slate-400"
											}`}
										/>
										{!collapsed && (
											<span className="truncate text-sm font-medium">
												{labelText}
											</span>
										)}
									</Link>
								</div>
							);
						})}
					</div>
				))}
				{!collapsed && (
					<p className="px-4 py-2 text-[10px] text-slate-600 italic">
						Marine module hidden — switch project type in Settings
					</p>
				)}
			</nav>

			<button
				onClick={() => setCollapsed(!collapsed)}
				className="flex items-center justify-center py-2 border-t border-slate-700/50 text-slate-400 hover:text-white transition-all duration-200 hover:bg-slate-700/50 shrink-0"
				aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
				data-onboarding="sidebar-toggle"
			>
				{collapsed ? (
					isRTL ? (
						<ChevronLeft className="h-4 w-4" />
					) : (
						<ChevronRight className="h-4 w-4" />
					)
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
