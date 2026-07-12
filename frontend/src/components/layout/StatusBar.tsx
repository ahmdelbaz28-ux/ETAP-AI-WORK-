/**
 * StatusBar.tsx — BAZspark V8.1 Production Status Bar
 *
 * Matches reference design:
 *   Left: "building mode" (red) + CONNECTED (green dot) + API: /api/v1 + PRODUCTION
 *   Right: BAZspark v8.1 Production + NFPA 72-2022 + SOLAS + IMO
 */
import type React from "react";

interface StatusBarProps {
	backendUrl: string;
	isConnected: boolean;
	environment: string;
}

const StatusBar: React.FC<StatusBarProps> = ({
	backendUrl,
	isConnected,
	environment,
}) => {
	return (
		<footer
			className="h-7 bg-slate-900 border-t border-slate-700/50 flex items-center px-3 gap-3 text-xs shrink-0"
			data-onboarding="status-bar"
		>
			{/* Left: building mode + connection + API + env */}
			<span className="text-red-500 font-medium">building mode</span>

			<div className="h-3 w-px bg-slate-700" />

			<div className="flex items-center gap-1.5">
				<span
					className={`h-1.5 w-1.5 rounded-full ${isConnected ? "bg-green-500" : "bg-red-500"}`}
				/>
				<span className={isConnected ? "text-green-500" : "text-red-500"}>
					{isConnected ? "CONNECTED" : "DISCONNECTED"}
				</span>
			</div>

			<div className="h-3 w-px bg-slate-700" />

			<span className="text-slate-400">API: {backendUrl}</span>

			<div className="h-3 w-px bg-slate-700" />

			<span className="text-slate-400 uppercase">{environment}</span>

			<div className="flex-1" />

			{/* Right: version + standards */}
			<span className="text-slate-400">BAZspark v8.1 Production</span>

			<div className="h-3 w-px bg-slate-700" />

			<span className="text-slate-400">NFPA 72-2022</span>

			<div className="h-3 w-px bg-slate-700" />

			<span className="text-slate-400">SOLAS</span>

			<div className="h-3 w-px bg-slate-700" />

			<span className="text-slate-400">IMO</span>
		</footer>
	);
};

export default StatusBar;
