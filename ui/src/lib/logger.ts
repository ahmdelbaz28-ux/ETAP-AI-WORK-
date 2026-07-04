type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  source: string;
  message: string;
  data?: Record<string, unknown>;
}

const _buffer: LogEntry[] = [];
const MAX_BUFFER = 500;

function formatEntry(entry: LogEntry): string {
  return `[${entry.timestamp}] ${entry.level.toUpperCase().padEnd(5)} [${entry.source}] ${entry.message}${entry.data ? ` ${JSON.stringify(entry.data)}` : ''}`;
}

function write(level: LogLevel, source: string, message: string, data?: Record<string, unknown>) {
  const entry: LogEntry = { timestamp: new Date().toISOString(), level, source, message, data };
  _buffer.push(entry);
  if (_buffer.length > MAX_BUFFER) _buffer.shift();

  const formatted = formatEntry(entry);
  switch (level) {
    case 'error':
      console.error(formatted);
      break;
    case 'warn':
      console.warn(formatted);
      break;
    default:
      console.log(formatted);
  }

  if (typeof globalThis !== 'undefined') {
    const w = globalThis as unknown as { __etapTelemetry?: (entry: LogEntry) => void };
    if (w.__etapTelemetry) {
      w.__etapTelemetry(entry);
    }
  }
}

export const logger = {
  debug: (source: string, message: string, data?: Record<string, unknown>) =>
    write('debug', source, message, data),
  info: (source: string, message: string, data?: Record<string, unknown>) =>
    write('info', source, message, data),
  warn: (source: string, message: string, data?: Record<string, unknown>) =>
    write('warn', source, message, data),
  error: (source: string, message: string, data?: Record<string, unknown>) =>
    write('error', source, message, data),
  getBuffer: (): readonly LogEntry[] => _buffer,
  clear: () => {
    _buffer.length = 0;
  },
};

export function installTelemetry(handler: (entry: LogEntry) => void) {
  (globalThis as unknown as { __etapTelemetry: (entry: LogEntry) => void }).__etapTelemetry =
    handler;
}
