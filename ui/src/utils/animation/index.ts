// AhmedETAP GSAP Animation Utility Library
// ==========================================
// Comprehensive GSAP integration for React with engineering aesthetic

// Core GSAP
import { gsap } from "gsap";

import { EasePack } from "gsap/EasePack";
import { Flip } from "gsap/Flip";
import { MotionPathPlugin } from "gsap/MotionPathPlugin";
// GSAP Plugins
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { TextPlugin } from "gsap/TextPlugin";

// Register plugins
if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger, TextPlugin, MotionPathPlugin, Flip, EasePack);
}

// Export core GSAP and plugins
export { gsap, ScrollTrigger, TextPlugin, MotionPathPlugin, Flip, EasePack };

export * from "./hooks";
export * from "./utils";
export * from "./presets";
export * from "./easing";
