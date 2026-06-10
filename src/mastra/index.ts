import { Mastra } from '@mastra/core/mastra';
import { PinoLogger } from '@mastra/loggers';
import { LibSQLStore } from '@mastra/libsql';
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
import { protectionAgent } from './agents/protection-agent';
import { powerSystemCoordinatorAgent } from './agents/power-system-coordinator-agent';

// Initialize observability store - handle DuckDB import issues gracefully
let observabilityStore: Awaited<ReturnType<DuckDBStore['getStore']>>;
try {
  const store = await new DuckDBStore().getStore('observability');
  observabilityStore = store;
} catch (e) {
  console.warn('[Mastra] DuckDB unavailable, using fallback');
  observabilityStore = {} as any;
}

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
    protectionAgent,
    powerSystemCoordinatorAgent
  },
  storage: new MastraCompositeStore({
    id: 'composite-storage',
    default: new LibSQLStore({
      id: "mastra-storage",
      url: "file:./mastra.db",
    }),
    domains: {
      observability: observabilityStore,
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
