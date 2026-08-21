// Secure pseudorandom helper using Web Crypto CSPRNG (sonar:S2245).
export function secureRandom(): number {
  const a = new Uint32Array(1);
  crypto.getRandomValues(a);
  return a[0] / 4294967296;
}

// AhmedETAP GSAP React Hooks
// ===========================
// Custom React hooks for seamless GSAP integration with React components
//
// ARCHITECTURE (systematic-debugging root cause fix):
// All hooks use the "latest ref" pattern to avoid stale closures without
// triggering effect re-runs. The effect captures the latest callback/options
// via a ref that is updated on every render. This is the canonical pattern
// for GSAP integration with React (see React docs on "getting a ref to the
// latest value" and useEvent polyfill discussions).

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useEffect, useRef, useState } from "react";

// Type helpers for GSAP - avoid self-referencing type annotation issues
type GSAPAnimation = gsap.core.Animation | gsap.core.Animation[];

/**
 * useGSAPAnimation - Core animation hook for React components
 * @param animationFn - Function that receives (element, gsapInstance, context) and returns GSAP animation
 * @param deps - Dependency array for when animation should re-run
 */
export function useGSAPAnimation<T extends HTMLElement = HTMLElement>(
  animationFn: (element: T, gsapInstance: typeof gsap, context: gsap.Context) => GSAPAnimation,
  deps: React.DependencyList = [],
) {
  const elementRef = useRef<T>(null);
  const ctxRef = useRef<gsap.Context | null>(null);
  // Latest-ref pattern: capture animationFn so the effect always calls the
  // freshest version without re-running on every render.
  const animationFnRef = useRef(animationFn);
  useEffect(() => {
    animationFnRef.current = animationFn;
  });

  useEffect(() => {
    // Create GSAP context for cleanup
    ctxRef.current = gsap.context((context) => {
      if (elementRef.current) {
        animationFnRef.current(elementRef.current, gsap, context);
      }
    });

    return () => {
      ctxRef.current?.revert(); // Cleanup animations
    };
    // deps is honoured separately to allow callers to opt-in to re-runs.
    // animationFn is captured via ref to avoid re-runs on every render.
  }, deps);

  return elementRef;
}

/**
 * useGSAPScrollTrigger - Hook for scroll-triggered animations
 * @param triggerSelector - Element selector to trigger animation
 * @param animationFn - Function that receives (element, gsapInstance, st) and returns animation
 * @param options - ScrollTrigger options
 */
export function useGSAPScrollTrigger<T extends HTMLElement = HTMLElement>(
  triggerSelector: string | HTMLElement,
  animationFn: (element: T, gsapInstance: typeof gsap, st: typeof ScrollTrigger) => GSAPAnimation,
  options: ScrollTrigger.Vars = {},
) {
  const elementRef = useRef<T>(null);
  const ctxRef = useRef<gsap.Context | null>(null);
  // Latest-ref pattern for animationFn + options to keep deps stable.
  const animationFnRef = useRef(animationFn);
  const optionsRef = useRef(options);
  useEffect(() => {
    animationFnRef.current = animationFn;
    optionsRef.current = options;
  });

  useEffect(() => {
    ctxRef.current = gsap.context(() => {
      if (elementRef.current) {
        const animation = animationFnRef.current(elementRef.current, gsap, ScrollTrigger);

        // Handle both single and array animations
        const anim = Array.isArray(animation) ? animation[0] : animation;

        // Create ScrollTrigger
        ScrollTrigger.create({
          trigger: triggerSelector,
          animation: anim,
          start: "top 80%",
          toggleActions: "play none none none",
          ...optionsRef.current,
        });

        // Handle remaining animations in array
        if (Array.isArray(animation)) {
          for (let i = 1; i < animation.length; i++) {
            ScrollTrigger.create({
              trigger: triggerSelector,
              animation: animation[i],
              start: "top 80%",
              toggleActions: "play none none none",
              ...optionsRef.current,
            });
          }
        }
      }
    });

    return () => {
      ctxRef.current?.revert();
      // use for...of instead of forEach (biome/complexity/noForEach)
      for (const trigger of ScrollTrigger.getAll()) {
        trigger.kill();
      }
    };
    // Only re-run when triggerSelector identity changes. animationFn and
    // options are kept fresh via refs above.
  }, [triggerSelector]);

  return elementRef;
}

/**
 * useGSAPNumberCounter - Animated number counter for engineering metrics
 * @param targetValue - Target number to animate to
 * @param options - Animation options
 */
export function useGSAPNumberCounter(
  targetValue: number,
  options: {
    duration?: number;
    delay?: number;
    ease?: string;
    decimals?: number;
    prefix?: string;
    suffix?: string;
  } = {},
) {
  const [displayValue, setDisplayValue] = useState("0");
  const elementRef = useRef<HTMLSpanElement>(null);
  // Latest-ref pattern: keep options fresh without forcing effect re-runs.
  const optionsRef = useRef(options);
  useEffect(() => {
    optionsRef.current = options;
  });

  useEffect(() => {
    if (!elementRef.current) return;

    const ctx = gsap.context(() => {
      gsap.to(
        {},
        {
          duration: optionsRef.current.duration || 2,
          delay: optionsRef.current.delay || 0,
          onUpdate: function () {
            if (!elementRef.current) return;

            const progress = this.progress();
            const currentValue = progress * targetValue;

            // Format with engineering precision
            const decimals = optionsRef.current.decimals ?? (targetValue < 100 ? 1 : 0);
            const formattedValue = currentValue.toFixed(decimals);

            setDisplayValue(
              `${optionsRef.current.prefix || ""}${formattedValue}${optionsRef.current.suffix || ""}`,
            );
          },
          ease: optionsRef.current.ease || "power3.out",
        },
      );
    });

    return () => ctx.revert();
    // Only re-run when targetValue identity changes.
  }, [targetValue]);

  return { displayValue, elementRef };
}

/**
 * useGSAPHoverEffect - Hover animation for engineering cards
 * @param options - Hover animation options
 */
export function useGSAPHoverEffect<T extends HTMLElement = HTMLElement>(
  options: {
    scale?: number;
    rotation?: number;
    glowIntensity?: number;
    duration?: number;
  } = {},
) {
  const elementRef = useRef<T>(null);
  // Latest-ref pattern: options captured via ref.
  const optionsRef = useRef(options);
  useEffect(() => {
    optionsRef.current = options;
  });

  useEffect(() => {
    if (!elementRef.current) return;

    const ctx = gsap.context(() => {
      if (!elementRef.current) return;

      const element = elementRef.current;
      const scale = optionsRef.current.scale || 1.03;
      const rotation = optionsRef.current.rotation || 0.5;
      const duration = optionsRef.current.duration || 0.3;

      // Create hover timeline
      const hoverTL = gsap.timeline({ paused: true });

      // Scale and rotation
      hoverTL.to(element, {
        scale,
        rotationY: rotation,
        duration,
        ease: "back.out(1.7)",
      });

      // Glow effect
      if (optionsRef.current.glowIntensity) {
        hoverTL.to(
          element,
          {
            boxShadow: `0 0 ${optionsRef.current.glowIntensity * 20}px rgba(0, 212, 255, ${optionsRef.current.glowIntensity * 0.3})`,
            duration: duration * 0.5,
            ease: "power2.out",
          },
          "<0.1",
        );
      }

      // Mouse enter/exit events
      const onMouseEnter = () => hoverTL.play();
      const onMouseLeave = () => hoverTL.reverse();
      element.addEventListener("mouseenter", onMouseEnter);
      element.addEventListener("mouseleave", onMouseLeave);

      return () => {
        element.removeEventListener("mouseenter", onMouseEnter);
        element.removeEventListener("mouseleave", onMouseLeave);
      };
    });

    return () => ctx.revert();
    // Intentionally empty: this hook should only set up the hover listener
    // once. Options are kept fresh via the ref above.
  }, []);

  return elementRef;
}

/**
 * useGSAPPageTransition - Page transition animations
 * @param options - Transition options
 */
export function useGSAPPageTransition(
  options: {
    duration?: number;
    ease?: string;
    delay?: number;
  } = {},
) {
  const [isTransitioning] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  // Latest-ref pattern: options captured via ref.
  const optionsRef = useRef(options);
  useEffect(() => {
    optionsRef.current = options;
  });

  useEffect(() => {
    if (!containerRef.current) return;

    const ctx = gsap.context(() => {
      // Initial state
      gsap.set(containerRef.current, { opacity: 0, y: 20 });

      // Entrance animation
      gsap.to(containerRef.current, {
        opacity: 1,
        y: 0,
        duration: optionsRef.current.duration || 0.8,
        delay: optionsRef.current.delay || 0.2,
        ease: optionsRef.current.ease || "expo.out",
      });
    });

    return () => ctx.revert();
    // Intentionally empty: page transition runs once on mount.
  }, []);

  return { containerRef, isTransitioning };
}

/**
 * useGSAPParticleSystem - Engineering particle system for backgrounds
 * @param options - Particle system options
 */
export function useGSAPParticleSystem(
  canvasRef: React.RefObject<HTMLCanvasElement>,
  options: {
    particleCount?: number;
    particleSize?: number;
    particleColor?: string;
    particleSpeed?: number;
    particleOpacity?: number;
    connectParticles?: boolean;
    connectionDistance?: number;
    connectionColor?: string;
  } = {},
) {
  // Latest-ref pattern: options captured via ref so the effect does not
  // re-run when callers pass a fresh object literal on each render.
  const optionsRef = useRef(options);
  useEffect(() => {
    optionsRef.current = options;
  });

  // biome-ignore lint/correctness/useExhaustiveDependencies: canvasRef is a ref (stable); options captured via optionsRef
  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas size
    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    // Particle configuration — snapshot once on mount; subsequent
    // option changes are picked up on the NEXT mount.
    const o = optionsRef.current;
    const particleCount = o.particleCount || 100;
    const particleSize = o.particleSize || 2;
    const particleColor = o.particleColor || "#00d4ff";
    const particleSpeed = o.particleSpeed || 0.5;
    const particleOpacity = o.particleOpacity || 0.6;
    const connectParticles = o.connectParticles ?? true;
    const connectionDistance = o.connectionDistance || 120;
    const connectionColor = o.connectionColor || "rgba(0, 212, 255, 0.1)";

    // Create particles
    const particles: Particle[] = [];
    for (let i = 0; i < particleCount; i++) {
      particles.push({
        x: secureRandom() * canvas.width,
        y: secureRandom() * canvas.height,
        size: particleSize,
        baseX: secureRandom() * canvas.width,
        baseY: secureRandom() * canvas.height,
        speed: particleSpeed * (secureRandom() * 0.5 + 0.5),
        directionAngle: secureRandom() * Math.PI * 2,
        velocity: {
          x: Math.cos(secureRandom() * Math.PI * 2) * particleSpeed,
          y: Math.sin(secureRandom() * Math.PI * 2) * particleSpeed,
        },
      });
    }

    // Animation loop
    let animationId: number;
    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // use for...of instead of forEach (biome/complexity/noForEach)
      // Update and draw particles
      for (const particle of particles) {
        // Update position
        particle.x += particle.velocity.x;
        particle.y += particle.velocity.y;

        // Boundary check
        if (particle.x < 0 || particle.x > canvas.width) particle.velocity.x *= -1;
        if (particle.y < 0 || particle.y > canvas.height) particle.velocity.y *= -1;

        // Draw particle
        ctx.beginPath();
        ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
        ctx.fillStyle = particleColor;
        ctx.globalAlpha = particleOpacity;
        ctx.fill();
        ctx.globalAlpha = 1;
      }

      // Connect particles
      if (connectParticles) {
        for (let i = 0; i < particles.length; i++) {
          for (let j = i + 1; j < particles.length; j++) {
            const dx = particles[i].x - particles[j].x;
            const dy = particles[i].y - particles[j].y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < connectionDistance) {
              ctx.beginPath();
              ctx.strokeStyle = connectionColor;
              ctx.lineWidth = 0.5;
              ctx.moveTo(particles[i].x, particles[i].y);
              ctx.lineTo(particles[j].x, particles[j].y);
              ctx.stroke();
            }
          }
        }
      }

      animationId = requestAnimationFrame(animate);
    };

    // Start animation
    animate();

    // GSAP animation for particle pulses
    const ctxGSAP = gsap.context(() => {
      gsap.to(particles, {
        duration: 3,
        opacity: 0.8,
        size: particleSize * 1.5,
        repeat: -1,
        yoyo: true,
        ease: "sine.inOut",
        stagger: {
          amount: 2,
          grid: "auto",
          from: "random",
        },
        onUpdate: function () {
          // use for loop with index instead of forEach (biome/complexity/noForEach)
          const targets = this.targets() as Particle[];
          for (let i = 0; i < particles.length; i++) {
            particles[i].size = targets[i].size;
            particles[i].opacity = targets[i].opacity;
          }
        },
      });
    });

    return () => {
      window.removeEventListener("resize", resizeCanvas);
      cancelAnimationFrame(animationId);
      ctxGSAP.revert();
    };
    // Intentionally empty: particle system is set up once on mount.
  }, []);
}

// Particle interface
interface Particle {
  x: number;
  y: number;
  size: number;
  baseX: number;
  baseY: number;
  speed: number;
  directionAngle: number;
  velocity: {
    x: number;
    y: number;
  };
  opacity?: number;
}
