// HTTP Server service
import http from 'node:http';
import type { AppConfig } from '../config/index.js';
import { logger } from '../utils/logger.js';

interface ServerError extends Error {
  code?: string;
}

export async function createServer(config: AppConfig): Promise<http.Server> {
  const server = http.createServer((req, res) => {
    // Security headers — per security-checklist
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('X-XSS-Protection', '1; mode=block');
    res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
    res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');

    // Health check endpoint
    if (req.url === '/health' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok', timestamp: new Date().toISOString() }));
      return;
    }

    // 404 for unknown routes
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not Found' }));
  });

  server.on('error', (error: ServerError) => {
    if (error.code === 'EADDRINUSE') {
      logger.error(`Port ${config.port} is already in use`);
      process.exit(1);
    } else {
      logger.error('Server error', error);
    }
  });

  return server;
}
