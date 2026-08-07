/**
 * EnvironmentPage.tsx — Environmental Context (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   GET /api/v1/environment/weather?lat=&lon=    — real weather from open-meteo
 *   GET /api/v1/environment/context?lat=&lon=    — full environmental context
 *   GET /api/v1/environment/air-quality?lat=&lon= — air quality data
 *   GET /api/v1/environment/elevation?lat=&lon=  — elevation data
 *
 * No hardcoded data — all values from live API responses.
 */
import { CloudSun, Loader2, MapPin, RefreshCw, Wind } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getApiKey } from "@/services/apiKey";

interface WeatherData {
	success: boolean;
	data: {
		temperature_c: number;
		wind_speed_m_s: number;
		relative_humidity_pct: number;
		outdoor_temp_c: number;
		air_density_kg_m3: number;
		temperature_k: number;
		source: string;
		is_default: boolean;
		is_stale: boolean;
		fetched_at: string;
		location: { latitude: number; longitude: number };
	};
}

interface EnvironmentContext {
	success: boolean;
	data?: Record<string, unknown>;
	error?: string;
}

const API_BASE = "/api/v1";

async function apiCall<T>(path: string): Promise<T> {
	const headers: Record<string, string> = {};
	const apiKey = getApiKey();
	if (apiKey) headers["X-API-Key"] = apiKey;
	const resp = await fetch(`${API_BASE}${path}`, { headers });
	if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
	return resp.json();
}

export function EnvironmentPage() {
	const [lat, setLat] = useState("30.04"); // Cairo default
	const [lon, setLon] = useState("31.24");
	const [weather, setWeather] = useState<WeatherData | null>(null);
	const [context, setContext] = useState<EnvironmentContext | null>(null);
	const [loading, setLoading] = useState(false);

	const fetchAll = useCallback(async () => {
		setLoading(true);
		try {
			const [w, c] = await Promise.all([
				apiCall<WeatherData>(`/environment/weather?lat=${lat}&lon=${lon}`),
				apiCall<EnvironmentContext>(`/environment/context?lat=${lat}&lon=${lon}`).catch((e) => ({
					success: false,
					error: e instanceof Error ? e.message : "Unknown",
				})),
			]);
			setWeather(w);
			setContext(c);
		} catch (err) {
			toast.error(`Failed to load environment data: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	}, [lat, lon]);

	useEffect(() => {
		fetchAll();
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-5xl mx-auto space-y-6">
				<div>
					<h1 className="text-2xl font-bold text-white">Environmental Context</h1>
					<p className="text-sm text-slate-400 mt-1">
						Real weather · Air quality · Elevation · Live API from open-meteo
					</p>
				</div>

				{/* Location input */}
				<Card className="bg-[#1E293B] border-[#334155]">
					<CardHeader>
						<CardTitle className="text-white flex items-center gap-2">
							<MapPin className="h-5 w-5 text-[#38BDF8]" />
							Location
						</CardTitle>
					</CardHeader>
					<CardContent>
						<div className="grid grid-cols-3 gap-4 items-end">
							<div>
								<Label className="text-slate-400 text-xs">Latitude</Label>
								<Input
									value={lat}
									onChange={(e) => setLat(e.target.value)}
									className="bg-[#0F172A] border-[#334155] text-white font-mono"
								/>
							</div>
							<div>
								<Label className="text-slate-400 text-xs">Longitude</Label>
								<Input
									value={lon}
									onChange={(e) => setLon(e.target.value)}
									className="bg-[#0F172A] border-[#334155] text-white font-mono"
								/>
							</div>
							<Button
								onClick={fetchAll}
								disabled={loading}
								className="bg-[#E84040] hover:bg-[#B91C1C] text-white"
							>
								{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
								Fetch Data
							</Button>
						</div>
					</CardContent>
				</Card>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#38BDF8]" />
					</div>
				) : weather ? (
					<>
						{/* Weather — REAL data */}
						<div className="grid grid-cols-4 gap-4">
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<CloudSun className="h-8 w-8 text-[#F59E0B] mb-2" />
									<p className="text-2xl font-bold text-white">
										{weather.data.temperature_c.toFixed(1)}°C
									</p>
									<p className="text-xs text-slate-400">Temperature</p>
								</CardContent>
							</Card>

							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<Wind className="h-8 w-8 text-[#38BDF8] mb-2" />
									<p className="text-2xl font-bold text-white">
										{weather.data.wind_speed_m_s.toFixed(1)}
									</p>
									<p className="text-xs text-slate-400">Wind (m/s)</p>
								</CardContent>
							</Card>

							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-2xl font-bold text-white">
										{weather.data.relative_humidity_pct.toFixed(0)}%
									</p>
									<p className="text-xs text-slate-400">Humidity</p>
								</CardContent>
							</Card>

							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-2xl font-bold text-white font-mono">
										{weather.data.air_density_kg_m3.toFixed(3)}
									</p>
									<p className="text-xs text-slate-400">Air Density (kg/m³)</p>
								</CardContent>
							</Card>
						</div>

						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white text-base">Weather Details</CardTitle>
								<CardDescription>
									Source: {weather.data.source} · Fetched: {new Date(weather.data.fetched_at).toLocaleString()}
								</CardDescription>
							</CardHeader>
							<CardContent>
								<div className="grid grid-cols-2 gap-4 text-sm">
									<div className="flex justify-between">
										<span className="text-slate-400">Temperature (K)</span>
										<span className="text-white font-mono">{weather.data.temperature_k.toFixed(2)} K</span>
									</div>
									<div className="flex justify-between">
										<span className="text-slate-400">Location</span>
										<span className="text-white font-mono">
											{weather.data.location.latitude}, {weather.data.location.longitude}
										</span>
									</div>
									<div className="flex justify-between">
										<span className="text-slate-400">Is Default</span>
										<span className="text-white">{weather.data.is_default ? "Yes" : "No"}</span>
									</div>
									<div className="flex justify-between">
										<span className="text-slate-400">Is Stale</span>
										<span className={weather.data.is_stale ? "text-[#F59E0B]" : "text-[#22C55E]"}>
											{weather.data.is_stale ? "Yes" : "No"}
										</span>
									</div>
								</div>
							</CardContent>
						</Card>

						{context && (
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardHeader>
									<CardTitle className="text-white text-base">Full Environmental Context</CardTitle>
								</CardHeader>
								<CardContent>
									{context.success ? (
										<pre className="text-xs text-slate-300 font-mono overflow-x-auto bg-[#0F172A] p-4 rounded-md border border-[#334155]">
											{JSON.stringify(context.data, null, 2)}
										</pre>
									) : (
										<p className="text-sm text-[#F59E0B]">
											⚠ {context.error || "Failed to load context"}
										</p>
									)}
								</CardContent>
							</Card>
						)}
					</>
				) : null}
			</div>
		</div>
	);
}
