// AhmedETAP GSAP Page Transition Component
// ========================================
// Smooth page transitions with GSAP for React Router

import { gsap } from "gsap";
import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

interface GSAPPageTransitionProps {
  children: React.ReactNode;
  animationType?: "slide" | "fade" | "scale" | "engineering";
  duration?: number;
  delay?: number;
}

/**
 * GSAP-powered page transition component for React Router
 * @param children - The page content to animate
 * @param animationType - Type of transition animation
 * @param duration - Animation duration in seconds
 * @param delay - Delay before animation starts
 */
export function GSAPPageTransition({
  children,
  animationType = "engineering",
  duration = 0.8,
  delay = 0.1
}: GSAPPageTransitionProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const previousPath = useRef(location.pathname);

  useEffect(() => {
    if (!containerRef.current) return;
    
    const ctx = gsap.context(() => {
      // Skip animation on initial load
      if (previousPath.current === location.pathname) {
        gsap.set(containerRef.current, { opacity: 1, y: 0, scale: 1 });
        return;
      }
      
      // Apply different animation types
      switch (animationType) {
        case "slide":
          gsap.fromTo(containerRef.current,
            { opacity: 0, y: 50 },
            { opacity: 1, y: 0, duration, delay, ease: "back.out(1.7)" }
          );
          break;
        case "fade":
          gsap.fromTo(containerRef.current,
            { opacity: 0 },
            { opacity: 1, duration, delay, ease: "power3.out" }
          );
          break;
        case "scale":
          gsap.fromTo(containerRef.current,
            { opacity: 0, scale: 0.95 },
            { opacity: 1, scale: 1, duration, delay, ease: "back.out(1.7)" }
          );
          break;
        case "engineering":
        default:
          // Engineering-specific transition with power surge effect
          gsap.fromTo(containerRef.current,
            {
              opacity: 0,
              y: 30,
              scale: 0.98,
              boxShadow: "0 0 0px rgba(0, 212, 255, 0)"
            },
            {
              opacity: 1,
              y: 0,
              scale: 1,
              duration,
              delay,
              ease: "back.out(1.7)",
              boxShadow: "0 0 20px rgba(0, 212, 255, 0.1)",
              onComplete: () => {
                // Remove box shadow after animation
                gsap.to(containerRef.current, {
                  boxShadow: "0 0 0px rgba(0, 212, 255, 0)",
                  duration: 0.3
                });
              }
            }
          );
          break;
      }
      
      // Update previous path
      previousPath.current = location.pathname;
    });
    
    return () => ctx.revert();
  }, [location.pathname, animationType, duration, delay]);

  return (
    <div ref={containerRef} style={{ opacity: 0, transform: "translateY(30px)" }}>
      {children}
    </div>
  );
}

/**
 * GSAP-powered route transition component for React Router
 * @param children - The route content to animate
 */
export function GSAPRouteTransition({ children }: { children: React.ReactNode }) {
  return (
    <GSAPPageTransition animationType="engineering">
      {children}
    </GSAPPageTransition>
  );
}