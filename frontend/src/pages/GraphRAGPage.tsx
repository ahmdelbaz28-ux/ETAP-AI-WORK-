/**
 * GraphRAGPage.tsx — GraphRAG Knowledge Graph (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   GET  /api/v2/graphrag/health    — service health + Neo4j connection
 *   POST /api/v2/graphrag/search     — semantic search
 *   POST /api/v2/graphrag/ask        — Q&A
 *   POST /api/v2/graphrag/knowledge   — add knowledge
 */
import { Brain, Loader2, Network, RefreshCw, Search } from "lucide-react";
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
import { getApiKey } from "@/services/apiKey";

interface GraphRagHealth {
        initialized: boolean;
        neo4j_connected: boolean;
        vector_store: boolean;
        transformer: boolean;
        qa_chain: boolean;
        embedding_model: string;
        embedding_dimensions: number;
        llm_model: string;
        neo4j_uri: string;
}

async function apiCall<T>(path: string, options?: RequestInit): Promise<T> {
        const headers: Record<string, string> = { "Content-Type": "application/json", ...((options?.headers as Record<string, string>) || {}) };
        const apiKey = getApiKey();
        if (apiKey) headers["X-API-Key"] = apiKey;
        const resp = await fetch(path, { ...options, headers });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
}

export function GraphRAGPage() {
        const [health, setHealth] = useState<GraphRagHealth | null>(null);
        const [loading, setLoading] = useState(true);
        const [query, setQuery] = useState("");
        const [results, setResults] = useState<string | null>(null);
        const [searching, setSearching] = useState(false);

        const fetchHealth = useCallback(async () => {
                setLoading(true);
                try {
                        const data = await apiCall<GraphRagHealth>("/api/v2/graphrag/health");
                        setHealth(data);
                } catch (err) {
                        toast.error(`Failed: ${err instanceof Error ? err.message : "Unknown"}`);
                } finally {
                        setLoading(false);
                }
        }, []);

        useEffect(() => {
                fetchHealth();
        }, [fetchHealth]);

        const handleSearch = async () => {
                if (!query.trim()) return;
                setSearching(true);
                try {
                        const data = await apiCall("/api/v2/graphrag/search", {
                                method: "POST",
                                body: JSON.stringify({ query, limit: 5 }),
                        });
                        setResults(JSON.stringify(data, null, 2));
                } catch (err) {
                        toast.error(`Search failed: ${err instanceof Error ? err.message : "Unknown"}`);
                } finally {
                        setSearching(false);
                }
        };

        return (
                <div className="flex-1 overflow-auto p-6">
                        <div className="max-w-5xl mx-auto space-y-6">
                                <div className="flex items-center justify-between">
                                        <div>
                                                <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                                                        <Network className="h-6 w-6 text-[#A78BFA]" />
                                                        GraphRAG
                                                </h1>
                                                <p className="text-sm text-slate-400 mt-1">Knowledge graph · Neo4j · Real API</p>
                                        </div>
                                        <Button variant="outline" onClick={fetchHealth} disabled={loading} className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
                                                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                                        </Button>
                                </div>

                                {loading ? (
                                        <div className="flex items-center justify-center py-12">
                                                <Loader2 className="h-8 w-8 animate-spin text-[#A78BFA]" />
                                        </div>
                                ) : health ? (
                                        <>
                                                <Card className="bg-[#1E293B] border-[#334155]">
                                                        <CardHeader>
                                                                <CardTitle className="text-white flex items-center gap-2">
                                                                        <Brain className="h-5 w-5 text-[#A78BFA]" />
                                                                        Service Health
                                                                </CardTitle>
                                                        </CardHeader>
                                                        <CardContent>
                                                                <div className="grid grid-cols-3 gap-4 text-sm">
                                                                        <div className="flex items-center gap-2">
                                                                                <span className={health.initialized ? "text-[#22C55E]" : "text-[#E84040]"}>{health.initialized ? "✓" : "✗"}</span>
                                                                                <span className="text-slate-300">Initialized</span>
                                                                        </div>
                                                                        <div className="flex items-center gap-2">
                                                                                <span className={health.neo4j_connected ? "text-[#22C55E]" : "text-[#E84040]"}>{health.neo4j_connected ? "✓" : "✗"}</span>
                                                                                <span className="text-slate-300">Neo4j Connected</span>
                                                                        </div>
                                                                        <div className="flex items-center gap-2">
                                                                                <span className={health.vector_store ? "text-[#22C55E]" : "text-[#E84040]"}>{health.vector_store ? "✓" : "✗"}</span>
                                                                                <span className="text-slate-300">Vector Store</span>
                                                                        </div>
                                                                        <div className="flex items-center gap-2">
                                                                                <span className={health.transformer ? "text-[#22C55E]" : "text-[#E84040]"}>{health.transformer ? "✓" : "✗"}</span>
                                                                                <span className="text-slate-300">Transformer</span>
                                                                        </div>
                                                                        <div className="flex items-center gap-2">
                                                                                <span className={health.qa_chain ? "text-[#22C55E]" : "text-[#E84040]"}>{health.qa_chain ? "✓" : "✗"}</span>
                                                                                <span className="text-slate-300">QA Chain</span>
                                                                        </div>
                                                                        <div><span className="text-slate-400">Dims:</span> <span className="text-white font-mono">{health.embedding_dimensions}</span></div>
                                                                </div>
                                                                <div className="mt-4 flex flex-wrap gap-2">
                                                                        <Badge className="bg-[#A78BFA]/10 text-[#A78BFA]">LLM: {health.llm_model}</Badge>
                                                                        <Badge className="bg-[#38BDF8]/10 text-[#38BDF8]">Embed: {health.embedding_model}</Badge>
                                                                        <Badge className="bg-slate-700 text-slate-300">Neo4j: {health.neo4j_uri}</Badge>
                                                                </div>
                                                        </CardContent>
                                                </Card>

                                                <Card className="bg-[#1E293B] border-[#334155]">
                                                        <CardHeader>
                                                                <CardTitle className="text-white text-base">Semantic Search</CardTitle>
                                                        </CardHeader>
                                                        <CardContent>
                                                                <div className="flex gap-2">
                                                                        <Input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleSearch()} placeholder="Search knowledge graph..." className="bg-[#0F172A] border-[#334155] text-white" />
                                                                        <Button onClick={handleSearch} disabled={searching} className="bg-[#A78BFA] hover:bg-[#A78BFA]/80 text-white">
                                                                                {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                                                                        </Button>
                                                                </div>
                                                                {results && (
                                                                        <pre className="mt-4 text-xs text-slate-300 font-mono overflow-x-auto bg-[#0F172A] p-4 rounded-md border border-[#334155]">
                                                                                {results}
                                                                        </pre>
                                                                )}
                                                        </CardContent>
                                                </Card>
                                        </>
                                ) : null}
                        </div>
                </div>
        );
}
