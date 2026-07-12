# BAZSPARK Design System — V223 Engineering Identity

> **⚠️ CRITICAL: This document is the single source of truth for the BAZSPARK UI design.**
> Any change to colors, typography, or component styling MUST be reviewed against this
> document. The design was accidentally overwritten once (commit `1ddad377` — the
> "Awwwards redesign") and we don't want that to happen again.

## Design Philosophy

BAZSPARK is an **engineering tool** for fire protection system design (NFPA 72).
The UI follows the **professional engineering theme** inspired by:
- VS Code Dark+
- GitHub Dark
- Material Dark
- NFPA 79 / IEC 60204-1 status color conventions

**Optimized for 8+ hour sessions** — reduced eye strain, WCAG AAA text contrast,
no flashy effects, no glassmorphism, no neon colors.

## Color Palette (DO NOT CHANGE)

### Surface Palette (3% elevation steps)

| Token | Hex | RGB | Usage |
|-------|-----|-----|-------|
| `--background` | `#0f172a` | `15 23 42` | Page background (slate-900 navy-charcoal) |
| `--card` | `#172033` | `23 32 51` | Elevated surfaces, cards, sidebar, main content |
| `--popover` | `#172033` | `23 32 51` | Dropdowns, popovers |
| `--secondary` | `#1e293b` | `30 41 59` | Recessed surfaces, hover states |
| `--muted` | `#1e293b` | `30 41 59` | Hover/recessed background |

### Text Colors

| Token | Hex | RGB | Usage |
|-------|-----|-----|-------|
| `--foreground` | `#e6edf3` | `230 237 243` | Primary text (cool off-white, NOT pure white) |
| `--muted-foreground` | `#94a3b8` | `148 163 184` | Secondary text (7:1 AAA contrast) |
| `--secondary-foreground` | `#cbd5e1` | `203 213 225` | Text on secondary surfaces |

### Action Colors

| Token | Hex | RGB | Usage |
|-------|-----|-----|-------|
| `--primary` | `#2f81f7` | `47 129 247` | **Calm cyan-blue** — primary buttons, active states, links |
| `--primary-foreground` | `#ffffff` | `255 255 255` | Text on primary (use semibold ≥15px) |
| `--accent` | `#2dd4bf` | `45 212 191` | **Teal** — active tab / selected row ONLY (not for buttons) |
| `--destructive` | `#dc2626` | `220 38 38` | Destructive filled buttons |

### Status Colors (NFPA 79 / IEC 60204-1 — NEVER DEVIATE)

| Token | Hex | RGB | Meaning |
|-------|-----|-----|---------|
| `--success` | `#3fb950` | `63 185 80` | GREEN = normal / safe / run |
| `--warning` | `#d29922` | `210 153 34` | AMBER = caution / attention |
| `--danger` | `#f85149` | `248 81 73` | RED = fault / alarm (status text) |
| `--info` | `#38bdf8` | `56 189 248` | BLUE = mandatory / informational |

### Structural Colors

| Token | Hex | RGB | Usage |
|-------|-----|-----|-------|
| `--border` | `#2a3a52` | `42 58 82` | Subtle but visible borders |
| `--input` | `#334155` | `51 65 85` | Stronger border for form fields |
| `--ring` | `#2f81f7` | `47 129 247` | Focus ring = primary |

## Typography

- **Primary font**: IBM Plex Sans (UI) — closest web-safe equivalent to AutoCAD's Arial
- **Mono font**: IBM Plex Mono (data, code, technical numbers)
- **Fallback**: Arial → Helvetica (AutoCAD's actual defaults)
- **Body line-height**: 1.5 (not 1.75 — that was the Awwwards mistake)
- **Letter-spacing**: normal (not 0.01em — that was the Awwwards mistake)

## Border Radius

- `--radius`: `0.5rem` (8px) — balanced for engineering
- `--radius-sm`: `0.375rem` (6px)

**DO NOT use `0.75rem` (12px)** — that was the Awwwards mistake.

## Component Styling Rules

### Buttons (`button.tsx`)

```tsx
// CORRECT (V223):
"default": "bg-primary text-primary-foreground hover:bg-primary/90"
// rounded-md, h-9, no shadow, no scale, no border

// WRONG (Awwwards — DO NOT DO THIS):
"default": "bg-cyan-400/90 text-cyan-950 hover:bg-cyan-400 shadow-md shadow-cyan-500/15 hover:scale-[1.02]"
// rounded-lg, h-11, shadow, scale, border
```

### Sidebar (`Sidebar.tsx`)

- Background: `bg-card backdrop-blur-sm` (NOT `glass` class)
- Border: `border-r border-border/50` (NOT `border-white/10`)
- Active item: `bg-card border-l-2 border-primary text-primary shadow-lg shadow-orange-500/20`
- Inactive item: `text-muted-foreground hover:bg-card/60 hover:text-foreground`
- Logo icon: `ShieldCheck` (NOT `Zap`)
- Logo background: `bg-primary` (NOT `bg-cyan-400/10 border border-cyan-400/20`)

### Ask AI Button (`AskAiButton.tsx`)

- Style: `bg-primary` (calm blue #2f81f7), flat, no shadow, no glow, no blob
- Position: `fixed bottom-4 right-4`
- Size: `h-10 px-4` (NOT `h-12`)
- Shape: `rounded-md` (NOT `rounded-full`)
- NO glassmorphism, NO floating animation, NO gradient blob

### Cards (`card.tsx`)

- Background: `bg-card` (solid #172033, NOT transparent)
- Border: `border border-border` (subtle #2a3a52)
- Radius: `rounded-lg` (8px)
- NO `backdrop-blur`, NO `bg-white/5`, NO transparency

## What NOT To Do (Anti-Patterns from the Awwwards Disaster)

1. ❌ **DO NOT use `#22d3ee` (neon cyan)** — use `#2f81f7` (calm blue) instead
2. ❌ **DO NOT use `#070b12` (deep navy)** — use `#0f172a` (slate-900) instead
3. ❌ **DO NOT use glassmorphism** (`backdrop-blur` + transparency) on solid surfaces
4. ❌ **DO NOT add `hover:scale-*` to buttons** — use color change only
5. ❌ **DO NOT add shadows to buttons** (`shadow-md`, `shadow-cyan-500/15`)
6. ❌ **DO NOT use `rounded-full` on buttons** — use `rounded-md`
7. ❌ **DO NOT use `rounded-xl` on logo container** — use `rounded-md`
8. ❌ **DO NOT add floating animations** to UI elements
9. ❌ **DO NOT add gradient blobs** as decorative backgrounds
10. ❌ **DO NOT change line-height to 1.75** — keep it at 1.5
11. ❌ **DO NOT use Inter font** — use IBM Plex Sans (AutoCAD style)
12. ❌ **DO NOT use `Zap` icon for logo** — use `ShieldCheck`

## Git History Reference

| Commit | Description | Status |
|--------|-------------|--------|
| `ae5252d9` | V223: Blue Ask AI button, no borders, AutoCAD font | ✅ **THIS IS THE CORRECT DESIGN** |
| `1ddad377` | Redesign: Awwwards identity (Cyan + Navy + Glassmorphism) | ❌ **THIS BROKE THE DESIGN — DO NOT REPEAT** |
| `bcc2e599` | V215 v3: ambient gradient blob | ❌ Removed in V216 |
| V216 (current) | Restored V223 + kept V214 features (Mining, ApiKeys, Exports, SelfHealing) | ✅ **CURRENT** |

## Pre-Commit Checklist

Before committing UI changes, verify:

- [ ] `globals.css` uses `--background: 15 23 42` (NOT `7 11 18`)
- [ ] `globals.css` uses `--primary: 47 129 247` (NOT `34 211 238`)
- [ ] `index.css` uses `--color-background: #0f172a` (NOT `#070b12`)
- [ ] `button.tsx` has NO `hover:scale-*` and NO `shadow-*`
- [ ] `Sidebar.tsx` uses `bg-card` (NOT `glass` class)
- [ ] `AskAiButton.tsx` uses `bg-primary` (NOT `glass` or `ask-ai-button` class)
- [ ] No `ask-ai-blob` or `ask-ai-button` custom CSS classes in `index.css`
- [ ] Border radius is `0.5rem` (NOT `0.75rem`)
- [ ] Font is IBM Plex Sans (NOT Inter)

## How To Restore If Broken Again

```bash
# Restore the V223 design files
git checkout ae5252d9 -- \
  frontend/src/styles/globals.css \
  frontend/src/styles/typography.css \
  frontend/src/index.css \
  frontend/src/components/ui/button.tsx \
  frontend/src/components/ui/card.tsx \
  frontend/src/components/layout/TopBar.tsx \
  frontend/src/components/layout/StatusBar.tsx \
  frontend/src/pages/LoginPage.tsx

# Then re-apply V216 Sidebar changes (Mining, ApiKeys, Exports, SelfHealing)
# See commit bcc2e599..HEAD for the V216 Sidebar additions
```
