// AhmedETAP GSAP Animation Presets
// =================================
// Pre-configured animation sequences for engineering UI

import { gsap } from "gsap";
import { Easing } from "./easing";

/**
 * Engineering Card Entrance Animation
 * - Used for stat cards, agent cards, study cards
 */
export function engineeringCardEntrance(element: HTMLElement, options: {
  delay?: number;
  duration?: number;
  stagger?: number;
} = {}) {
  const delay = options.delay || 0;
  const duration = options.duration || 0.6;
  const stagger = options.stagger || 0.1;

  return gsap.from(element, {
    y: 30,
    opacity: 0,
    scale: 0.95,
    duration,
    delay,
    ease: Easing.COMPONENT_ACTIVATION,
    stagger,
    clearProps: "transform,opacity"
  });
}

/**
 * Power System Dashboard Entrance
 * - Used for dashboard page entrance
 */
export function powerSystemDashboardEntrance(_container: HTMLElement) {
  const tl = gsap.timeline();

  // Header entrance
  tl.from(".dashboard-header", {
    y: -20,
    opacity: 0,
    duration: 0.5,
    ease: Easing.COMPONENT_ACTIVATION
  });

  // Stat cards entrance
  tl.from(".stat-card", {
    y: 30,
    opacity: 0,
    scale: 0.95,
    duration: 0.6,
    stagger: 0.1,
    ease: Easing.COMPONENT_ACTIVATION
  }, "-=0.3");

  // Charts entrance
  tl.from(".dashboard-chart", {
    opacity: 0,
    scale: 0.98,
    duration: 0.8,
    ease: Easing.COMPONENT_ACTIVATION
  }, "-=0.4");

  // System gauges entrance
  tl.from(".system-gauge", {
    opacity: 0,
    y: 15,
    duration: 0.5,
    stagger: 0.05,
    ease: Easing.COMPONENT_ACTIVATION
  }, "-=0.6");

  // Quick actions entrance
  tl.from(".quick-action", {
    opacity: 0,
    x: -10,
    duration: 0.4,
    stagger: 0.05,
    ease: Easing.COMPONENT_ACTIVATION
  }, "-=0.5");

  // Agents list entrance
  tl.from(".agent-item", {
    opacity: 0,
    x: 10,
    duration: 0.4,
    stagger: 0.05,
    ease: Easing.COMPONENT_ACTIVATION
  }, "-=0.5");

  return tl;
}

/**
 * Login Page Power Grid Animation
 * - Used for login page background
 */
export function loginPagePowerGridAnimation(canvas: HTMLCanvasElement) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return gsap.timeline();

  const tl = gsap.timeline({ repeat: -1, yoyo: true });

  // Create grid lines
  const gridSize = 60;
  const gridWidth = canvas.width;
  const gridHeight = canvas.height;

  // Animate grid lines
  tl.to({}, {
    duration: 8,
    onUpdate: () => {
      ctx.clearRect(0, 0, gridWidth, gridHeight);
      
      // Draw vertical lines
      for (let x = 0; x < gridWidth; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, gridHeight);
        ctx.strokeStyle = `rgba(70, 120, 200, ${0.1 + Math.random() * 0.05})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      
      // Draw horizontal lines
      for (let y = 0; y < gridHeight; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(gridWidth, y);
        ctx.strokeStyle = `rgba(70, 120, 200, ${0.1 + Math.random() * 0.05})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }
  });

  // Add power nodes
  tl.to({}, {
    duration: 4,
    onUpdate: () => {
      // Draw power nodes at intersections
      for (let x = 0; x < gridWidth; x += gridSize) {
        for (let y = 0; y < gridHeight; y += gridSize) {
          const pulse = Math.sin(Date.now() * 0.002 + x * 0.01 + y * 0.01) * 0.5 + 0.5;
          const size = 3 + pulse * 4;
          const opacity = 0.3 + pulse * 0.7;
          
          ctx.beginPath();
          ctx.arc(x, y, size, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(0, 212, 255, ${opacity})`;
          ctx.fill();
        }
      }
    }
  });

  return tl;
}

/**
 * Engineering Number Counter Animation
 * - Used for metrics, statistics, gauges
 */
export function engineeringNumberCounter(element: HTMLElement, targetValue: number, options: {
  duration?: number;
  delay?: number;
  decimals?: number;
} = {}) {
  const duration = options.duration || 2;
  const delay = options.delay || 0;
  const decimals = options.decimals ?? (targetValue < 100 ? 1 : 0);

  return gsap.to(element, {
    innerText: targetValue,
    duration,
    delay,
    ease: Easing.ENGINEERING_PRECISION,
    snap: { innerText: 1 },
    onUpdate: function() {
      const currentValue = parseFloat(this.targets()[0].innerText);
      this.targets()[0].innerText = currentValue.toFixed(decimals);
    }
  });
}

/**
 * Power System Component Activation
 * - Used for buttons, interactive elements
 */
export function powerSystemComponentActivation(element: HTMLElement) {
  const tl = gsap.timeline({ paused: true });

  // Initial state
  tl.set(element, {
    boxShadow: "0 0 0px rgba(0, 212, 255, 0)"
  });

  // Hover animation
  tl.to(element, {
    scale: 1.03,
    duration: 0.3,
    ease: Easing.COMPONENT_ACTIVATION
  });

  // Glow effect
  tl.to(element, {
    boxShadow: "0 0 12px rgba(0, 212, 255, 0.3)",
    duration: 0.2,
    ease: "power2.out"
  }, "-=0.2");

  // Active animation
  tl.to(element, {
    scale: 0.98,
    duration: 0.1,
    ease: "power2.in"
  }, "active");

  return tl;
}

/**
 * System Alert Animation
 * - Used for notifications, warnings, alerts
 */
export function systemAlertAnimation(element: HTMLElement) {
  const tl = gsap.timeline({ repeat: -1, yoyo: true });

  // Pulse animation
  tl.to(element, {
    scale: 1.05,
    opacity: 0.9,
    duration: 1.5,
    ease: Easing.CRITICAL_ALERT
  });

  // Color oscillation
  tl.to(element, {
    backgroundColor: "#ef4444",
    duration: 0.8,
    ease: "sine.inOut"
  });

  tl.to(element, {
    backgroundColor: "#f59e0b",
    duration: 0.8,
    ease: "sine.inOut"
  });

  return tl;
}

/**
 * Engineering Data Flow Animation
 * - Used for data visualization, power flow diagrams
 */
export function engineeringDataFlowAnimation(element: SVGElement) {
  const tl = gsap.timeline({ repeat: -1 });

  // Animate stroke dash offset for flow effect
  tl.to(element, {
    strokeDashoffset: -10,
    duration: 2,
    ease: "none",
    attr: {
      "stroke-dasharray": "5, 5",
      "stroke": "#00d4ff",
      "stroke-width": "2"
    }
  });

  return tl;
}