import { describe, it, expect } from '@jest/globals';
import { loadConfig } from '../../src/config/index.js';

describe('loadConfig', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('should load config with required environment variables', () => {
    process.env['DATABASE_URL'] = 'postgresql://localhost:5432/testdb';
    process.env['JWT_SECRET'] = 'test-secret-key';
    process.env['PORT'] = '4000';
    process.env['NODE_ENV'] = 'production';

    const config = loadConfig();

    expect(config.port).toBe(4000);
    expect(config.databaseUrl).toBe('postgresql://localhost:5432/testdb');
    expect(config.jwtSecret).toBe('test-secret-key');
    expect(config.nodeEnv).toBe('production');
  });

  it('should use default values for optional variables', () => {
    process.env['DATABASE_URL'] = 'postgresql://localhost:5432/testdb';
    process.env['JWT_SECRET'] = 'test-secret-key';
    delete process.env['PORT'];
    delete process.env['NODE_ENV'];
    delete process.env['LOG_LEVEL'];

    const config = loadConfig();

    expect(config.port).toBe(3000);
    expect(config.nodeEnv).toBe('development');
    expect(config.logLevel).toBe('info');
  });

  it('should throw error when DATABASE_URL is missing', () => {
    delete process.env['DATABASE_URL'];
    process.env['JWT_SECRET'] = 'test-secret-key';

    expect(() => loadConfig()).toThrow('Missing required environment variable: DATABASE_URL');
  });

  it('should throw error when JWT_SECRET is missing', () => {
    process.env['DATABASE_URL'] = 'postgresql://localhost:5432/testdb';
    delete process.env['JWT_SECRET'];

    expect(() => loadConfig()).toThrow('Missing required environment variable: JWT_SECRET');
  });

  it('should parse PORT as integer', () => {
    process.env['DATABASE_URL'] = 'postgresql://localhost:5432/testdb';
    process.env['JWT_SECRET'] = 'test-secret-key';
    process.env['PORT'] = '8080';

    const config = loadConfig();

    expect(config.port).toBe(8080);
    expect(typeof config.port).toBe('number');
  });
});
