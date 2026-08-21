// Type declarations for GSAP (GreenSock Animation Platform)
// GSAP is imported in animation utilities but is an optional runtime dependency.
// When GSAP is not installed, the animation modules gracefully degrade.
// These declarations allow TypeScript to compile without the GSAP package installed.
//
// Root cause analysis (systematic-debugging skill):
// Replaced ALL `any` with `unknown` or proper type signatures. Biome 1.9.4
// does not support `biome-ignore` comments reliably in `.d.ts` files, so we
// eliminated the `any` usages entirely. `unknown` is type-safe: callers must
// narrow the type before use, which is the correct behavior for optional deps.

declare module "gsap" {
  namespace gsap {
    interface Tween {
      kill(): void;
    }
    interface Timeline {
      kill(): void;
    }
    interface ScrollTriggerPlugin {
      create(vars?: Record<string, unknown>): unknown;
      getAll(): Array<{ kill(): void }>;
      kill(): void;
    }
    interface Context {
      revert(): void;
    }
    // GSAP core is dynamic without @types/gsap — use unknown to force callers to narrow
    const core: Record<string, unknown>;
  }

  // GSAP default export is dynamic — use a callable unknown with named exports
  const gsap: {
    context: (fn: (context?: gsap.Context) => void) => gsap.Context;
    to: (target: unknown, vars: Record<string, unknown>) => Tween;
    set: (target: unknown, vars: Record<string, unknown>) => void;
    timeline: (vars?: Record<string, unknown>) => Timeline;
    [key: string]: unknown;
  };
  export default gsap;
  export { gsap };
}

declare module "gsap/ScrollTrigger" {
  export const ScrollTrigger: {
    create: (vars: unknown) => { kill(): void };
    getAll: () => Array<{ kill(): void }>;
    [key: string]: unknown;
  };
  export default ScrollTrigger;
  namespace ScrollTrigger {
    interface Vars {
      trigger?: string | HTMLElement;
      start?: string;
      toggleActions?: string;
      animation?: unknown;
      [key: string]: unknown;
    }
  }
}

declare module "gsap/TextPlugin" {
  export const TextPlugin: Record<string, unknown>;
}

declare module "gsap/MotionPathPlugin" {
  export const MotionPathPlugin: Record<string, unknown>;
}

declare module "gsap/Flip" {
  export const Flip: Record<string, unknown>;
}

declare module "gsap/EasePack" {
  export const EasePack: Record<string, unknown>;
}
