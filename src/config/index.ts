// Application configuration
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

  return {
    port: parseInt(process.env['PORT'] ?? '3000', 10),
    nodeEnv: process.env['NODE_ENV'] ?? 'development',
    logLevel: process.env['LOG_LEVEL'] ?? 'info',
    databaseUrl: process.env['DATABASE_URL'] ?? '',
    jwtSecret: process.env['JWT_SECRET'] ?? '',
    corsOrigin: process.env['CORS_ORIGIN'] ?? '*',
  };
}
