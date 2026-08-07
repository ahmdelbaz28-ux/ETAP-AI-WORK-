// Application configuration
// Per ci-cd-and-automation skill: secrets come from environment, never hardcoded
export interface AppConfig {
  port: number;
  nodeEnv: string;
  logLevel: string;
  databaseUrl: string;
  jwtSecret: string;
  corsOrigin: string;
}

export function loadConfig(): AppConfig {
  const requiredEnvVars = ['DATABASE_URL', 'JWT_SECRET'];

  for (const envVar of requiredEnvVars) {
    if (!process.env[envVar]) {
      throw new Error(`Missing required environment variable: ${envVar}`);
    }
  }

  const nodeEnv = process.env['NODE_ENV'] ?? 'development';
  const corsOrigin = process.env['CORS_ORIGIN'] ?? 'http://localhost:3000';

  // Security: warn if wildcard CORS in production
  if (nodeEnv === 'production' && corsOrigin === '*') {
    throw new Error(
      'CORS_ORIGIN cannot be "*" in production — set a specific origin in CORS_ORIGIN env var',
    );
  }

  // Security: warn if default JWT secret in production
  const jwtSecret = process.env['JWT_SECRET'] ?? '';
  if (nodeEnv === 'production' && jwtSecret.length < 32) {
    throw new Error('JWT_SECRET must be at least 32 characters in production');
  }

  return {
    port: Number.parseInt(process.env['PORT'] ?? '3000', 10),
    nodeEnv,
    logLevel: process.env['LOG_LEVEL'] ?? 'info',
    databaseUrl: process.env['DATABASE_URL'] ?? '',
    jwtSecret,
    corsOrigin,
  };
}
