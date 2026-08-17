// Type declarations for GSAP (GreenSock Animation Platform)
// GSAP is imported in animation utilities but is an optional runtime dependency.
// When GSAP is not installed, the animation modules gracefully degrade.
// These declarations allow TypeScript to compile without the GSAP package installed.

declare module "gsap" {
  namespace gsap {
    interface Tween {
      kill(): void;
    }
    interface Timeline {
      kill(): void;
    }
    interface ScrollTriggerPlugin {
      create(vars?: any): any;
      getAll(): any[];
      kill(): void;
    }
  }

  const gsap: any;
  export default gsap;
  export { gsap };
}

declare module "gsap/ScrollTrigger" {
  export const ScrollTrigger: any;
  export default ScrollTrigger;
  namespace ScrollTrigger {
    interface ScrollTriggerInstance {
      kill(): void;
    }
  }
}

declare module "gsap/TextPlugin" {
  export const TextPlugin: any;
}

declare module "gsap/MotionPathPlugin" {
  export const MotionPathPlugin: any;
}

declare module "gsap/Flip" {
  export const Flip: any;
}

declare module "gsap/EasePack" {
  export const EasePack: any;
}
