// AhmedETAP GSAP React Hooks
// ===========================
// Custom React hooks for seamless GSAP integration with React components

import { gsap } from "gsap";
import { useEffect, useRef, useState } from "react";
import { ScrollTrigger } from "gsap/ScrollTrigger";

// Type helpers for GSAP - avoid self-referencing type annotation issues
type GSAPAnimation = gsap.core.Animation | gsap.core.Animation[];

/**
 * useGSAPAnimation - Core animation hook for React components
 * @param animationFn - Function that receives (element, gsapInstance, context) and returns GSAP animation
 * @param deps - Dependency array for when animation should re-run
 */
export function useGSAPAnimation<T extends HTMLElement = HTMLElement>(
  animationFn: (element: T, gsapInstance: typeof gsap, context: gsap.Context) => GSAPAnimation,
  deps: React.DependencyList = []
) {
  const elementRef = useRef<T>(null);
  const ctxRef = useRef<gsap.Context | null>(null);

  useEffect(() => {
    // Create GSAP context for cleanup
    ctxRef.current = gsap.context(() => {
      if (elementRef.current) {
        animationFn(elementRef.current, gsap, ctxRef.current!);
      }
    });

    return () => {
      ctxRef.current?.revert(); // Cleanup animations
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
  options: ScrollTrigger.Vars = {}
) {
  const elementRef = useRef<T>(null);
  const ctxRef = useRef<gsap.Context | null>(null);

  useEffect(() => {
    ctxRef.current = gsap.context(() => {
      if (elementRef.current) {
        const animation = animationFn(elementRef.current, gsap, ScrollTrigger);

        // Handle both single and array animations
        const anim = Array.isArray(animation) ? animation[0] : animation;

        // Create ScrollTrigger
        ScrollTrigger.create({
          trigger: triggerSelector,
          animation: anim,
          start: "top 80%",
          toggleActions: "play none none none",
          ...options,
        });

        // Handle remaining animations in array
        if (Array.isArray(animation)) {
          for (let i = 1; i < animation.length; i++) {
            ScrollTrigger.create({
              trigger: triggerSelector,
              animation: animation[i],
              start: "top 80%",
              toggleActions: "play none none none",
              ...options,
            });
          }
        }
      }
    });

    return () => {
      ctxRef.current?.revert();
      ScrollTrigger.getAll().forEach(trigger => trigger.kill());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggerSelector, options]);

  return elementRef;
}

/**
 * useGSAPNumberCounter - Animated number counter for engineering metrics
 * @param targetValue - Target number to animate to
 * @param options - Animation options
 */
export function useGSAPNumberCounter(targetValue: number, options: {
  duration?: number;
  delay?: number;
  ease?: string;
  decimals?: number;
  prefix?: string;
  suffix?: string;
} = {}) {
  const [displayValue, setDisplayValue] = useState("0");
  const elementRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!elementRef.current) return;

    const ctx = gsap.context(() => {
      gsap.to({}, {
        duration: options.duration || 2,
        delay: options.delay || 0,
        onUpdate: function() {
          if (!elementRef.current) return;

          const progress = this.progress();
          const currentValue = progress * targetValue;

          // Format with engineering precision
          const decimals = options.decimals ?? (targetValue < 100 ? 1 : 0);
          const formattedValue = currentValue.toFixed(decimals);

          setDisplayValue(`${options.prefix || ""}${formattedValue}${options.suffix || ""}`);
        },
        ease: options.ease || "power3.out"
      });
    });

    return () => ctx.revert();
  }, [targetValue]); // eslint-disable-line react-hooks/exhaustive-deps

  return { displayValue, elementRef };
}

/**
 * useGSAPHoverEffect - Hover animation for engineering cards
 * @param options - Hover animation options
 */
export function useGSAPHoverEffect<T extends HTMLElement = HTMLElement>(options: {
  scale?: number;
  rotation?: number;
  glowIntensity?: number;
  duration?: number;
} = {}) {
  const elementRef = useRef<T>(null);

  useEffect(() => {
    if (!elementRef.current) return;

    const ctx = gsap.context(() => {
      const element = elementRef.current!;
      const scale = options.scale || 1.03;
      const rotation = options.rotation || 0.5;
      const duration = options.duration || 0.3;

      // Create hover timeline
      const hoverTL = gsap.timeline({ paused: true });

      // Scale and rotation
      hoverTL.to(element, {
        scale,
        rotationY: rotation,
        duration,
        ease: "back.out(1.7)"
      });

      // Glow effect
      if (options.glowIntensity) {
        hoverTL.to(element, {
          boxShadow: `0 0 ${options.glowIntensity * 20}px rgba(0, 212, 255, ${options.glowIntensity * 0.3})`,
          duration: duration * 0.5,
          ease: "power2.out"
        }, "<0.1");
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
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return elementRef;
}

/**
 * useGSAPPageTransition - Page transition animations
 * @param options - Transition options
 */
export function useGSAPPageTransition(options: {
  duration?: number;
  ease?: string;
  delay?: number;
} = {}) {
  const [isTransitioning] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const ctx = gsap.context(() => {
      // Initial state
      gsap.set(containerRef.current, { opacity: 0, y: 20 });

      // Entrance animation
      gsap.to(containerRef.current, {
        opacity: 1,
        y: 0,
        duration: options.duration || 0.8,
        delay: options.delay || 0.2,
        ease: options.ease || "expo.out"
      });
    });

    return () => ctx.revert();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { containerRef, isTransitioning };
}

/**
 * useGSAPParticleSystem - Engineering particle system for backgrounds
 * @param options - Particle system options
 */
export function useGSAPParticleSystem(canvasRef: React.RefObject<HTMLCanvasElement>, options: {
  particleCount?: number;
  particleSize?: number;
  particleColor?: string;
  particleSpeed?: number;
  particleOpacity?: number;
  connectParticles?: boolean;
  connectionDistance?: number;
  connectionColor?: string;
} = {}) {
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

    // Particle configuration
    const particleCount = options.particleCount || 100;
    const particleSize = options.particleSize || 2;
    const particleColor = options.particleColor || "#00d4ff";
    const particleSpeed = options.particleSpeed || 0.5;
    const particleOpacity = options.particleOpacity || 0.6;
    const connectParticles = options.connectParticles ?? true;
    const connectionDistance = options.connectionDistance || 120;
    const connectionColor = options.connectionColor || "rgba(0, 212, 255, 0.1)";

    // Create particles
    const particles: Particle[] = [];
    for (let i = 0; i < particleCount; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        size: particleSize,
        baseX: Math.random() * canvas.width,
        baseY: Math.random() * canvas.height,
        speed: particleSpeed * (Math.random() * 0.5 + 0.5),
        directionAngle: Math.random() * Math.PI * 2,
        velocity: {
          x: Math.cos(Math.random() * Math.PI * 2) * particleSpeed,
          y: Math.sin(Math.random() * Math.PI * 2) * particleSpeed
        }
      });
    }

    // Animation loop
    let animationId: number;
    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Update and draw particles
      particles.forEach(particle => {
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
      });

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
          from: "random"
        },
        onUpdate: function() {
          // Update particle properties
          particles.forEach((_particle, i) => {
            _particle.size = this.targets()[i].size;
            _particle.opacity = this.targets()[i].opacity;
          });
        }
      });
    });

    return () => {
      window.removeEventListener("resize", resizeCanvas);
      cancelAnimationFrame(animationId);
      ctxGSAP.revert();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
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
