// AhmedETAP GSAP Easing Presets
// ==============================
// Custom easing functions for engineering animations

import { gsap } from "gsap";

// Engineering-specific easing functions
export const Easing = {
  // Power surge - fast start, slow finish (for power system animations)
  POWER_SURGE: "power3.in",
  
  // Circuit flow - smooth, continuous flow (for data/power flow animations)
  CIRCUIT_FLOW: "sine.inOut",
  
  // Engineering bounce - technical bounce with precision (for indicators, alerts)
  ENGINEERING_BOUNCE: "back.out(1.4)",
  
  // System stabilization - slow start, fast finish (for system initialization)
  SYSTEM_STABILIZATION: "power3.out",
  
  // Critical alert - fast, urgent motion (for warnings, faults)
  CRITICAL_ALERT: "elastic.out(1, 0.5)",
  
  // Data pulse - rhythmic data visualization (for charts, metrics)
  DATA_PULSE: "sine.inOut",
  
  // Component activation - smooth component entrance (for UI elements)
  COMPONENT_ACTIVATION: "back.out(1.7)",
  
  // System shutdown - slow, controlled deceleration (for exit animations)
  SYSTEM_SHUTDOWN: "power2.in",
  
  // Engineering precision - linear motion with slight overshoot
  ENGINEERING_PRECISION: "expo.out",
  
  // Power grid - smooth grid animations (for background grids)
  POWER_GRID: "circ.inOut"
};

// Register custom eases if needed
gsap.registerEase("Custom.PowerSurge", (progress: number) => {
  // Custom power surge ease - fast start, slow finish with overshoot
  return progress < 0.3 ? progress * 1.5 : 1 - Math.pow(1 - progress, 2);
});

gsap.registerEase("Custom.CircuitFlow", (progress: number) => {
  // Custom circuit flow ease - smooth continuous flow
  return 0.5 - 0.5 * Math.cos(progress * Math.PI);
});