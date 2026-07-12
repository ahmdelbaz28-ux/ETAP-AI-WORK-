/**
 * StatusBar.tsx — BAZSPARK V8.1 Production Status Bar
 *
 * Per V8.1 prompt:
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
			className="h-7 bg-[#0F172A] border-t border-[#334155] flex items-center px-4 gap-3 text-xs shrink-0"
			data-onboarding="status-bar"
		>
			{/* Left: building mode + connection + API + env */}
			<span className="text-[#E84040] font-medium">building mode</span>

			<div className="h-3 w-px bg-[#334155]" />

			<div className="flex items-center gap-1.5">
				<span
					className={`h-1.5 w-1.5 rounded-full ${
						isConnected
							? "bg-[#22C55E] shadow-[0_0_6px_rgba(34,197,94,0.6)]"
							: "bg-[#EF4444] shadow-[0_0_6px_rgba(239,68,68,0.6)]"
					}`}
				/>
				<span className={isConnected ? "text-[#22C55E]" : "text-[#EF4444]"}>
					{isConnected ? "CONNECTED" : "DISCONNECTED"}
				</span>
			</div>

			<div className="h-3 w-px bg-[#334155]" />

			<span className="text-slate-400">API: {backendUrl}</span>

			<div className="h-3 w-px bg-[#334155]" />

			<span className="text-slate-400 uppercase">{environment}</span>

			<div className="flex-1" />

			{/* Right: version + standards */}
			<span className="text-slate-400">BAZspark v8.1 Production</span>

			<div className="h-3 w-px bg-[#334155]" />

			<span className="text-slate-400">NFPA 72-2022</span>

			<div className="h-3 w-px bg-[#334155]" />

			<span className="text-slate-400">SOLAS</span>

			<div className="h-3 w-px bg-[#334155]" />

			<span className="text-slate-400">IMO</span>
		</footer>
	);
};

export default StatusBar;
