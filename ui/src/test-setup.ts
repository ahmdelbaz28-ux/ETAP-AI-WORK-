import '@testing-library/jest-dom'

// Polyfill ResizeObserver for jsdom (required by recharts)
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = ResizeObserverMock as unknown as typeof globalThis.ResizeObserver
