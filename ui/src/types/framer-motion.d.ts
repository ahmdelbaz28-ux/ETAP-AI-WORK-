// Type declarations for framer-motion (used alongside GSAP in some components)
// NOSONAR — framer-motion has no official @types/ package; this minimal declaration
// satisfies TypeScript for components that still use framer-motion alongside GSAP.
declare module "framer-motion" {
  import type { ComponentType, ReactNode, CSSProperties } from "react";

  // Animation controls
  export type AnimationControls = {
    start: () => void;
    stop: () => void;
  };

  // Variants
  export type Variants = Record<string, Record<string, unknown>>;

  // Transition
  export type Transition = {
    duration?: number;
    delay?: number;
    ease?: string | number[];
    type?: string;
    stiffness?: number;
    damping?: number;
    staggerChildren?: number;
    delayChildren?: number;
    repeat?: number;
    repeatType?: string;
    yoyo?: boolean;
  };

  // Motion props
  export type MotionProps = {
    initial?: Record<string, unknown> | string;
    animate?: Record<string, unknown> | string;
    exit?: Record<string, unknown> | string;
    variants?: Variants;
    transition?: Transition;
    className?: string;
    style?: CSSProperties;
    key?: string | number;
    children?: ReactNode;
    layout?: boolean;
    layoutId?: string;
    whileHover?: Record<string, unknown>;
    whileTap?: Record<string, unknown>;
    onAnimationComplete?: () => void;
    ref?: import("react").Ref<unknown>;
    // Allow event handlers compatible with native HTML element props
    onClick?: React.MouseEventHandler;
    onMouseEnter?: React.MouseEventHandler;
    onMouseLeave?: React.MouseEventHandler;
    onSubmit?: React.FormEventHandler;
    onChange?: React.ChangeEventHandler;
    [key: string]: unknown;
  };

  // Motion components
  export const motion: {
    div: ComponentType<MotionProps & import("react").HTMLAttributes<HTMLDivElement>>;
    span: ComponentType<MotionProps & import("react").HTMLAttributes<HTMLSpanElement>>;
    p: ComponentType<MotionProps & import("react").HTMLAttributes<HTMLParagraphElement>>;
    h1: ComponentType<MotionProps & import("react").HTMLAttributes<HTMLHeadingElement>>;
    h2: ComponentType<MotionProps & import("react").HTMLAttributes<HTMLHeadingElement>>;
    h3: ComponentType<MotionProps & import("react").HTMLAttributes<HTMLHeadingElement>>;
    button: ComponentType<MotionProps & import("react").ButtonHTMLAttributes<HTMLButtonElement>>;
    a: ComponentType<MotionProps & import("react").AnchorHTMLAttributes<HTMLAnchorElement>>;
    img: ComponentType<MotionProps & import("react").ImgHTMLAttributes<HTMLImageElement>>;
    svg: ComponentType<MotionProps & import("react").SVGAttributes<SVGSVGElement>>;
    path: ComponentType<MotionProps & import("react").SVGAttributes<SVGPathElement>>;
    circle: ComponentType<MotionProps & import("react").SVGAttributes<SVGCircleElement>>;
    g: ComponentType<MotionProps & import("react").SVGAttributes<SVGGElement>>;
    ul: ComponentType<MotionProps & import("react").HTMLAttributes<HTMLUListElement>>;
    li: ComponentType<MotionProps & import("react").HTMLAttributes<HTMLLIElement>>;
    section: ComponentType<MotionProps & import("react").HTMLAttributes<HTMLElement>>;
    [key: string]: ComponentType<MotionProps & Record<string, unknown>>;
  };

  // AnimatePresence
  export const AnimatePresence: ComponentType<{
    children?: ReactNode;
    mode?: "wait" | "sync" | "popLayout";
    initial?: boolean;
    onExitComplete?: () => void;
  }>;

  // useAnimation
  export function useAnimation(): AnimationControls;

  // useMotionValue
  export function useMotionValue<T>(initial: T): { get: () => T; set: (v: T) => void };
}
