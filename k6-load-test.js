// =============================================================================
// AhmedETAP — k6 Load Test Suite
// Comprehensive load testing with multiple scenarios and CI thresholds.
// =============================================================================

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.2/index.js';

// ─── Custom Metrics ──────────────────────────────────────────────────────────

const errorRate = new Rate('errors');
const healthResponseTime = new Trend('health_response_time');
const studyExecutionTime = new Trend('study_execution_time');
const concurrentStudyTime = new Trend('concurrent_study_time');
const studyRequests = new Counter('study_requests_total');
const failedStudyRequests = new Counter('study_requests_failed');

// ─── Configuration ───────────────────────────────────────────────────────────

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const K6_VUS = Number.parseInt(__ENV.K6_VUS || '100', 10);
const K6_DURATION = __ENV.K6_DURATION || '2m';

const API_HEADERS = {
  'Content-Type': 'application/json',
  'x-api-key': __ENV.API_KEY || '',
};

// ─── Test Data ───────────────────────────────────────────────────────────────

const STUDY_TYPES = ['load_flow', 'short_circuit', 'arc_flash', 'protection_coordination'];
const SAMPLE_SYSTEM = {
  base_mva: 100,
  buses: [
    { bus_id: 1, voltage_magnitude: 1.05, bus_type: 'slack', base_kv: 138, generation_power_real: 0, generation_power_imag: 0 },
    { bus_id: 2, voltage_magnitude: 1, bus_type: 'pq', base_kv: 13.8, load_power_real: 50, load_power_imag: 20 },
    { bus_id: 3, voltage_magnitude: 1, bus_type: 'pv', base_kv: 4.16, generation_power_real: 30, voltage_setpoint: 1.02 },
  ],
  lines: [
    { line_id: 1, from_bus_id: 1, to_bus_id: 2, r1: 0.01, x1: 0.05, bshunt1: 0.02 },
    { line_id: 2, from_bus_id: 2, to_bus_id: 3, r1: 0.02, x1: 0.08, bshunt1: 0.01 },
  ],
  generators: [
    { generator_id: 1, bus_id: 1, x1: 0.2, internal_voltage_mag: 1.05 },
    { generator_id: 2, bus_id: 3, x1: 0.15, internal_voltage_mag: 1.02, power_real: 30 },
  ],
  loads: [
    { load_id: 1, bus_id: 2, p_mw: 50, q_mvar: 20 },
  ],
};

// ─── Scenarios & Thresholds ─────────────────────────────────────────────────

export const options = {
  // Scenarios: each targets a different aspect of the system
  scenarios: {
    // Scenario 1: Health/readiness endpoints — high-frequency lightweight checks
    health_checks: {
      executor: 'ramping-vus',
      startVUs: 5,
      stages: [
        { duration: '30s', target: 20 },
        { duration: '1m', target: 40 },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '10s',
      tags: { scenario: 'health' },
      exec: 'healthScenario',
    },

    // Scenario 2: Study execution — medium-frequency heavy operations
    study_execution: {
      executor: 'ramping-vus',
      startVUs: 2,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '1m', target: 20 },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '15s',
      tags: { scenario: 'study' },
      exec: 'studyScenario',
    },

    // Scenario 3: Concurrent study submissions — burst of parallel requests
    concurrent_studies: {
      executor: 'ramping-vus',
      startVUs: 5,
      stages: [
        { duration: '20s', target: 30 },
        { duration: '40s', target: 30 },
        { duration: '20s', target: 0 },
      ],
      gracefulRampDown: '10s',
      tags: { scenario: 'concurrent' },
      exec: 'concurrentStudyScenario',
    },

    // Scenario 4: General load — configurable via env vars for CI
    general_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: Math.round(K6_VUS * 0.3) },
        { duration: K6_DURATION, target: K6_VUS },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '15s',
      tags: { scenario: 'general' },
      exec: 'generalScenario',
    },
  },

  // ── Thresholds — pipeline FAILS if any are not met ────────────────────────
  thresholds: {
    // Overall HTTP request duration
    http_req_duration: [
      'p(95)<500',   // 95th percentile < 500 ms
      'p(99)<1000',  // 99th percentile < 1000 ms
    ],

    // Custom error rate
    errors: [
      'rate<0.01',   // Error rate < 1%
    ],

    // Per-scenario thresholds
    health_response_time: [
      'p(95)<200',   // Health checks should be very fast
      'p(99)<500',
    ],
    study_execution_time: [
      'p(95)<3000',  // Study execution can be slower
      'p(99)<5000',
    ],
    concurrent_study_time: [
      'p(95)<5000',
      'p(99)<8000',
    ],

    // HTTP failures must stay under 1%
    http_req_failed: [
      'rate<0.01',
    ],
  },

  // Summary output for CI parsing
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

// ─── Scenario Functions ──────────────────────────────────────────────────────

/**
 * Scenario 1: Health & Readiness endpoint checks
 * Lightweight, high-frequency — simulates monitoring / k8s probes.
 */
export function healthScenario() {
  group('Health Check', () => {
    const resp = http.get(`${BASE_URL}/health`, { tags: { endpoint: 'health' } });
    check(resp, {
      'health status 200': (r) => r.status === 200,
      'health body has status': (r) => {
        try { return r.json('status') === 'healthy'; } catch { return false; }
      },
    });
    errorRate.add(resp.status !== 200);
    healthResponseTime.add(resp.timings.duration);
  });

  sleep(0.5);

  group('Readiness Check', () => {
    const resp = http.get(`${BASE_URL}/ready`, { tags: { endpoint: 'ready' } });
    check(resp, {
      'ready status 200': (r) => r.status === 200,
      'ready body is ready': (r) => {
        try { return r.json('ready') === true; } catch { return false; }
      },
    });
    errorRate.add(resp.status !== 200);
    healthResponseTime.add(resp.timings.duration);
  });

  sleep(0.5);

  group('Liveness Probe', () => {
    const resp = http.get(`${BASE_URL}/healthz`, { tags: { endpoint: 'healthz' } });
    check(resp, {
      'healthz status 200': (r) => r.status === 200,
    });
    errorRate.add(resp.status !== 200);
    healthResponseTime.add(resp.timings.duration);
  });

  sleep(1);
}

/**
 * Scenario 2: Study execution endpoint
 * Heavy operations — simulates real engineering study submissions.
 */
export function studyScenario() {
  const studyType = STUDY_TYPES[__ITER % STUDY_TYPES.length];

  group(`Study: ${studyType}`, () => {
    let payload;
    let params = { headers: API_HEADERS, tags: { endpoint: 'study_run', study_type: studyType } };

    if (studyType === 'load_flow') {
      payload = JSON.stringify({
        study_type: 'load_flow',
        system: SAMPLE_SYSTEM,
        parameters: { max_iterations: 100, tolerance: 1e-6, algorithm: 'newton_raphson' },
      });
    } else if (studyType === 'short_circuit') {
      payload = JSON.stringify({
        study_type: 'short_circuit',
        system: SAMPLE_SYSTEM,
        parameters: { fault_type: 'three_phase', bus_id: 2 },
      });
    } else if (studyType === 'arc_flash') {
      payload = JSON.stringify({
        study_type: 'arc_flash',
        parameters: {
          voltage_kv: 13.8,
          bolted_fault_current_ka: 20,
          arc_duration_sec: 0.5,
          working_distance_mm: 610,
        },
      });
    } else if (studyType === 'protection_coordination') {
      payload = JSON.stringify({
        study_type: 'protection_coordination',
        system: SAMPLE_SYSTEM,
        parameters: {
          upstream_relay_id: 1,
          downstream_relay_id: 2,
          fault_currents: [2, 5, 10, 20],
        },
      });
    }

    const resp = http.post(`${BASE_URL}/api/v1/studies/run`, payload, params);
    const success = check(resp, {
      'study status 200': (r) => r.status === 200,
      'study has result': (r) => {
        try { return r.json('success') === true; } catch { return false; }
      },
    });

    errorRate.add(!success);
    studyExecutionTime.add(resp.timings.duration);
    studyRequests.add(1);
    if (!success) failedStudyRequests.add(1);
  });

  sleep(2);
}

/**
 * Scenario 3: Concurrent study submissions
 * Burst of parallel requests to test contention and queuing.
 */
export function concurrentStudyScenario() {
  group('Concurrent Study Submission', () => {
    // Submit multiple studies in quick succession
    const studyPayloads = [
      JSON.stringify({
        study_type: 'load_flow',
        system: SAMPLE_SYSTEM,
        parameters: { max_iterations: 50 },
      }),
      JSON.stringify({
        study_type: 'short_circuit',
        system: SAMPLE_SYSTEM,
        parameters: { fault_type: 'three_phase', bus_id: 2 },
      }),
      JSON.stringify({
        study_type: 'load_flow',
        system: SAMPLE_SYSTEM,
        parameters: { max_iterations: 200, algorithm: 'fast_decoupled' },
      }),
    ];

    const requests = studyPayloads.map((body, i) => ({
      method: 'POST',
      url: `${BASE_URL}/api/v1/studies/run`,
      body,
      params: {
        headers: API_HEADERS,
        tags: { endpoint: 'concurrent_study', batch: String(i) },
      },
    }));

    const responses = http.batch(requests);

    responses.forEach((resp, i) => {
      check(resp, {
        [`batch ${i} status ok`]: (r) => r.status === 200 || r.status === 400, // 400 = validation issue, not crash
      });
      errorRate.add(resp.status >= 500);
      concurrentStudyTime.add(resp.timings.duration);
      studyRequests.add(1);
      if (resp.status >= 500) failedStudyRequests.add(1);
    });
  });

  sleep(1);
}

/**
 * Scenario 4: General mixed load — mirrors real user behavior patterns
 * Mix of reads (health, metrics, agents) and writes (studies, validation).
 */
export function generalScenario() {
  // 40% chance: health/readiness
  const rand = Math.random();  // NOSONAR — javascript:S2245: load-test scenario selection, not security-sensitive
  if (rand < 0.2) {
    group('General: Health', () => {
      const resp = http.get(`${BASE_URL}/health`, { tags: { endpoint: 'health' } });
      check(resp, { 'health ok': (r) => r.status === 200 });
      errorRate.add(resp.status !== 200);
      healthResponseTime.add(resp.timings.duration);
    });
    sleep(0.5);
  } else if (rand < 0.4) {
    group('General: Readiness', () => {
      const resp = http.get(`${BASE_URL}/ready`, { tags: { endpoint: 'ready' } });
      check(resp, { 'ready ok': (r) => r.status === 200 });
      errorRate.add(resp.status !== 200);
      healthResponseTime.add(resp.timings.duration);
    });
    sleep(0.5);
  } else if (rand < 0.55) {
    group('General: Metrics', () => {
      const resp = http.get(`${BASE_URL}/metrics`, { tags: { endpoint: 'metrics' } });
      check(resp, { 'metrics ok': (r) => r.status === 200 });
      errorRate.add(resp.status !== 200);
    });
    sleep(0.5);
  } else if (rand < 0.7) {
    group('General: Agent Info', () => {
      const resp = http.get(`${BASE_URL}/api/v1/agents/info`, {
        headers: API_HEADERS,
        tags: { endpoint: 'agents_info' },
      });
      check(resp, { 'agents ok': (r) => r.status === 200 });
      errorRate.add(resp.status !== 200);
    });
    sleep(1);
  } else if (rand < 0.9) {
    group('General: Study Run', () => {
      const payload = JSON.stringify({
        study_type: 'load_flow',
        system: SAMPLE_SYSTEM,
        parameters: { max_iterations: 100 },
      });
      const resp = http.post(`${BASE_URL}/api/v1/studies/run`, payload, {
        headers: API_HEADERS,
        tags: { endpoint: 'study_run' },
      });
      const success = check(resp, { 'study ok': (r) => r.status === 200 });
      errorRate.add(!success);
      studyExecutionTime.add(resp.timings.duration);
      studyRequests.add(1);
      if (!success) failedStudyRequests.add(1);
    });
    sleep(2);
  } else {
    group('General: System Validation', () => {
      const payload = JSON.stringify({
        buses: [
          { id: 'BUS1', nominal_kv: 13.8, type: 'swing' },
          { id: 'BUS2', nominal_kv: 4.16, type: 'load' },
        ],
        branches: [{ from_bus: 'BUS1', to_bus: 'BUS2', r: 0.01, x: 0.05 }],
      });
      const resp = http.post(`${BASE_URL}/api/v1/system/validate`, payload, {
        headers: API_HEADERS,
        tags: { endpoint: 'validate' },
      });
      check(resp, { 'validate ok': (r) => r.status === 200 || r.status === 400 });
      errorRate.add(resp.status >= 500);
    });
    sleep(1);
  }
}

// ─── Summary Callback — JSON output for CI parsing ───────────────────────────

export function handleSummary(data) {
  // Build a machine-readable JSON summary
  const metrics = data.metrics || {};
  const result = {
    timestamp: new Date().toISOString(),
    test_run: {
      vus_max: data.state?.vusMax || 'N/A',
      iterations: metrics.iterations?.values?.count || 0,
      duration_ms: data.state?.testRunDurationMs || 0,
    },
    thresholds: {},
    metrics_summary: {
      http_req_duration: {
        avg: metrics.http_req_duration?.values?.avg,
        p95: metrics.http_req_duration?.values?.['p(95)'],
        p99: metrics.http_req_duration?.values?.['p(99)'],
      },
      errors: {
        rate: metrics.errors?.values?.rate,
        count: metrics.errors?.values?.fails,
      },
      health_response_time: {
        avg: metrics.health_response_time?.values?.avg,
        p95: metrics.health_response_time?.values?.['p(95)'],
        p99: metrics.health_response_time?.values?.['p(99)'],
      },
      study_execution_time: {
        avg: metrics.study_execution_time?.values?.avg,
        p95: metrics.study_execution_time?.values?.['p(95)'],
        p99: metrics.study_execution_time?.values?.['p(99)'],
      },
      concurrent_study_time: {
        avg: metrics.concurrent_study_time?.values?.avg,
        p95: metrics.concurrent_study_time?.values?.['p(95)'],
        p99: metrics.concurrent_study_time?.values?.['p(99)'],
      },
      study_requests_total: metrics.study_requests_total?.values?.count || 0,
      study_requests_failed: metrics.study_requests_failed?.values?.count || 0,
    },
  };

  // Threshold pass/fail
  for (const [metricName, metricData] of Object.entries(metrics)) {
    const thresholds = metricData.thresholds;
    if (thresholds) {
      for (const [tName, tData] of Object.entries(thresholds)) {
        result.thresholds[`${metricName}: ${tName}`] = tData.ok;
      }
    }
  }

  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'load-test-results/k6/summary.json': JSON.stringify(data, null, 2),
  };
}
