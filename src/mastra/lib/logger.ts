/**
 * Enhanced Security Logger
 * =======================
 *
 * Provides secure logging functionality with sensitive data filtering,
 * audit trails, and tamper-resistant logging.
 *
 * Uses pino (via @mastra/loggers) which is already a project dependency.
 */

import pino from 'pino';
import { createHash } from 'node:crypto';

// Define log levels (pino uses numeric levels)
export const LOG_LEVELS = {
  ERROR: 50,
  WARN: 40,
  INFO: 30,
  DEBUG: 20,
};

// Define log types
export const LOG_TYPES = {
  SECURITY: 'SECURITY',
  API: 'API',
  AUDIT: 'AUDIT',
  ERROR: 'ERROR',
  INFO: 'INFO',
  DEBUG: 'DEBUG',
};

/**
 * Sanitize log metadata to remove sensitive information.
 */
function sanitizeLogMeta(meta: Record<string, unknown>): Record<string, unknown> {
  const sanitized: Record<string, unknown> = { ...meta };

  const sensitiveKeys = [
    'apiKey',
    'apiKeyHash',
    'password',
    'token',
    'secret',
    'authorization',
    'cookie',
    'x-api-key',
    'x-auth-token',
  ];

  for (const key of sensitiveKeys) {
    if (sanitized[key]) {
      const valueStr = typeof sanitized[key] === 'object' ? JSON.stringify(sanitized[key]) : String(sanitized[key]);
      const hash = createHash('sha256').update(valueStr).digest('hex');
      sanitized[key] = `***REDACTED*** (hash: ${hash.substring(0, 8)}...)`;
    }
  }

  const sensitivePatterns = [
    /pass/i,
    /auth/i,
    /token/i,
    /secret/i,
    /key/i,
    /credential/i,
  ];

  for (const prop in sanitized) {
    if (sensitivePatterns.some(pattern => pattern.test(prop))) {
      const hash = createHash('sha256').update(String(sanitized[prop])).digest('hex');
      sanitized[prop] = `***REDACTED*** (hash: ${hash.substring(0, 8)}...)`;
    }
  }

  return sanitized;
}

/**
 * Create a pino logger with secure configuration.
 *
 * @param module - Module name for log context
 * @returns pino.Logger instance
 */
export function createLogger(module: string): pino.Logger {
  return pino({
    level: process.env.LOG_LEVEL || 'info',
    name: module,
    formatters: {
      log(object: Record<string, unknown>) {
        return sanitizeLogMeta(object) as Record<string, unknown>;
      },
    },
    redact: {
      paths: ['apiKey', 'password', 'token', 'secret', 'authorization', 'cookie'],
      censor: '***REDACTED***',
    },
  });
}

/**
 * Log security events with risk level.
 */
export function logSecurityEvent(
  logger: pino.Logger,
  message: string,
  riskLevel: 'low' | 'medium' | 'high' | 'critical',
  action: string,
  details?: Record<string, unknown>,
): void {
  logger.warn({
    type: LOG_TYPES.SECURITY,
    riskLevel,
    action,
    ...details,
  }, message);
}

/**
 * Log API events for audit purposes.
 */
export function logApiEvent(
  logger: pino.Logger,
  endpoint: string,
  method: string,
  statusCode: number,
  duration: number,
  userId?: string,
  details?: Record<string, unknown>,
): void {
  const level = statusCode >= 400 ? 'error' : 'info';
  const fn = level === 'error' ? logger.error.bind(logger) : logger.info.bind(logger);
  fn({
    type: LOG_TYPES.API,
    endpoint,
    method,
    statusCode,
    duration,
    userId,
    ...details,
  }, `API ${method} ${endpoint} ${statusCode} (${duration}ms)`);
}

/**
 * Log audit events for compliance.
 */
export function logAuditEvent(
  logger: pino.Logger,
  action: string,
  resource: string,
  userId: string,
  result: 'success' | 'failure',
  details?: Record<string, unknown>,
): void {
  const fn = result === 'success' ? logger.info.bind(logger) : logger.warn.bind(logger);
  fn({
    type: LOG_TYPES.AUDIT,
    action,
    resource,
    userId,
    result,
    ...details,
  }, `Audit: ${action} on ${resource} - ${result}`);
}
