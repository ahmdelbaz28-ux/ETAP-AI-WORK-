import { describe, it, expect } from '@jest/globals';
import { createServer } from '../../src/services/server.js';
import type * as nodeHttp from 'node:http';
import type { AppConfig } from '../../src/config/index.js';

describe('Server', () => {
  let server: ReturnType<typeof nodeHttp.createServer>;
  const testConfig: AppConfig = {
    port: 0,
    nodeEnv: 'test',
    logLevel: 'error',
    databaseUrl: 'postgresql://localhost:5432/testdb',
    jwtSecret: 'test-secret',
    corsOrigin: '*',
  };

  afterEach(async () => {
    if (server) {
      server.close();
    }
  });

  it('should create an HTTP server', async () => {
    server = await createServer(testConfig);
    expect(server).toBeDefined();
    expect(server.listening).toBe(false);
  });

  it('should respond to /health with 200', async () => {
    server = await createServer(testConfig);
    const { port } = await listenOnRandomPort(server);

    const response = await fetch(`http://localhost:${port}/health`);
    expect(response.status).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('status', 'ok');
    expect(body).toHaveProperty('timestamp');
  });

  it('should include security headers', async () => {
    server = await createServer(testConfig);
    const { port } = await listenOnRandomPort(server);

    const response = await fetch(`http://localhost:${port}/health`);
    expect(response.headers.get('x-content-type-options')).toBe('nosniff');
    expect(response.headers.get('x-frame-options')).toBe('DENY');
    expect(response.headers.get('x-xss-protection')).toBe('1; mode=block');
    expect(response.headers.get('strict-transport-security')).toContain('max-age=31536000');
  });

  it('should return 404 for unknown routes', async () => {
    server = await createServer(testConfig);
    const { port } = await listenOnRandomPort(server);

    const response = await fetch(`http://localhost:${port}/unknown`);
    expect(response.status).toBe(404);

    const body = await response.json();
    expect(body).toHaveProperty('error', 'Not Found');
  });
});

function listenOnRandomPort(
  server: ReturnType<typeof nodeHttp.createServer>,
): Promise<{ port: number }> {
  return new Promise((resolve, reject) => {
    server.listen(0, () => {
      const address = server.address();
      if (address && typeof address === 'object') {
        resolve({ port: address.port });
      } else {
        reject(new Error('Failed to get server address'));
      }
    });
  });
}
