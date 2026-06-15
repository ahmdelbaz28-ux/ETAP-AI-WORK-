import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const responseTime = new Trend('response_time');

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 50 },
    { duration: '30s', target: 100 },
    { duration: '1m', target: 100 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'],
    errors: ['rate<0.05'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  // Health check (lightweight)
  const healthResp = http.get(`${BASE_URL}/health`);
  check(healthResp, {
    'health status is 200': (r) => r.status === 200,
    'health body has status': (r) => r.json('status') === 'healthy',
  });
  errorRate.add(healthResp.status !== 200);
  responseTime.add(healthResp.timings.duration);
  sleep(1);

  // Readiness check
  const readyResp = http.get(`${BASE_URL}/ready`);
  check(readyResp, {
    'ready status is 200': (r) => r.status === 200,
    'ready body is ready': (r) => r.json('ready') === true,
  });
  errorRate.add(readyResp.status !== 200);
  sleep(1);

  // Metrics (medium weight)
  const metricsResp = http.get(`${BASE_URL}/metrics`);
  check(metricsResp, {
    'metrics status is 200': (r) => r.status === 200,
  });
  errorRate.add(metricsResp.status !== 200);
  sleep(0.5);

  // Study run (heavy)
  const studyResp = http.post(`${BASE_URL}/api/v1/studies/run`, JSON.stringify({
    study_type: 'load_flow',
    config: {
      max_iterations: 100,
      tolerance: 1e-6,
      algorithm: 'newton_raphson',
    },
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
  check(studyResp, {
    'study status is 200': (r) => r.status === 200,
  });
  errorRate.add(studyResp.status !== 200);
  sleep(2);
}
