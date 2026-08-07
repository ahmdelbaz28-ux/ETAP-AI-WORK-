/**
 * TopBar.tsx — BAZSPARK V8.1 Production Top Header
 *
 * Per V8.1 Stitch-Ready UI Prompt (h=64px):
 *   Left: Breadcrumb (Home > PageName)
 *   Center: Global search bar (max-width 400px, ⌘K badge)
 *   Right:
 *     - AI Agent button (BrainCircuit, purple glow if suggestions)
 *     - Notifications bell (badge with count, red pulse if >0)
 *     - System health indicator (green dot + "System Online")
 *     - User avatar dropdown
 */
import { Bell, BrainCircuit, ChevronRight, Globe, HelpCircle, Search } from "lucide-react";
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
	"/ai-agent": "AI Agent",
	"/digital-twin": "Digital Twin",
	"/bim-import": "BIM Import",
	"/facp": "FACP Design",
	"/settings": "Settings",
	"/audit-log": "Audit Log",
	"/self-healing": "Self-Healing",
	"/marine": "Vessel Overview",
	"/marine/zones": "Zone Mapping",
	"/marine/detectors": "Detector Grid",
	"/marine/gas": "Gas / UGLD",
	"/marine/pa": "PA / Alarm Zones",
	"/marine/compliance": "Class Compliance",
	"/engineering": "Engineering",
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

	// V8.1: AI suggestion count (would come from useAIAgent hook in production)
	const aiSuggestionCount = 3;
	const notificationCount = 5;

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
		<header className="h-16 bg-[#0F172A] border-b border-[#334155] flex items-center px-6 gap-4 shrink-0">
			{/* Left: Breadcrumb */}
			<nav className="flex items-center gap-2 text-sm shrink-0">
				<Link
					to="/dashboard"
					className="text-slate-400 hover:text-white transition-colors"
				>
					Home
				</Link>
				<ChevronRight className="h-3.5 w-3.5 text-slate-600" />
				<span className="text-white font-medium">{pageName}</span>
			</nav>

			<div className="flex-1 flex justify-center">
				{/* Center: Global search bar */}
				<button
					onClick={onSearchOpen}
					className="flex items-center gap-2 px-4 h-9 bg-[#1E293B] border border-[#334155] rounded-full text-slate-400 text-sm hover:bg-[#334155] transition-colors w-full max-w-[400px]"
					aria-label="Search"
					title="Search (⌘K)"
				>
					<Search className="h-4 w-4 shrink-0" />
					<span className="truncate flex-1 text-left">
						Search rooms, projects, standards...
					</span>
					<kbd className="text-[10px] font-mono bg-[#334155] px-1.5 py-0.5 rounded text-slate-300 shrink-0">
						⌘K
					</kbd>
				</button>
			</div>

			{/* Right: Action buttons */}
			<div className="flex items-center gap-2 shrink-0">
				{/* AI Agent button — purple glow if suggestions pending */}
				<Link
					to="/ai-agent"
					className={`relative flex items-center gap-2 px-3 h-9 rounded-md transition-all duration-150 ${
						aiSuggestionCount > 0
							? "bg-[#A78BFA]/10 text-[#A78BFA] ai-glow"
							: "bg-[#1E293B] text-slate-400 hover:text-white"
					}`}
					aria-label="AI Agent"
					title="AI Engineering Agent (⌘⇧A)"
				>
					<BrainCircuit className="h-4 w-4" />
					{aiSuggestionCount > 0 && (
						<span className="absolute -top-1 -right-1 h-4 min-w-4 px-1 bg-[#E84040] rounded-full text-[10px] font-bold text-white flex items-center justify-center notification-badge">
							{aiSuggestionCount}
						</span>
					)}
				</Link>

				{/* Notifications bell — badge with count, red pulse if >0 */}
				<button
					className="relative p-2 text-slate-400 hover:text-white transition-colors rounded-md hover:bg-[#1E293B]"
					aria-label="Notifications"
					title="Notifications"
				>
					<Bell className="h-4 w-4" />
					{notificationCount > 0 && (
						<span className="absolute top-1 right-1 h-3.5 min-w-3.5 px-1 bg-[#E84040] rounded-full text-[9px] font-bold text-white flex items-center justify-center notification-badge">
							{notificationCount}
						</span>
					)}
				</button>

				<ContextualHelpButton />

				<button
					onClick={onHelpOpen}
					className="p-2 text-slate-400 hover:text-white transition-colors rounded-md hover:bg-[#1E293B]"
					aria-label="Help"
					data-onboarding="help-button"
					title="Global help (F1)"
				>
					<HelpCircle className="h-4 w-4" />
				</button>

				{/* System health indicator */}
				<div className="flex items-center gap-1.5 px-2">
					<span
						className={`h-2 w-2 rounded-full ${
							isConnected
								? "bg-[#22C55E] shadow-[0_0_8px_rgba(34,197,94,0.5)]"
								: "bg-[#EF4444] shadow-[0_0_8px_rgba(239,68,68,0.5)]"
						}`}
					/>
					{!isConnected ? (
						<span className="text-caption text-[#EF4444]">Backend Offline</span>
					) : (
						<span className="text-xs text-slate-400 hidden lg:inline">System Online</span>
					)}
				</div>

				<div className="h-5 w-px bg-[#334155]" />

				{/* Language selector */}
				<div className="relative" ref={langRef}>
					<button
						onClick={() => setLangOpen(!langOpen)}
						className="flex items-center gap-1 px-2 h-9 text-slate-400 hover:text-white transition-colors text-xs rounded-md hover:bg-[#1E293B]"
						aria-label="Change language"
					>
						<Globe className="h-4 w-4" />
						{currentLanguage.toUpperCase()}
					</button>
					{langOpen && (
						<div className="absolute right-0 top-full mt-1 bg-[#1E293B] border border-[#334155] rounded-md shadow-lg z-50 min-w-[120px]">
							{["en", "ar"].map((lang) => (
								<button
									key={lang}
									onClick={() => {
										onLanguageChange(lang);
										setLangOpen(false);
									}}
									className={`block w-full text-left px-3 py-2 text-xs transition-colors first:rounded-t-md last:rounded-b-md ${
										currentLanguage === lang
											? "text-[#E84040] bg-[#E84040]/10"
											: "text-slate-300 hover:bg-[#334155]"
									}`}
								>
									{lang === "en" ? "English" : "العربية"}
								</button>
							))}
						</div>
					)}
				</div>

				<div className="h-5 w-px bg-[#334155]" />

				{/* User avatar dropdown */}
				<UserMenu />
			</div>
		</header>
	);
};

export default TopBar;
