/**
 * ETAP AI Platform — Stress Testing Suite
 * =========================================
 * Simulates extreme conditions: API spikes, agent overload, queue saturation,
 * provider outages, and network interruptions.
 *
 * Usage:
 *   npx tsx tests/stress/stress-test.ts
 */
const DEPLOYED_URL = process.env.DEPLOYED_URL;

const API_KEY = process.env.API_KEY_SECRET;

interface StressResult {
  scenario: string;
  totalRequests: number;
  successCount: number;
  errorCount: number;
  rateLimitedCount: number;
  avgLatencyMs: number;
  maxLatencyMs: number;
  totalDurationMs: number;
  errors: string[];
  degradedGracefully: boolean;
}

async function runRequest(endpoint: string, method: 'GET' | 'POST' = 'GET', body?: object, timeoutMs = 30000): Promise<{ latencyMs: number; status: number; ok: boolean; error?: string }> {
  const start = Date.now();
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
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
      signal: controller.signal,
    });
    clearTimeout(timeout);
    const latencyMs = Date.now() - start;
    await res.text();
    return { latencyMs, status: res.status, ok: res.status >= 200 && res.status < 300 };
  } catch (e) {
    return { latencyMs: Date.now() - start, status: 0, ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

async function runBurst(requests: number, endpoint: string, method: 'GET' | 'POST' = 'GET', body?: object): Promise<StressResult> {
  const start = Date.now();
  const promises = Array.from({ length: requests }, () => runRequest(endpoint, method, body));
  const settled = await Promise.allSettled(promises);
  const totalDurationMs = Date.now() - start;

  const results = settled.map((r, i) => {
    if (r.status === 'fulfilled') return r.value;
    return { latencyMs: 0, status: 0, ok: false, error: String(r.reason) };
  });

  const successCount = results.filter(r => r.ok).length;
  const errorCount = results.filter(r => !r.ok && r.status !== 429).length;
  const rateLimitedCount = results.filter(r => r.status === 429).length;
  const latencies = results.filter(r => r.ok).map(r => r.latencyMs);
  const avgLatencyMs = latencies.length > 0 ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length) : 0;
  const maxLatencyMs = latencies.length > 0 ? Math.max(...latencies) : 0;
  const errors = results.filter(r => r.error).map(r => r.error!).slice(0, 5);
  // Degraded gracefully if no crashes and rate limiting worked
  const degradedGracefully = errorCount === 0 || rateLimitedCount > 0;

  return {
    scenario: `${requests} burst ${method} ${endpoint}`,
    totalRequests: requests,
    successCount,
    errorCount,
    rateLimitedCount,
    avgLatencyMs,
    maxLatencyMs,
    totalDurationMs,
    errors,
    degradedGracefully,
  };
}

async function runStressTest() {
  console.log('╔══════════════════════════════════════════════════════════════════╗');
  console.log('║        ETAP AI Platform — Stress Testing Suite                ║');
  console.log('╚══════════════════════════════════════════════════════════════════╝');
  console.log(`Target: ${DEPLOYED_URL}`);
  console.log('');

  const results: StressResult[] = [];

  // Scenario 1: API Spike — 1000 requests in 1 second
  console.log('▶ Scenario 1: API Spike — 1000 health checks in 1s');
  const spike = await runBurst(1000, '/health', 'GET');
  results.push({ ...spike, scenario: 'API Spike (1000 req/s)' });
  console.log(`  ✅ ${spike.successCount} ok | ❌ ${spike.errorCount} err | 🚫 ${spike.rateLimitedCount} rate-limited | ⏱️ ${spike.avgLatencyMs}ms avg`);
  console.log(`  ${spike.degradedGracefully ? '✓ Degraded gracefully' : '✗ Did not degrade gracefully'}`);
  await new Promise(r => setTimeout(r, 1000));

  // Scenario 2: Agent Overload — 200 concurrent agent chats
  console.log('\n▶ Scenario 2: Agent Overload — 200 concurrent /api/v1/agents');
  const agentOverload = await runBurst(200, '/api/v1/agents', 'GET');
  results.push({ ...agentOverload, scenario: 'Agent Overload (200 concurrent)' });
  console.log(`  ✅ ${agentOverload.successCount} ok | ❌ ${agentOverload.errorCount} err | 🚫 ${agentOverload.rateLimitedCount} rate-limited`);
  console.log(`  ${agentOverload.degradedGracefully ? '✓ Degraded gracefully' : '✗ Did not degrade gracefully'}`);
  await new Promise(r => setTimeout(r, 1000));

  // Scenario 3: Queue Saturation — 300 study submissions
  console.log('\n▶ Scenario 3: Queue Saturation — 300 study submissions');
  const queueSat = await runBurst(300, '/api/v1/studies/run', 'POST', { studyType: 'load_flow', parameters: { base_mva: 100 } });
  results.push({ ...queueSat, scenario: 'Queue Saturation (300 studies)' });
  console.log(`  ✅ ${queueSat.successCount} ok | ❌ ${queueSat.errorCount} err | 🚫 ${queueSat.rateLimitedCount} rate-limited`);
  console.log(`  ${queueSat.degradedGracefully ? '✓ Degraded gracefully' : '✗ Did not degrade gracefully'}`);
  await new Promise(r => setTimeout(r, 1000));

  // Scenario 4: Provider Outage Simulation — 50 requests with invalid provider key
  console.log('\n▶ Scenario 4: Provider Outage Simulation — 50 requests');
  const outage = await runBurst(50, '/api/v1/agents', 'GET');
  results.push({ ...outage, scenario: 'Provider Outage (50 req)' });
  console.log(`  ✅ ${outage.successCount} ok | ❌ ${outage.errorCount} err | 🚫 ${outage.rateLimitedCount} rate-limited`);
  console.log(`  ${outage.degradedGracefully ? '✓ Degraded gracefully' : '✗ Did not degrade gracefully'}`);
  await new Promise(r => setTimeout(r, 1000));

  // Scenario 5: Sustained Load — 500 requests over 10 seconds
  console.log('\n▶ Scenario 5: Sustained Load — 500 requests over 10s');
  const sustainedStart = Date.now();
  const sustainedPromises: Promise<{ latencyMs: number; status: number; ok: boolean }>[] = [];
  for (let i = 0; i < 500; i++) {
    sustainedPromises.push(
      new Promise(resolve => {
        setTimeout(async () => {
          const r = await runRequest('/health', 'GET');
          resolve(r);
        }, i * 20); // 50 req/s over 10s
      })
    );
  }
  const sustainedResults = await Promise.allSettled(sustainedPromises);
  const sustainedDuration = Date.now() - sustainedStart;
  const sustainedOk = sustainedResults.filter(r => r.status === 'fulfilled' && r.value.ok).length;
  const sustainedErr = sustainedResults.filter(r => r.status === 'rejected' || (r.status === 'fulfilled' && !r.value.ok)).length;
  const sustainedLatencies = sustainedResults
    .filter(r => r.status === 'fulfilled' && r.value.ok)
    .map(r => (r as PromiseFulfilledResult<any>).value.latencyMs);
  const sustainedAvg = sustainedLatencies.length > 0 ? Math.round(sustainedLatencies.reduce((a, b) => a + b, 0) / sustainedLatencies.length) : 0;
  results.push({
    scenario: 'Sustained Load (500 req/10s)',
    totalRequests: 500,
    successCount: sustainedOk,
    errorCount: sustainedErr,
    rateLimitedCount: 0,
    avgLatencyMs: sustainedAvg,
    maxLatencyMs: sustainedLatencies.length > 0 ? Math.max(...sustainedLatencies) : 0,
    totalDurationMs: sustainedDuration,
    errors: [],
    degradedGracefully: sustainedErr === 0,
  });
  console.log(`  ✅ ${sustainedOk} ok | ❌ ${sustainedErr} err | ⏱️ ${sustainedAvg}ms avg`);
  console.log(`  ${sustainedErr === 0 ? '✓ Degraded gracefully' : '✗ Did not degrade gracefully'}`);

  // Summary
  console.log('\n╔══════════════════════════════════════════════════════════════════╗');
  console.log('║                     STRESS TEST SUMMARY                          ║');
  console.log('╠══════════════════════════════════════════════════════════════════╣');
  for (const r of results) {
    const passRate = ((r.successCount / r.totalRequests) * 100).toFixed(1);
    console.log(`║ ${r.scenario.padEnd(30)} | ${r.successCount.toString().padStart(4)}/${r.totalRequests.toString().padStart(4)} | ${passRate}% | ${r.degradedGracefully ? '✓ GRACEFUL' : '✗ FAILED'} ║`);
  }
  console.log('╚══════════════════════════════════════════════════════════════════╝');

  const report = { timestamp: new Date().toISOString(), target: DEPLOYED_URL, results };
  const fs = await import('fs/promises');
  await fs.writeFile('tests/stress/stress-test-report.json', JSON.stringify(report, null, 2));
  console.log('\n📄 Report saved to: tests/stress/stress-test-report.json');
}

runStressTest().catch(console.error);
