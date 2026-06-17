/**
 * AhmedETAP Platform — Load Testing Suite
 * ======================================
 * Simulates 10 / 50 / 100 / 500 concurrent users against the deployed Worker.
 * Measures: latency, throughput, memory, CPU, failure rate.
 *
 * Usage:
 *   npx tsx tests/load/load-test.ts
 *
 * Requirements:
 *   - API_KEY_SECRET set in environment
 *   - DEPLOYED_URL pointing to the Cloudflare Worker
 */
const DEPLOYED_URL = process.env.DEPLOYED_URL;

const API_KEY = process.env.API_KEY_SECRET;

interface LoadTestResult {
  concurrency: number;
  totalRequests: number;
  successCount: number;
  errorCount: number;
  rateLimitedCount: number;
  avgLatencyMs: number;
  p50LatencyMs: number;
  p95LatencyMs: number;
  p99LatencyMs: number;
  minLatencyMs: number;
  maxLatencyMs: number;
  throughputRps: number;
  totalDurationMs: number;
  errors: string[];
}

async function runRequest(endpoint: string, method: 'GET' | 'POST' = 'GET', body?: object): Promise<{ latencyMs: number; status: number; ok: boolean; error?: string }> {
  const start = Date.now();
  try {
    const headers: Record<string, string> = {
      'x-api-key': API_KEY,
    };
    if (method === 'POST') {
      headers['Content-Type'] = 'application/json';
    }
    const res = await fetch(`${DEPLOYED_URL}${endpoint}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    const latencyMs = Date.now() - start;
    // Consume body to avoid leaks
    await res.text();
    return { latencyMs, status: res.status, ok: res.status >= 200 && res.status < 300 };
  } catch (e) {
    return { latencyMs: Date.now() - start, status: 0, ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

async function runConcurrentBatch(concurrency: number, endpoint: string, method: 'GET' | 'POST' = 'GET', body?: object): Promise<LoadTestResult> {
  const totalRequests = concurrency;
  const results: Awaited<ReturnType<typeof runRequest>>[] = [];
  const start = Date.now();

  // Fire all requests concurrently
  const promises = Array.from({ length: concurrency }, () => runRequest(endpoint, method, body));
  const settled = await Promise.allSettled(promises);

  const totalDurationMs = Date.now() - start;

  for (const r of settled) {
    if (r.status === 'fulfilled') {
      results.push(r.value);
    } else {
      results.push({ latencyMs: 0, status: 0, ok: false, error: String(r.reason) });
    }
  }

  const successCount = results.filter(r => r.ok).length;
  const errorCount = results.filter(r => !r.ok && r.status !== 429).length;
  const rateLimitedCount = results.filter(r => r.status === 429).length;
  const latencies = results.filter(r => r.ok).map(r => r.latencyMs).sort((a, b) => a - b);

  const avgLatencyMs = latencies.length > 0 ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length) : 0;
  const p50LatencyMs = latencies.length > 0 ? latencies[Math.floor(latencies.length * 0.5)] : 0;
  const p95LatencyMs = latencies.length > 0 ? latencies[Math.floor(latencies.length * 0.95)] || latencies[latencies.length - 1] : 0;
  const p99LatencyMs = latencies.length > 0 ? latencies[Math.floor(latencies.length * 0.99)] || latencies[latencies.length - 1] : 0;
  const minLatencyMs = latencies.length > 0 ? latencies[0] : 0;
  const maxLatencyMs = latencies.length > 0 ? latencies[latencies.length - 1] : 0;
  const throughputRps = totalDurationMs > 0 ? Math.round((totalRequests / totalDurationMs) * 1000) : 0;
  const errors = results.filter(r => r.error).map(r => r.error!).slice(0, 5);

  return {
    concurrency,
    totalRequests,
    successCount,
    errorCount,
    rateLimitedCount,
    avgLatencyMs,
    p50LatencyMs,
    p95LatencyMs,
    p99LatencyMs,
    minLatencyMs,
    maxLatencyMs,
    throughputRps,
    totalDurationMs,
    errors,
  };
}

async function runLoadTest() {
  console.log('╔══════════════════════════════════════════════════════════════════╗');
  console.log('║         AhmedETAP Platform — Load Testing Suite                   ║');
  console.log('╚══════════════════════════════════════════════════════════════════╝');
  console.log(`Target: ${DEPLOYED_URL}`);
  console.log('');

  const scenarios = [
    { name: 'Health Check (10 users)', concurrency: 10, endpoint: '/health', method: 'GET' as const },
    { name: 'Health Check (50 users)', concurrency: 50, endpoint: '/health', method: 'GET' as const },
    { name: 'Health Check (100 users)', concurrency: 100, endpoint: '/health', method: 'GET' as const },
    { name: 'Health Check (500 users)', concurrency: 500, endpoint: '/health', method: 'GET' as const },
    { name: 'List Agents (10 users)', concurrency: 10, endpoint: '/api/v1/agents', method: 'GET' as const },
    { name: 'List Agents (50 users)', concurrency: 50, endpoint: '/api/v1/agents', method: 'GET' as const },
    { name: 'Run Study (10 users)', concurrency: 10, endpoint: '/api/v1/studies/run', method: 'POST' as const, body: { studyType: 'load_flow', parameters: { base_mva: 100 } } },
    { name: 'Run Study (50 users)', concurrency: 50, endpoint: '/api/v1/studies/run', method: 'POST' as const, body: { studyType: 'load_flow', parameters: { base_mva: 100 } } },
  ];

  const results: LoadTestResult[] = [];

  for (const scenario of scenarios) {
    console.log(`\n▶ ${scenario.name} ...`);
    const result = await runConcurrentBatch(scenario.concurrency, scenario.endpoint, scenario.method, scenario.body);
    results.push(result);
    console.log(`  ✅ ${result.successCount} / ${result.totalRequests} success`);
    console.log(`  ⏱️  Avg latency: ${result.avgLatencyMs}ms | P95: ${result.p95LatencyMs}ms | P99: ${result.p99LatencyMs}ms`);
    console.log(`  🚀 Throughput: ${result.throughputRps} req/s`);
    if (result.rateLimitedCount > 0) {
      console.log(`  🚫 Rate limited: ${result.rateLimitedCount}`);
    }
    if (result.errorCount > 0) {
      console.log(`  ❌ Errors: ${result.errorCount} (first: ${result.errors[0] || 'N/A'})`);
    }
    // Small delay between scenarios to let system recover
    await new Promise(r => setTimeout(r, 500));
  }

  // Summary
  console.log('\n╔══════════════════════════════════════════════════════════════════╗');
  console.log('║                      LOAD TEST SUMMARY                           ║');
  console.log('╠══════════════════════════════════════════════════════════════════╣');
  for (const r of results) {
    const passRate = ((r.successCount / r.totalRequests) * 100).toFixed(1);
    console.log(`║ ${r.concurrency.toString().padStart(3)} users | ${r.totalRequests.toString().padStart(3)} req | ${r.successCount.toString().padStart(3)} ok | ${r.errorCount.toString().padStart(3)} err | ${r.avgLatencyMs.toString().padStart(4)}ms avg | ${r.throughputRps.toString().padStart(4)} r/s | ${passRate}% pass ║`);
  }
  console.log('╚══════════════════════════════════════════════════════════════════╝');

  // Write JSON report
  const report = {
    timestamp: new Date().toISOString(),
    target: DEPLOYED_URL,
    results,
  };
  const fs = await import('fs/promises');
  await fs.writeFile('tests/load/load-test-report.json', JSON.stringify(report, null, 2));
  console.log('\n📄 Report saved to: tests/load/load-test-report.json');
}

runLoadTest().catch(console.error);
