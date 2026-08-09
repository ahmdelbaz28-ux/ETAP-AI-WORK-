import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { logger } from '../../src/utils/logger.js';

describe('logger', () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    jest.spyOn(console, 'debug').mockImplementation(() => {});
    jest.spyOn(console, 'info').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('should log info messages', () => {
    logger.info('Test info message');
    expect(console.info).toHaveBeenCalled();
  });

  it('should log error messages', () => {
    logger.error('Test error message');
    expect(console.error).toHaveBeenCalled();
  });

  it('should log warn messages', () => {
    logger.warn('Test warning message');
    expect(console.warn).toHaveBeenCalled();
  });

  it('should include timestamp in log messages', () => {
    logger.info('Test message');
    const mockInfo = console.info as jest.Mock;
    const calls = mockInfo.mock.calls;
    expect(calls.length).toBeGreaterThan(0);
    const firstCall = calls[0];
    expect(firstCall).toBeDefined();
    expect(firstCall![0]).toMatch(/^\[\d{4}-\d{2}-\d{2}T/);
  });

  it('should stringify data objects', () => {
    logger.info('Test', { key: 'value' });
    const mockInfo = console.info as jest.Mock;
    const calls = mockInfo.mock.calls;
    expect(calls.length).toBeGreaterThan(0);
    const lastCall = calls[calls.length - 1];
    expect(lastCall).toBeDefined();
    expect(lastCall![0]).toContain('"key":"value"');
  });
});
