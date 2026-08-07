// AhmedETAP GSAP Utility Functions
// =================================
// Reusable GSAP animation utilities for engineering aesthetics

import { gsap } from "gsap";

/**
 * createPowerSurgeAnimation - Engineering power surge animation
 * @param element - Target element
 * @param options - Animation options
 */
export function createPowerSurgeAnimation(element: HTMLElement | string, options: {
  duration?: number;
  intensity?: number;
  color?: string;
  delay?: number;
} = {}) {
  const duration = options.duration || 1.5;
  const intensity = options.intensity || 1;
  const color = options.color || "#00d4ff";
  const delay = options.delay || 0;

  return gsap.to(element, {
    duration,
    delay,
    boxShadow: `0 0 ${20 * intensity}px ${color}`,
    borderColor: color,
    backgroundColor: `color-mix(in srgb, ${color} 10%, transparent)`,
    repeat: -1,
    yoyo: true,
    ease: "sine.inOut"
  });
}

/**
 * createEngineeringEntrance - Entrance animation for engineering components
 * @param element - Target element
 * @param options - Animation options
 */
export function createEngineeringEntrance(element: HTMLElement | string, options: {
  duration?: number;
  delay?: number;
  yStart?: number;
  opacityStart?: number;
  ease?: string;
} = {}) {
  const duration = options.duration || 0.8;
  const delay = options.delay || 0;
  const yStart = options.yStart || 30;
  const opacityStart = options.opacityStart || 0;
  const ease = options.ease || "back.out(1.7)";

  return gsap.from(element, {
    y: yStart,
    opacity: opacityStart,
    duration,
    delay,
    ease,
    clearProps: "transform,opacity"
  });
}

/**
 * createNumberCounter - Animated number counter for engineering metrics
 * @param element - Target element
 * @param targetValue - Target number
 * @param options - Animation options
 */
export function createNumberCounter(element: HTMLElement | string, targetValue: number, options: {
  duration?: number;
  delay?: number;
  ease?: string;
  decimals?: number;
  prefix?: string;
  suffix?: string;
} = {}) {
  const duration = options.duration || 2;
  const delay = options.delay || 0;
  const ease = options.ease || "power3.out";
  const decimals = options.decimals ?? (targetValue < 100 ? 1 : 0);

  return gsap.to(element, {
    innerText: targetValue,
    duration,
    delay,
    ease,
    snap: { innerText: 1 },
    onUpdate: function() {
      const currentValue = Number.parseFloat(this.targets()[0].innerText);
      this.targets()[0].innerText = `${options.prefix || ""}${currentValue.toFixed(decimals)}${options.suffix || ""}`;
    }
  });
}

/**
 * createPowerFlowAnimation - Power flow animation for engineering diagrams
 * @param element - Target element (SVG path or group)
 * @param options - Animation options
 */
export function createPowerFlowAnimation(element: HTMLElement | string, options: {
  duration?: number;
  delay?: number;
  color?: string;
  width?: number;
  repeat?: number;
} = {}) {
  const duration = options.duration || 3;
  const delay = options.delay || 0;
  const color = options.color || "#00d4ff";
  const width = options.width || 2;
  const repeat = options.repeat ?? -1;

  // Create a dashed line animation
  return gsap.to(element, {
    strokeDashoffset: 0,
    duration,
    delay,
    repeat,
    ease: "none",
    attr: {
      stroke: color,
      "stroke-width": width,
      "stroke-dasharray": "5, 5",
      "stroke-dashoffset": 10
    }
  });
}

/**
 * createGlassMorphismEffect - Glass morphism animation for cards
 * @param element - Target element
 * @param options - Animation options
 */
export function createGlassMorphismEffect(element: HTMLElement | string, options: {
  duration?: number;
  blur?: number;
  opacity?: number;
  delay?: number;
} = {}) {
  const duration = options.duration || 1;
  const blur = options.blur || 12;
  const opacity = options.opacity || 0.7;
  const delay = options.delay || 0;

  return gsap.to(element, {
    duration,
    delay,
    backdropFilter: `blur(${blur}px) saturate(180%)`,
    backgroundColor: `rgba(15, 21, 37, ${opacity})`,
    borderColor: `rgba(255, 255, 255, ${opacity * 0.1})`,
    ease: "power2.out"
  });
}

/**
 * createEngineeringPulse - Pulse animation for engineering indicators
 * @param element - Target element
 * @param options - Animation options
 */
export function createEngineeringPulse(element: HTMLElement | string, options: {
  duration?: number;
  scale?: number;
  opacity?: number;
  color?: string;
  delay?: number;
} = {}) {
  const duration = options.duration || 2;
  const scale = options.scale || 1.2;
  const opacity = options.opacity || 0.8;
  const color = options.color || "#00d4ff";
  const delay = options.delay || 0;

  return gsap.to(element, {
    duration,
    delay,
    scale,
    opacity,
    backgroundColor: color,
    repeat: -1,
    yoyo: true,
    ease: "sine.inOut"
  });
}

/**
 * createTimeline - Create a GSAP timeline with engineering aesthetic defaults
 * @param options - Timeline options
 */
export function createTimeline(options: gsap.TimelineVars = {}) {
  return gsap.timeline({
    defaults: {
      ease: "power3.out",
      duration: 0.5
    },
    ...options
  });
}