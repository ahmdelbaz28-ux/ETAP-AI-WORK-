import '@testing-library/jest-dom';

// Polyfill ResizeObserver for jsdom (required by recharts)
// Methods are intentionally empty — this is a no-op mock so chart components
// can render in the test environment without a real ResizeObserver.
class ResizeObserverMock {
  observe() {
    // no-op: jsdom doesn't layout, so observation is unnecessary
  }
  unobserve() {
    // no-op
  }
  disconnect() {
    // no-op
  }
}
globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof globalThis.ResizeObserver;
