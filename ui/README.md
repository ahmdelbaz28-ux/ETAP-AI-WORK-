# AhmedETAP — Chat-First v3.0 Web Application

The frontend of **AhmedETAP** is a high-performance, safety-critical engineering workspace built with React 19, TypeScript 5.7, Tailwind CSS 4, and Vite 6.

---

## Key Features & Architecture

### 1. Chat-First v3.0 Engineering Workspace (`ChatWorkspace.tsx`)
- **Conversational Core**: Unified natural-language engineering interface with real-time server-sent event (SSE) streaming (`POST /api/v1/chat/stream`).
- **BYOK (Bring Your Own Key)**: Direct client streaming with custom API credentials (`X-User-LLM-Key`, `X-User-LLM-Provider`) configured via `AISettingsModal.tsx` and validated without server key leakage.
- **Dual-Control Maker-Checker**: High-consequence operational commands (such as substation breaker switching) trigger automated pre-flight checks and require secondary engineer signoff (`DualControl.tsx`) with WebSocket state synchronization.
- **EmergencyStop Interlock**: Hardware-styled kill-switch button (`EmergencyStopButton.tsx`) to immediately halt active study streams and CUA browser automation.

### 2. Dual-Theme Design Token System
- Full **Light Mode & Dark Mode** support without hardcoded hex color overrides.
- All components consume dynamic CSS variable design tokens (`var(--bg-primary)`, `var(--accent-primary)`, `var(--border-primary)`, `var(--color-danger)`, `var(--color-success)`).
- Complete bilingual internationalization (English and Arabic with proper RTL layout via `i18next`).

### 3. Integrated Engineering Views
- **AutoViewPanel**: Context-aware diagram switching between Single-Line Diagrams (SLD), GIS geospatial layers, and time-series charts.
- **ResultViewer**: Scientific tabular inspection of bus voltages, line loadings, and protection coordination curves with rollback history.
- **ParametersDrawer**: Interactive tuning of Newton-Raphson tolerances and study parameters.

---

## Local Development & Testing

### Installation & Run
```bash
# Install dependencies
npm install

# Start development server (port 5173)
npm run dev

# Build production bundle
npm run build

# Run TypeScript type check
npm run typecheck
```

### Running Test Suite
The UI test suite is powered by Vitest and React Testing Library:
```bash
npx vitest run
```
**Verification Evidence:** 26/26 test suites passed, 208/208 automated tests passed (0 failures, 0 timeouts).
