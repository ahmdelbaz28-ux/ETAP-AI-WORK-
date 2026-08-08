// Application entry point
import { createServer } from './services/server.js';
import { loadConfig } from './config/index.js';
import { logger } from './utils/logger.js';

async function main(): Promise<void> {
  const config = loadConfig();
  const server = await createServer(config);

  const port = config.port ?? 3000;
  server.listen(port, () => {
    logger.info(`Server running on port ${port}`);
  });

  // Graceful shutdown
  const shutdown = (signal: string): void => {
    logger.info(`Received ${signal}, shutting down gracefully...`);
    server.close(() => {
      logger.info('Server closed');
      process.exit(0);
    });

    // Force shutdown after 10 seconds
    setTimeout(() => {
      logger.error('Forced shutdown after timeout');
      process.exit(1);
    }, 10_000);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

main().catch((error: unknown) => {
  logger.error('Fatal error during startup', error);
  process.exit(1);
});
