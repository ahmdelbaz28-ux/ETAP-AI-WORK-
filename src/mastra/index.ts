import { Mastra } from '@mastra/core/mastra';
import { PinoLogger } from '@mastra/loggers';
import { LibSQLStore } from '@mastra/libsql';
import {
  Observability,
  MastraStorageExporter,
  MastraPlatformExporter,
  SensitiveDataFilter,
} from '@mastra/observability';

import { DuckDBStore } from "@mastra/duckdb";
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

// IMPORTANT: We previously used MastraCompositeStore with a lazy-initialized
// DuckDB observability store. However:
//   1. MastraCompositeStore.init() calls `domain.init()` which was removed
//      from Node.js (TypeError: domain.init is not a function) — this broke
//      ALL scenario tests in CI.
//   2. The DuckDB store was never actually used (the Proxy returned an empty
//      object on any method call when DuckDB was unavailable, which is always
//      the case in CI and HF Space).
// The fix: use a plain LibSQLStore for ALL storage domains (including
// observability). This is simpler, works on all Node versions, and the
// MastraStorageExporter will persist observability events to the same
// SQLite file. DuckDB can be re-added later if needed for analytics.

export const mastra = new Mastra({
  workflows: { weatherWorkflow },
  agents: {
    weatherAgent,
    goalPlannerAgent,

// Lazy-initialized observability store to avoid blocking startup with DuckDB
let _observabilityStore: any = null;
let _observabilityStoreInitialized = false;

async function getObservabilityStore(): Promise<any> {
  if (_observabilityStoreInitialized) {
    return _observabilityStore;
  }
  _observabilityStoreInitialized = true;
  const start = Date.now();
  try {
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
    codeGuardAgent,
  },
  storage: new LibSQLStore({
    id: 'mastra-storage',
    url: 'file:./mastra.db',

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
