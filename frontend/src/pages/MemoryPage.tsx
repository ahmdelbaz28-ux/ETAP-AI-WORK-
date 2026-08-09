/**
 * MemoryPage.tsx — AI Memory Service (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   GET  /api/v1/memory/status  — service initialization + provider info
 *   GET  /api/v1/memory/all     — all stored memories
 *   POST /api/v1/memory/search  — semantic search
 *   POST /api/v1/memory/add     — add new memory
 *   DELETE /api/v1/memory/{id}  — delete memory
 *
 * No hardcoded data — all values from live API responses.
 */
import { Brain, Loader2, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
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

interface MemoryStatus {
	success: boolean;
	status: {
		initialized: boolean;
		provider: string;
		vector_store: string;
		llm_provider: string;
		embedder_provider: string;
		embedding_dims: number;
		error: string | null;
	};
	disclaimer: string;
}

interface MemoryAll {
	success: boolean;
	error: string | null;
	results: Array<{
		id: string;
		content: string;
		metadata: Record<string, unknown>;
		score?: number;
	}>;
	source: string;
	disclaimer: string;
}

const API_BASE = "/api/v1";

async function apiCall<T>(path: string, options?: RequestInit): Promise<T> {
	const headers: Record<string, string> = {
		"Content-Type": "application/json",
		...((options?.headers as Record<string, string>) || {}),
	};
	const apiKey = getApiKey();
	if (apiKey) headers["X-API-Key"] = apiKey;
	const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
	if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
	return resp.json();
}

export function MemoryPage() {
	const [status, setStatus] = useState<MemoryStatus | null>(null);
	const [memories, setMemories] = useState<MemoryAll | null>(null);
	const [loading, setLoading] = useState(true);
	const [searchQuery, setSearchQuery] = useState("");
	const [searchResults, setSearchResults] = useState<MemoryAll | null>(null);
	const [newMemory, setNewMemory] = useState("");

	const fetchAll = useCallback(async () => {
		setLoading(true);
		try {
			const [s, m] = await Promise.all([
				apiCall<MemoryStatus>("/memory/status"),
				apiCall<MemoryAll>("/memory/all"),
			]);
			setStatus(s);
			setMemories(m);
		} catch (err) {
			toast.error(`Failed to load memory data: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchAll();
	}, [fetchAll]);

	const handleSearch = async () => {
		if (!searchQuery.trim()) return;
		try {
			const results = await apiCall<MemoryAll>("/memory/search", {
				method: "POST",
				body: JSON.stringify({ query: searchQuery, limit: 10 }),
			});
			setSearchResults(results);
		} catch (err) {
			toast.error(`Search failed: ${err instanceof Error ? err.message : "Unknown"}`);
		}
	};

	const handleAdd = async () => {
		if (!newMemory.trim()) return;
		try {
			await apiCall("/memory/add", {
				method: "POST",
				body: JSON.stringify({ content: newMemory, metadata: { source: "ui" } }),
			});
			toast.success("Memory added");
			setNewMemory("");
			fetchAll();
		} catch (err) {
			toast.error(`Add failed: ${err instanceof Error ? err.message : "Unknown"}`);
		}
	};

	const handleDelete = async (id: string) => {
		try {
			await apiCall(`/memory/${id}`, { method: "DELETE" });
			toast.success("Memory deleted");
			fetchAll();
		} catch (err) {
			toast.error(`Delete failed: ${err instanceof Error ? err.message : "Unknown"}`);
		}
	};

	const displayMemories = searchResults?.results ?? memories?.results ?? [];

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-5xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold text-white">AI Memory Service</h1>
						<p className="text-sm text-slate-400 mt-1">
							Semantic memory · Real API · Advisory context only
						</p>
					</div>
					<Button
						variant="outline"
						onClick={fetchAll}
						disabled={loading}
						className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]"
					>
						{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
					</Button>
				</div>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#A78BFA]" />
					</div>
				) : (
					<>
						{/* Service status — REAL data */}
						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white flex items-center gap-2">
									<Brain className="h-5 w-5 text-[#A78BFA]" />
									Service Status
								</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="grid grid-cols-3 gap-4 text-sm">
									<div>
										<p className="text-slate-400 text-xs">Initialized</p>
										<p className={status?.status.initialized ? "text-[#22C55E]" : "text-[#F59E0B]"}>
											{status?.status.initialized ? "✓ Yes" : "⚠ No"}
										</p>
									</div>
									<div>
										<p className="text-slate-400 text-xs">Provider</p>
										<p className="text-white font-mono">{status?.status.provider ?? "—"}</p>
									</div>
									<div>
										<p className="text-slate-400 text-xs">Vector Store</p>
										<p className="text-white font-mono">{status?.status.vector_store ?? "—"}</p>
									</div>
									<div>
										<p className="text-slate-400 text-xs">LLM Provider</p>
										<p className="text-white font-mono">{status?.status.llm_provider ?? "—"}</p>
									</div>
									<div>
										<p className="text-slate-400 text-xs">Embedder</p>
										<p className="text-white font-mono">{status?.status.embedder_provider ?? "—"}</p>
									</div>
									<div>
										<p className="text-slate-400 text-xs">Embedding Dims</p>
										<p className="text-white font-mono">{status?.status.embedding_dims ?? 0}</p>
									</div>
								</div>
								{status?.status.error && (
									<div className="mt-4 p-3 bg-[#F59E0B]/10 border border-[#F59E0B]/30 rounded-md">
										<p className="text-xs text-[#F59E0B]">
											⚠ {status.status.error}
										</p>
									</div>
								)}
								{status?.disclaimer && (
									<p className="mt-4 text-[10px] text-slate-500 italic">
										{status.disclaimer}
									</p>
								)}
							</CardContent>
						</Card>

						{/* Add memory */}
						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white text-base">Add Memory</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="flex gap-2">
									<Input
										value={newMemory}
										onChange={(e) => setNewMemory(e.target.value)}
										placeholder="Enter engineering knowledge, code reference, or design pattern..."
										className="bg-[#0F172A] border-[#334155] text-white"
									/>
									<Button onClick={handleAdd} className="bg-[#A78BFA] hover:bg-[#A78BFA]/80 text-white">
										<Plus className="h-4 w-4" />
									</Button>
								</div>
							</CardContent>
						</Card>

						{/* Search */}
						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white text-base">Semantic Search</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="flex gap-2">
									<Input
										value={searchQuery}
										onChange={(e) => setSearchQuery(e.target.value)}
										onKeyDown={(e) => e.key === "Enter" && handleSearch()}
										placeholder="Search memories..."
										className="bg-[#0F172A] border-[#334155] text-white"
									/>
									<Button onClick={handleSearch} className="bg-[#38BDF8] hover:bg-[#38BDF8]/80 text-[#0F172A]">
										<Search className="h-4 w-4" />
									</Button>
								</div>
							</CardContent>
						</Card>

						{/* Memories list — REAL data */}
						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white text-base">
									{searchResults ? "Search Results" : "All Memories"} ({displayMemories.length})
								</CardTitle>
								<CardDescription>
									{memories?.success === false && memories.error
										? memories.error
										: "Real stored memories from the memory service"}
								</CardDescription>
							</CardHeader>
							<CardContent>
								{displayMemories.length > 0 ? (
									<div className="space-y-2">
										{displayMemories.map((mem) => (
											<div
												key={mem.id}
												className="flex items-start gap-3 p-3 bg-[#0F172A] rounded-md border border-[#334155]"
											>
												<div className="flex-1 min-w-0">
													<p className="text-sm text-white">{mem.content}</p>
													{mem.score !== undefined && (
														<Badge className="mt-1 bg-[#A78BFA]/10 text-[#A78BFA]">
															Score: {mem.score.toFixed(3)}
														</Badge>
													)}
												</div>
												<Button
													variant="ghost"
													size="sm"
													onClick={() => handleDelete(mem.id)}
													className="text-[#E84040] hover:text-[#E84040]/80 p-1"
												>
													<Trash2 className="h-4 w-4" />
												</Button>
											</div>
										))}
									</div>
								) : (
									<p className="text-sm text-slate-400 text-center py-6">
										{memories?.error
											? "Memory service not initialized. Configure OPENAI_API_KEY or GEMINI_API_KEY to enable."
											: "No memories stored yet."}
									</p>
								)}
							</CardContent>
						</Card>
					</>
				)}
			</div>
		</div>
	);
}
