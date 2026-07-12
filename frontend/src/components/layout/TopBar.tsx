/**
 * TopBar.tsx — BAZspark V8.1 Production Top Bar
 *
 * Layout matches reference design:
 *   Left: Breadcrumb (Home > PageName) + version badge
 *   Right: Search bar + status icons + user profile
 *
 * No hover:scale, no shadow — flat engineering style.
 */
import { Bell, Globe, HelpCircle, Search, Sun } from "lucide-react";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { UserMenu } from "@/components/auth/UserMenu";
import { ContextualHelpButton } from "@/components/shared/ContextualHelpButton";

interface TopBarProps {
	isConnected: boolean;
	onHelpOpen: () => void;
	onSearchOpen?: () => void;
	currentLanguage: string;
	onLanguageChange: (lang: string) => void;
}

const routeLabels: Record<string, string> = {
	"/": "Dashboard",
	"/dashboard": "Dashboard",
	"/projects": "Projects",
	"/detectors": "Detectors",
	"/cable-routing": "Cable Routing",
	"/conduit": "Conduit",
	"/circuits": "Circuits",
	"/safety-rules": "Safety Rules",
	"/reports": "BOQ & Reports",
	"/reports-generator": "Reports",
	"/ai-agent": "AI Agent",
	"/digital-twin": "Digital Twin",
	"/bim-import": "BIM Import",
	"/facp": "FACP Design",
	"/settings": "Settings",
	"/audit-log": "Audit Log",
	"/self-healing": "Self-Healing",
	"/engineering": "Engineering",
	"/marine": "Marine",
	"/mining": "Mining",
	"/fire-alarm/designer": "Fire Alarm Designer",
	"/autocad": "AutoCAD",
	"/revit": "Revit",
	"/elements": "Elements",
	"/connections": "Connections",
	"/conflicts": "Conflicts",
	"/exports": "Exports",
	"/api-keys": "API Keys",
	"/environment": "Environment",
	"/monitor": "Monitor",
	"/memory": "Memory",
	"/graphrag": "GraphRAG",
	"/workflow": "Workflows",
};

const TopBar: React.FC<TopBarProps> = ({
	isConnected,
	onHelpOpen,
	onSearchOpen,
	currentLanguage,
	onLanguageChange,
}) => {
	const location = useLocation();
	const [langOpen, setLangOpen] = useState(false);
	const langRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		const handler = (e: MouseEvent) => {
			if (langRef.current && !langRef.current.contains(e.target as Node)) {
				setLangOpen(false);
			}
		};
		document.addEventListener("mousedown", handler);
		return () => document.removeEventListener("mousedown", handler);
	}, []);

	const pageName = routeLabels[location.pathname] || "Dashboard";

	return (
		<header className="h-12 bg-slate-900 border-b border-slate-700/50 flex items-center px-4 gap-3 shrink-0">
			{/* Left: Breadcrumb */}
			<div className="flex items-center gap-2 text-sm">
				<Link
					to="/dashboard"
					className="text-slate-400 hover:text-white transition-colors"
				>
					Home
				</Link>
				<span className="text-slate-600">/</span>
				<span className="text-white font-medium">{pageName}</span>
				<span className="text-[10px] text-slate-500 ml-2">v8.1</span>
			</div>

			<div className="flex-1" />

			{/* Search bar */}
			<button
				onClick={onSearchOpen}
				className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 border border-slate-700/50 rounded-md text-slate-400 text-xs hover:bg-slate-700/50 transition-colors w-64"
				aria-label="Search"
				title="Search (Ctrl+K)"
			>
				<Search className="h-3.5 w-3.5" />
				<span className="truncate">Search rooms, projects, standards...</span>
			</button>

			<div className="h-5 w-px bg-slate-700/50" />

			{/* Status icons */}
			<button
				className="p-1.5 text-slate-400 hover:text-white transition-colors rounded"
				aria-label="Theme"
				title="Toggle theme"
			>
				<Sun className="h-4 w-4" />
			</button>

			<ContextualHelpButton />

			<button
				onClick={onHelpOpen}
				className="p-1.5 text-slate-400 hover:text-white transition-colors rounded"
				aria-label="Help"
				data-onboarding="help-button"
				title="Global help (F1)"
			>
				<HelpCircle className="h-4 w-4" />
			</button>

			<button
				className="p-1.5 text-slate-400 hover:text-white transition-colors rounded relative"
				aria-label="Notifications"
				title="Notifications"
			>
				<Bell className="h-4 w-4" />
				<span className="absolute top-1 right-1 h-1.5 w-1.5 bg-red-500 rounded-full" />
			</button>

			{/* Connection status badge */}
			{!isConnected && (
				<span className="px-2 py-0.5 bg-red-500/20 border border-red-500/50 text-red-400 text-[10px] font-medium rounded">
					Backend Offline
				</span>
			)}

			<div className="h-5 w-px bg-slate-700/50" />

			{/* Language selector */}
			<div className="relative" ref={langRef}>
				<button
					onClick={() => setLangOpen(!langOpen)}
					className="flex items-center gap-1 px-1.5 py-1 text-slate-400 hover:text-white transition-colors text-xs rounded"
					aria-label="Change language"
				>
					<Globe className="h-4 w-4" />
					{currentLanguage.toUpperCase()}
				</button>
				{langOpen && (
					<div className="absolute right-0 top-full mt-1 bg-slate-800 border border-slate-700/50 rounded shadow-lg z-50 min-w-[120px]">
						{["en", "ar"].map((lang) => (
							<button
								key={lang}
								onClick={() => {
									onLanguageChange(lang);
									setLangOpen(false);
								}}
								className={`block w-full text-left px-3 py-1.5 text-xs transition-colors ${
									currentLanguage === lang
										? "text-orange-500 bg-orange-500/10"
										: "text-slate-300 hover:bg-slate-700/50"
								}`}
							>
								{lang === "en" ? "English" : "العربية"}
							</button>
						))}
					</div>
				)}
			</div>

			<div className="h-5 w-px bg-slate-700/50" />

			{/* User profile */}
			<UserMenu />
		</header>
	);
};

export default TopBar;
