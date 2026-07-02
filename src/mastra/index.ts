import { Mastra } from '@mastra/core/mastra';
import { PinoLogger } from '@mastra/loggers';
import { LibSQLStore } from '@mastra/libsql';
import { MastraCompositeStore } from '@mastra/core/storage';
import { Observability, MastraStorageExporter, MastraPlatformExporter, SensitiveDataFilter } from '@mastra/observability';
import { weatherWorkflow } from './workflows/weather-workflow';
import { weatherAgent } from './agents/weather-agent';
import { goalPlannerAgent } from './agents/goal-planner-agent';
import { motorStartingAgent } from './agents/motorstarting-agent';
import { shortCircuitAgent } from './agents/shortcircuit-agent';
import { loadFlowAgent } from './agents/loadflow-agent';
import { arcFlashAgent } from './agents/arcflash-agent';
import { etapEngineerAgent } from './agents/etap-engineer-agent';
import { etapExpertAgent } from './agents/etap-expert-agent';
import { protectionAgent } from './agents/protection-agent';
import { powerSystemCoordinatorAgent } from './agents/power-system-coordinator-agent';
import { codeGuardAgent } from './agents/code-guard-agent';

// Lazy-initialized observability store to avoid blocking startup with DuckDB.
// IMPORTANT: @mastra/duckdb is imported DYNAMICALLY (not at top-level) so that
// `mastra build` (rollup) does not try to parse the native `.node` binary
// bindings that ship with @duckdb/node-bindings. DuckDB is optional at runtime
// (the lazy init falls back to an empty store if it fails).
let _observabilityStore: any = null;
let _observabilityStoreInitialized = false;

async function getObservabilityStore(): Promise<any> {
  if (_observabilityStoreInitialized) {
    return _observabilityStore;
  }
  _observabilityStoreInitialized = true;
  const start = Date.now();
  try {
    // Use a variable + @vite-ignore so rollup/mastra-build cannot statically
    // analyze this import (which would pull in the native .node bindings and
    // break `mastra build`). The module is loaded at runtime only.
    const moduleName = '@mastra/duckdb';
    const mod = await import(/* @vite-ignore */ /* webpackIgnore: true */ moduleName);
    const DuckDBStore = mod.DuckDBStore;
    const store = await new DuckDBStore().getStore('observability');
    _observabilityStore = store;
    console.log(`[Mastra] DuckDB observability store initialized in ${Date.now() - start}ms`);
  } catch (e) {
    console.warn(`[Mastra] DuckDB unavailable after ${Date.now() - start}ms, using fallback`);
    _observabilityStore = {};
  }
  return _observabilityStore;
}

// Initialize observability store lazily on first access
const observabilityStoreProxy = new Proxy({} as any, {
  get(_target, prop) {
    // Trigger lazy initialization if needed
    if (!_observabilityStoreInitialized) {
      // Return a placeholder that resolves on first real call
      return (...args: any[]) => {
        const store = _observabilityStore || {};
        const fn = store[prop];
        if (typeof fn === 'function') {
          return fn.apply(store, args);
        }
        return undefined;
      };
    }
    const store = _observabilityStore || {};
    const value = store[prop];
    if (typeof value === 'function') {
      return value.bind(store);
    }
    return value;
  },
});

export const mastra = new Mastra({
  workflows: { weatherWorkflow },
  agents: { 
    weatherAgent, 
    goalPlannerAgent, 
    motorStartingAgent,
    shortCircuitAgent,
    loadFlowAgent,
    arcFlashAgent,
    etapEngineerAgent,
    etapExpertAgent,
    protectionAgent,
    powerSystemCoordinatorAgent,
    codeGuardAgent
  },
  storage: new MastraCompositeStore({
    id: 'composite-storage',
    default: new LibSQLStore({
      id: "mastra-storage",
      url: "file:./mastra.db",
    }),
    domains: {
      observability: observabilityStoreProxy,
    }
  }),
  logger: new PinoLogger({
    name: 'Mastra',
    level: 'info',
  }),
  observability: new Observability({
    configs: {
      default: {
        serviceName: 'mastra',
        exporters: [
          new MastraStorageExporter(), // Persists observability events to Mastra Storage
          new MastraPlatformExporter(), // Sends observability events to Mastra Platform (if MASTRA_PLATFORM_ACCESS_TOKEN is set)
        ],
        spanOutputProcessors: [
          new SensitiveDataFilter(), // Redacts sensitive data like passwords, tokens, keys
        ],
      },
    },
  }),
});

// Trigger background initialization so it's ready when needed, but non-blocking
getObservabilityStore().catch(() => {});
