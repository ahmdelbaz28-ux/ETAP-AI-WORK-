
═══════════════════════════════════════════════════════════════════
BAZSPARK v8.1 — STITCH-READY UI PROMPT
Production-Grade Engineering Interface · Consolidated & Optimized
═══════════════════════════════════════════════════════════════════

[CRITICAL IMPROVEMENTS APPLIED FROM EVALUATION]
1. Viewport: min-width 1440px · Collapsible panels (⌘B / ⌘I)
2. Context Isolation: Marine tab removed in Building Mode
3. Canvas: Ctrl+Wheel zoom · Middle-Click pan · CAD muscle memory
4. AI: Background-first suggestions · Purple glow indicator only
═══════════════════════════════════════════════════════════════════

SYSTEM IDENTITY & BRAND
═══════════════════════════════════════════════════════════════════

Application: BAZspark — Intelligent Fire Safety Engineering Platform
Tagline: NFPA 72 · NEC 2022 · SOLAS · IMO · AI-Powered Engineering
Parent Brand: FireAI Technology

Color System:
  Primary:     #E84040  (Fire Red)
  Primary Dark:#B91C1C
  Secondary:   #1E293B  (Slate 800)
  Surface:     #0F172A  (Slate 950 — main background)
  Surface-2:   #1E293B  (Slate 800 — card background)
  Surface-3:   #334155  (Slate 700 — elevated surface)
  Accent:      #38BDF8  (Sky Blue — interactive/data)
  Ocean:       #0EA5E9  (Ocean Blue — marine module)
  Purple:      #A78BFA  (AI agent)
  Success:     #22C55E
  Warning:     #F59E0B
  Danger:      #EF4444
  Text-1:      #F8FAFC
  Text-2:      #CBD5E1
  Text-3:      #64748B
  Border:      #334155
  Border-2:    #475569

Typography:
  Font Family: "Inter", "JetBrains Mono" (code/numbers)
  Heading-1: 28px / 700 / -0.02em
  Heading-2: 22px / 600 / -0.01em
  Heading-3: 16px / 600
  Body:       14px / 400 / 1.6 lineHeight
  Caption:    12px / 500 / uppercase / 0.05em
  Code/Data:  13px / JetBrains Mono / 500

Spacing Grid: 4px base (4, 8, 12, 16, 24, 32, 48, 64)
Border Radius: sm=4px, md=8px, lg=12px, xl=16px, 2xl=24px, full=9999px

Shadow System:
  sm:  0 1px 3px rgba(0,0,0,0.3)
  md:  0 4px 16px rgba(0,0,0,0.4)
  lg:  0 8px 32px rgba(0,0,0,0.5)
  glow-red:   0 0 20px rgba(232,64,64,0.3)
  glow-blue:  0 0 20px rgba(56,189,248,0.3)
  glow-green: 0 0 20px rgba(34,197,94,0.2)
  glow-purple: 0 0 20px rgba(167,139,250,0.3)
  glow-ocean:  0 0 20px rgba(14,165,233,0.3)

Icons: Lucide React — stroke-width=1.5, size=16|20|24
Animations: 150ms cubic-bezier(0.4,0,0.2,1)

═══════════════════════════════════════════════════════════════════
VIEWPORT & RESPONSIVE CONSTRAINTS [P1 IMPROVEMENT]
═══════════════════════════════════════════════════════════════════

Min-width: 1440px (desktop engineering tool, NOT mobile-first)
Max-width: 100% of viewport

Panel System (Collapsible):
  ┌─────────────────────────────────────────────────────────────┐
  │  Sidebar (260px) │  Main Content Area  │  Right Panel     │
  │  [fixed]         │  [flex:1]           │  (300px, fixed)  │
  │                  │                     │                  │
  │  Toggle: ⌘B      │  Canvas expands     │  Toggle: ⌘I      │
  │  (or click ←→)   │  when panels hidden │  (or click ←→)   │
  └─────────────────────────────────────────────────────────────┘

Panel States:
  - Both open:   Sidebar 260px + Canvas flex + Right 300px
  - Left hidden: Canvas expands + Right 300px
  - Right hidden: Sidebar 260px + Canvas expands
  - Both hidden:  Canvas = 100% width (full focus mode)

Panel Toggle Buttons:
  - Floating pill buttons at panel edges
  - Icon: ChevronLeft/ChevronRight (16px)
  - Hover: bg=Surface-3, radius=md
  - Keyboard: ⌘B (left), ⌘I (right), ⌘Shift+F (full focus)

═══════════════════════════════════════════════════════════════════
SCREEN 1: AUTHENTICATION / LOGIN
═══════════════════════════════════════════════════════════════════

Layout: Full-screen split — Left 45% brand panel, Right 55% form panel
Background: Surface (#0F172A)

LEFT PANEL (brand):
  Background: linear-gradient(135deg, #0F172A 0%, #1a0a0a 50%, #0F172A 100%)
  Animated circuit/flame pattern SVG (subtle, 5% opacity, animated drift)
  Top: BAZspark logo — flame icon (Lucide Flame, #E84040, 32px) + "BAZspark" text 28px 700
  Center:
    Large fire alarm icon (48px, #E84040, glow-red shadow)
    Heading: "Intelligent Fire Safety Engineering" — 22px 700 Text-1
    Sub: "NFPA 72-2022 · NEC 2022 · SOLAS · IMO · AI-Powered" — 12px Caption #38BDF8
    Divider line with small flame dots
    Feature list (3 items with check icons #22C55E, 14px):
      ✓ AI-Powered Detector Placement (NFPA 72 / SOLAS)
      ✓ Real-Time Multi-Standard Compliance
      ✓ Automated Cable, Conduit & BOQ Design
  Bottom: Version badge "v8.1 Production" — Surface-3, Caption

RIGHT PANEL (form):
  Background: Surface-2 (#1E293B)
  Top: "Welcome back" — Heading-2 Text-1
  Sub: "Sign in to your engineering workspace" — Body Text-3
  Form (max-width 380px, centered):
    Email field:
      Label: "Email" Caption Text-3
      Input: h=44px, bg=Surface, border=Border, radius=md
      Left icon: Mail (16px, Text-3)
      Focus: border=#38BDF8, glow-blue shadow
      Placeholder: "engineer@company.com" Text-3
    Password field:
      Label: "Password" Caption Text-3
      Input: same style as email
      Left icon: Lock, Right icon: Eye/EyeOff toggle
    Row: "Remember me" checkbox + "Forgot password?" link (#38BDF8)
    Submit button (full-width, h=44px, bg=#E84040, radius=md):
      Text: "Sign In" — 14px 600 white
      Hover: bg=#B91C1C, transform translateY(-1px), glow-red
      Loading state: spinner left side + "Authenticating..."
      Active: scale(0.98)
  Error state: red banner top of form, AlertCircle icon
  Bottom: "Don't have an account? Contact admin" — Body Text-3

═══════════════════════════════════════════════════════════════════
SCREEN 2: MAIN DASHBOARD
═══════════════════════════════════════════════════════════════════

Layout: Fixed sidebar (260px) + Top header (64px) + Main content area

SIDEBAR:
  Background: Surface-2 (#1E293B)
  Border-right: 1px solid Border
  Width: 260px, full height, fixed position
  Collapsible: ⌘B toggle, floating pill at edge

  LOGO SECTION (h=64px, border-bottom):
    Flame icon (20px #E84040) + "BAZspark" (18px 700 Text-1) + "v8.1" badge (Caption #38BDF8 bg-blue/10 px-2 rounded-full)

  NAV SECTION (padding 12px):
    Group label: "WORKSPACE" Caption Text-3 uppercase, mb-8
    Nav items (h=40px each, px-12, radius=md, gap-10):
      🏠 Dashboard      (LayoutDashboard icon) — ⌘1
      📁 Projects       (FolderOpen icon) — ⌘2
      🔴 Detectors      (Radio icon) — ⌘3
      〰  Cable Routing  (Cable icon)
      ⬡  Conduit        (Layers icon)
      ⚡  Circuits       (Zap icon)
      🛡  Safety Rules   (ShieldCheck icon) — NFPA 72 badge
      📊 BOQ & Reports   (BarChart3 icon)

    Separator 8px gap
    Group label: "MARINE ⚓" Caption Text-3 uppercase #0EA5E9
      ⚓ Vessel Overview  (Anchor icon)
      🗺  Zone Mapping     (Map icon)
      🔴 Detector Grid    (Radio icon)
      📡 Gas / UGLD       (Radio2 icon)
      🔊 PA / Alarm Zones (Volume2 icon)
      📋 Class Compliance  (ClipboardCheck icon)

    Separator 8px gap
    Group label: "AI & SYSTEM" Caption Text-3 uppercase
      🧠 AI Agent        (BrainCircuit icon) — purple accent
      🔄 Digital Twin     (RotateCcw icon)
      📤 BIM Import       (Upload icon)
      ⚙  Settings        (Settings icon) — ⌘,
      📋 Audit Log        (FileText icon)
      💊 Self-Healing     (Activity icon) — status dot

    Active state: bg=red/10, text=#E84040, icon=#E84040, left border 2px #E84040
    Marine active: bg=ocean/10, text=#0EA5E9, icon=#0EA5E9, left border 2px #0EA5E9
    AI active: bg=purple/10, text=#A78BFA, icon=#A78BFA, left border 2px #A78BFA
    Hover: bg=Surface-3, text=Text-1, transition 150ms

  BOTTOM SECTION (border-top, padding 12px):
    User avatar (32px circle, initials, bg=#E84040)
    Name: 14px 600 Text-1
    Role: 12px Text-3 "Fire Protection Engineer"
    Settings gear icon right side

TOP HEADER (64px):
  Background: Surface (#0F172A) with border-bottom
  Left: Current page breadcrumb (Home > Projects > Room Design)
  Center: Global search bar (max-width 400px):
    bg=Surface-2, border=Border, radius=full, h=36px
    Search icon left, "Search rooms, projects, standards..." placeholder
    Keyboard shortcut badge "⌘K" right side
  Right (gap-8):
    AI Agent button (BrainCircuit icon, purple glow if suggestions pending)
    Notifications bell — badge with count (red, animated pulse if >0)
    System health indicator (green dot + "System Online" 12px)
    User avatar dropdown

MAIN CONTENT (padding 24px):

  PAGE HEADER:
    "Dashboard" Heading-1 Text-1
    "BAZspark Engineering Workspace · NFPA 72-2022 / SOLAS / IMO" Body Text-3
    Right: "New Project" button (bg=#E84040, 14px 600, Plus icon, h=40px, radius=md)

  STATS ROW (4 cards, gap-16):
    Each card: bg=Surface-2, border=Border, radius=lg, padding=20px

    Card 1 — Active Projects:
      Icon container: 40x40 bg=blue/10 radius=md, Folder icon #38BDF8
      Value: 12 — 28px 700 Text-1 (countUp animation)
      Label: "Active Projects" Caption Text-3
      Trend: +2 this week, green arrow up, 12px #22C55E

    Card 2 — Rooms/Zones Designed:
      Icon: bg=green/10, Radio icon #22C55E
      Value: 847
      Label: "Rooms/Zones Designed"
      Trend: +34 today

    Card 3 — Compliance Rate:
      Icon: bg=red/10, ShieldCheck icon #E84040
      Value: 98.7% — animated progress ring (SVG circle, stroke #E84040)
      Label: "NFPA 72 / SOLAS Compliance"
      Sub: "2 violations active" — #F59E0B, AlertTriangle icon 12px

    Card 4 — System Health:
      Icon: bg=purple/10, Activity icon #A78BFA
      Value: "Healthy" — #22C55E
      Label: "Pipeline Status"
      Sub: "8 stages · 0 failures" — Body Text-3

  MAIN GRID (2 columns, gap-16, mt-24):

    LEFT COLUMN (flex:1.6):

      RECENT PROJECTS TABLE:
        Header: "Recent Projects" Heading-3 + "View All" link #38BDF8
        Table (full-width):
          Columns: Project | Type | Rooms/Zones | Status | Compliance | Modified | Actions
          Row height: 52px, border-bottom Border
          Status badges:
            "Active" bg=green/10 text=#22C55E radius=full px-8 py-2 Caption
            "Draft" bg=yellow/10 text=#F59E0B
            "Complete" bg=blue/10 text=#38BDF8
            "Marine" bg=ocean/10 text=#0EA5E9
          Compliance: progress bar (4px height, bg=Surface-3, fill=#22C55E or #E84040)
          Actions: Edit (pencil), View (eye), Delete (trash) icons — hover show
          Hover row: bg=Surface-3, transition 150ms
        Pagination: prev/next, page numbers, "Showing 1-8 of 24"

      PIPELINE STATUS CARD (mt-16):
        Header: "Pipeline Health" Heading-3 + live indicator (green pulse dot)
        8 stages grid (2x4):
          Each stage: bg=Surface-3, radius=md, padding 12px
          Icon left (colored), stage name 13px 600, status right
          Status icons: CheckCircle (#22C55E), XCircle (#E84040), Clock (#F59E0B), Minus (Text-3)
          Stages:
            Stage 0 — Input Contract    ✓ PASS  (FileCheck icon)
            Stage 1 — NFPA Spacing      ✓ PASS  (Ruler icon)
            Stage 2 — Coverage Verify   ✓ PASS  (Eye icon)
            Stage 3 — Safety Classify   ✓ PASS  (Shield icon)
            Stage 4 — Release Gates     ⚠ 1 WARN (Gate icon → Lock icon)
            Stage 5 — Evidence Package  ✓ PASS  (Package icon)
            Stage 6 — Rules Engine      ✓ PASS  (Brain icon)
            Stage 7 — Cable Routing     ✓ PASS  (Cable icon)
          Bottom: "Last run 2 min ago · 847ms total" Caption Text-3

    RIGHT COLUMN (flex:1):

      LIVE COMPLIANCE FEED:
        Header: "Live Safety Events" Heading-3 + "Pause" toggle
        Feed (max-height 280px, overflow-y scroll, custom scrollbar):
          Each item: left colored dot, timestamp Caption Text-3, message Body Text-2
          Types:
            🟢 PASS: #22C55E dot
            🔴 FAIL: #E84040 dot + bg=red/5
            🟡 WARN: #F59E0B dot
          Example items with real NFPA/SOLAS refs:
            "R-101 spacing verified NFPA §17.7.3.2.1" — 2s ago
            "CRITICAL: R-205 wall violation §17.6.3.1.1" — #E84040 highlighted
            "Battery sized 26Ah §10.6.7.1.1" — 15s ago
            "SOLAS VFZ-03: accommodation coverage verified §9.2.2.2.1" — 30s ago
        Empty state: "No active events" with shield icon

      NFPA/SOLAS GATE STATUS (mt-16):
        Header: "Release Gates (G1-G8)" Heading-3
        Gates list (gap-8):
          Each gate: h=36px, flex row
          Left: gate ID badge "G1" (bg=Surface-3, 11px 600, 24x24 rounded-sm)
          Middle: gate name 13px Text-2
          Right: status pill (PASS/FAIL/SKIP) — colored badges
          Gates: G1 Input Validation, G2 NFPA Spacing, G3 Coverage,
                 G4 Wall Distance, G5 Battery, G6 Voltage Drop,
                 G7 Fault Isolation, G8 Safety Tier
        Overall: "RELEASE: GREEN ✓" — full-width pill bg=#22C55E/10 text=#22C55E border border-green/20 mt-12

      AI AGENT SUGGESTIONS (mt-16) [P1 IMPROVEMENT — Background-First]:
        Header: "AI Proactive Suggestions" Heading-3 + BrainCircuit icon purple
        State: Collapsed by default. Purple glow indicator only.
        Expand: On "Run Analysis" (⌘+Enter) or explicit click.
        3 suggestion cards (scrollable):
          [CRITICAL — red border-left]:
            "Pump room detection non-compliant"
            "SOLAS §11.6.3.2 requires flame detectors in all pump rooms."
            [Fix Automatically] [Show Me]
          [WARNING — amber border-left]:
            "Battery calculation may be incorrect"
            "Room R-205 shows 18Ah but load analysis indicates 22Ah required."
            [Recalculate] [Explain]
          [INFO — blue border-left]:
            "Optimization available"
            "Cable routing in Zone VFZ-03 can be reduced by 34m (18%)."
            [Apply Optimization] [Preview]

      SYSTEM RESOURCES (mt-16):
        "Memory Service" row: Brain icon + status + provider name
        "Audit Chain" row: Link icon + "847 entries" + "SHA-256 verified"
        "AI Engine" row: Cpu icon + "QOMN-FIRE v2.0" + health dot

═══════════════════════════════════════════════════════════════════
SCREEN 3: PROJECT DETAIL — ROOM DESIGN (Building Mode)
═══════════════════════════════════════════════════════════════════

Layout: Same sidebar/header + full-width content
Panel System: Sidebar 260px (collapsible ⌘B) + Canvas (flex) + Right Panel 300px (collapsible ⌘I)

PAGE HEADER:
  Breadcrumb: Dashboard > Projects > "Office Complex B-12"
  Title: "Office Complex B-12" Heading-1 + edit icon inline
  Meta row: "Last modified 3h ago · 24 rooms · NFPA 72-2022 · Engineer: Ahmed"
  Right buttons:
    "Run Analysis" — bg=#E84040, PlayCircle icon, 14px 600 (⌘+Enter)
    "Export Report" — bg=Surface-3, Download icon, 14px (⌘+E)
    "Share" — bg=Surface-3, Share2 icon

BUILDING HIERARCHY (collapsible tree, top of content):
  🏢 Building B-12 [98.7% compliant]
    📶 Floor 4 — Roof [8 rooms, 100%]
    📶 Floor 3 — Offices [24 rooms, 99.2%]
    📶 Floor 2 — Labs [18 rooms, 96.5%] ⚠ 1 UNSAFE
    📶 Floor 1 — Lobby [12 rooms, 100%]
    📶 Floor G — Parking [16 rooms, 100%]

  Blocking Logic: ANY floor with UNSAFE room blocks entire building submission
  "safe_to_submit": false if any floor UNSAFE
  Visual: Red banner "safe_to_submit = FALSE (Floor 2 has UNSAFE room)"

MAIN GRID (3 columns with collapsible panels):

  LEFT PANEL (240px, collapsible ⌘B):
    "Rooms" header + search input + "Add Room" button (Plus icon, #38BDF8 text)
    Room list (scrollable):
      Each room item: h=48px, padding 12px, border-bottom
      Name: 14px 600 Text-1
      Sub: "42.0m² · Smoke" Caption Text-3
      Right: compliance badge (green check or red X)
      Active: bg=red/10, left border 2px #E84040
      Hover: bg=Surface-3

  CENTER PANEL (flex:1 — EXPANDS when side panels hidden):
    ROOM CANVAS (bg=Surface-3, radius=lg, overflow hidden):
      h=460px (expands to fill available height when panels hidden)
      Canvas controls top-right: Zoom+ (+), Zoom- (-), Fit (F), Grid toggle (G) — 4 buttons, Surface-2 bg

      [P1 IMPROVEMENT — CAD-First Interaction]:
        Mouse:
          Ctrl + Wheel = Zoom in/out (Revit/AutoCAD muscle memory)
          Middle Click + Drag = Pan canvas
          Double Middle Click = Fit to view
          Left Click = Select object
          Right Click = Context menu ("Analyze with AI", "Properties", "Delete")
        Keyboard:
          + / − = Zoom In / Out
          F = Fit Canvas
          G = Toggle Grid
          ⌘Z / CtrlZ = Undo
          ⌘⇧Z / Ctrl⇧Z = Redo
          Del = Delete Selected
          ⌘Enter = Run Analysis
          Space = Pan Canvas (hold)
          Arrow Keys = Nudge Selected Object

      SVG canvas:
        Room outline: stroke=#334155 2px
        Detectors: circles (r=12px, fill=#E84040/20, stroke=#E84040 2px)
          Center dot: r=4px fill=#E84040
          Coverage radius: dashed circle, stroke=#38BDF8/30
          Hover: tooltip showing detector ID, type, coverage, NFPA ref
          Selected: stroke=#E84040 3px, glow-red shadow
        Dead zones: red hatch pattern areas
        Walls: thick strokes #475569
        Doors: thin arcs
        Grid: 1px #334155/30 lines (toggleable)
        Scale indicator bottom-left: "1 unit = 1.0m" Caption Text-3
        Status bar bottom: Real-time cursor coordinates (X,Y) — JetBrains Mono 12px
      Bottom bar: room dimensions, area, detector count, coverage %

    ANALYSIS RESULTS (mt-16, 3 columns gap-12):
      Card "Coverage": large % number #22C55E + progress ring
      Card "Detectors": count + type breakdown
      Card "Status": NFPA COMPLIANT badge (green, ShieldCheck, animated checkmark)

    FLOOR COMPLIANCE SUMMARY (mt-16):
      "Floor 3 — Offices: 24 rooms, 98.7% compliant, 1 violation (R-205)"
      "Building Status: safe_to_submit = FALSE (Floor 2 has UNSAFE room)"

  RIGHT PANEL (300px, collapsible ⌘I):
    ROOM PROPERTIES FORM:
      Section header: "Room Configuration" Heading-3 + collapse chevron

      Tabs: "Basic" | "NFPA Settings" | "Advanced"
      [P1 IMPROVEMENT — Context Isolation]:
        "Marine" tab is COMPLETELY REMOVED from DOM in Building Mode.
        "NFPA Settings" tab is COMPLETELY REMOVED in Marine Mode.
        Project type is set at creation and cannot be switched without confirmation dialog.

      TAB: Basic
        Room ID: input (read-only with copy icon)
        Room Name: text input
        Detector Type:
          Select dropdown (custom styled):
            Options with icons: 🔴 Smoke Detector | 🌡 Heat Detector | 🔥 Flame Detector | 💨 CO Detector | 🔊 Beam Detector
            bg=Surface, border, radius=md, ChevronDown icon
        Ceiling Height (m): number input with ▲▼ buttons, unit badge "m"
        Room Use: select (Office/Corridor/Storage/Hazardous/Machinery/Accommodation/...)

      TAB: NFPA Settings
        Section "Spacing (NFPA 72 §17.7.3.2.1)":
          Listed Spacing S: number + "m" unit + help icon with tooltip
          Coverage Radius R: auto-calculated, locked field (= 0.7 × S)
          Wall Distance Max: auto-calculated (= S/2)
          Ceiling Type: select (Flat/Sloped/Peaked/Beam)
          HVAC Influence: toggle switch
        Section "Battery (NFPA 72 §10.6.7.1)":
          Standby Hours: 24h (readonly, code requirement)
          Alarm Duration: 5 min (readonly)
          Calculated Ah: live-computed value, #38BDF8
        Section "Voltage Drop (NFPA 72 §10.6.4)":
          Wire Gauge: select (AWG 14/12/10)
          Circuit Length: number input "m"
          Drop %: live-computed, color-coded (green <5%, yellow 5-8%, red >10%)
          Max Allowed: "10.0%" readonly
        Section "Fault Isolation (NFPA 72 §12.3.1)":
          Devices per segment: live count
          Max allowed: "32" readonly badge
          Isolators required: computed, badge

      TAB: Advanced
        SLC Class: A or B — radio buttons with icons
        NAC Class: A or B
        FACP Zones: number
        Hazardous Area: toggle → shows IEC 60079 / ATEX classification dropdown
        Export Format: IFC | DXF | JSON | Revit JSON checkboxes
        Marine Mode: toggle (if enabled, shows SOLAS tab — requires project type change confirmation)

      ACTIONS (bottom, border-top, padding-top 16px):
        "Apply Changes" full-width bg=#E84040
        "Reset to Defaults" text button, Text-3
        "Undo" (⌘Z) / "Redo" (⌘⇧Z) ghost buttons

═══════════════════════════════════════════════════════════════════
SCREEN 4: CABLE ROUTING & CONDUIT
═══════════════════════════════════════════════════════════════════

Layout: Full-width engineering view
Panel System: Both side panels hidden by default (full focus mode)

PAGE HEADER:
  "Cable Routing & Conduit Design" Heading-1
  "NEC 2022 · NFPA 72 §12.2 · Class A/B Circuits"
  Tabs: "Cable Routing" | "Conduit Fittings" | "Fill Calculator" | "Schedules" | "BOQ"

TAB: Cable Routing
  SPLIT VIEW (left 340px, right flex):

    LEFT PANEL "Circuit Configuration":
      Circuit Type section:
        SLC (Signaling Line Circuit):
          Radio + label + badge "Class A" / "Class B"
          NFPA ref: §12.2.2
        NAC (Notification Appliance Circuit):
          Same pattern

      Wire Gauge:
        Visual gauge selector (4 buttons in row):
          AWG 18 | AWG 16 | AWG 14 | AWG 12
          Each: border card, centered text, resistance below in Caption
          Selected: border=#E84040, bg=red/10, text=#E84040
        Active gauge data:
          Resistance: "10.07 Ω/km @ 75°C" — JetBrains Mono 13px #38BDF8
          NEC ref: "NEC Ch.9 Table 8" Caption Text-3
          Ampacity: "15A @ 60°C" Caption Text-3

      Cable Length:
        Input with "m" unit, max length computed and shown below in Caption

      Voltage Drop Calculator:
        Live calculation card (bg=Surface-3, rounded, padding 12px):
          Formula display: "V = I × 2 × R × L" JetBrains Mono 12px Text-3
          Inputs visible: I=0.150A, R=10.07Ω/km, L=0.250km
          Result: "V_drop = 0.756V (3.15%)" — large, color-coded
          Status: COMPLIANT ✓ or VIOLATION ✗ with NFPA §10.6.4 ref
          Progress bar showing % of 10% limit

      Devices Section:
        Add Device button + list (name, type, current draw, position)

      Run Route button: full-width #E84040 large

    RIGHT PANEL "Route Visualization":
      3D/2D view toggle (top right)
      SVG canvas (h=500px, bg=Surface-3):
        Panel/FACP position: square with thunderbolt icon
        Device positions: colored circles per type
        Route path: animated dashed line (stroke-dashoffset animation 1s linear infinite)
          Class A: two separate colored paths (outgoing blue, return orange)
          Class B: single path
        Obstacles: gray rectangles (walls, beams)
        Bends: arc indicators with degree labels
        Pull boxes: diamond shapes with "PB" label
        Hover segments: show length, bend angle tooltip
      Bottom stats bar: Total length, Bends, Compliance status

TAB: Conduit Fittings
  SPLIT (left 360px, right flex):
    LEFT "Conduit Configuration":
      Conduit Type (4 cards):
        EMT | UPVC Sch40 | UPVC Sch80 | RGD
        Each: icon, name, NEC article ref, select on click
      Trade Size (6 buttons): ½" | ¾" | 1" | 1¼" | 1½" | 2"

      NEC Fill Calculator live:
        Conductors list (add/remove rows):
          Wire gauge select | Diameter (auto-fill from NEC Table 5) | Count
        Result card:
          Internal area: "0.304 in²" — from NEC Table 4
          Conductor area: "0.029 in²" JetBrains Mono
          Fill %: large number, color-coded (≤40% green, >40% red)
          Max allowed: "40% (3+ conductors, NEC Ch.9 Table 1)"
          Recommend larger size if violation: yellow banner

      Bend Analysis:
        Add bend (angle, radius) inputs
        Cumulative total: progress ring 0-360°
        Warning at >360: "PULL BOX REQUIRED — NEC 358.26" red banner

    RIGHT "Fitting Schedule & BOM":
      Table header: "Material Schedule"
      Export: CSV, PDF, Revit JSON buttons
      Table:
        Catalog No | Description | Qty | Unit | NEC Ref | Weight | Unit Price | Total
        E90-050 | EMT Elbow 90° ½" | 4 | EA | 358.24 | 0.18kg | $2.50 | $10.00
        EC-050  | EMT Coupling ½"  | 12 | EA | 358.42 | 0.28kg | $1.20 | $14.40
        PB-GEN  | Pull Box        | 1  | EA | 358.26 | 0.50kg | $15.00 | $15.00
        Rows sorted by catalog number

      Summary footer:
        Total fittings: count | Total weight: kg | Total conduit: m | Total cost: $
        "Revit JSON ready" badge with SHA-256 hash display (12px mono)

TAB: Fill Calculator (standalone)
  Full-width centered card (max-width 680px):
    Header: "NEC Chapter 9 — Conduit Fill Calculator"
    Conduit selector + trade size selector (same as above)
    Internal area result card (prominent, bg=Surface-3, large number #38BDF8)
    Conductors table (add rows dynamically):
      Select: AWG 18/16/14/12/10 | Area auto-fills | diameter auto-fills | Qty
    Results:
      Donut chart (SVG, animated): filled portion vs available
      Center: "22.4%" large
      Legend: Used / Available / Limit
    Compliance: large COMPLIANT/VIOLATION banner
    Recommend: next size up if violation, with one-click upgrade

TAB: Schedules
  3 sub-tabs: Conduit Schedule | Fitting Schedule | Cable Schedule
  Each: full-width table, filter bar, export buttons (CSV/PDF/Excel)

TAB: BOQ (Bill of Quantities)
  BOQ Dashboard integration (see Screen 11)

═══════════════════════════════════════════════════════════════════
SCREEN 5: SAFETY RULES ENGINE
═══════════════════════════════════════════════════════════════════

NFPA 72 Rules Dashboard:
  Header: "Safety Rules Engine — NFPA 72-2022 Truth Maintenance System"

  TOP METRICS ROW (5 cards):
    Rules Active | Rules Fired | Violations | Safety Score | Confidence Level

  RULE CHAIN VISUALIZATION:
    Horizontal flow diagram (SVG):
      Nodes: Room Facts → Spacing Rules → Coverage → Detector Requirements → Compliance
      Animated flow particles on connecting arrows
      Node colors: green (fired+pass), red (fired+fail), gray (not fired)
      Click node: show rule details panel

  RULES TABLE:
    Filters: All | Fired | Not Fired | Violations | By NFPA Section | By SOLAS Section
    Columns: Rule ID | Standard Ref | Status | Priority | Fired At | Reason
    Each row expandable to show full rule details + matched facts
    Priority badges: SAFETY_CRITICAL (red), HIGH (orange), MEDIUM (yellow), INFO (blue)

  AUDIT LOG PANEL (bottom):
    Live scrolling audit entries
    Each: timestamp | rule_id | event_type | room_id | hash (12 chars mono)
    "Export Audit Chain" button (with SHA-256 integrity seal)

═══════════════════════════════════════════════════════════════════
SCREEN 6: BOQ & PROCUREMENT — BILL OF QUANTITIES
═══════════════════════════════════════════════════════════════════

PAGE HEADER:
  "Bill of Quantities" Heading-1
  "Office Complex B-12 · NFPA 72-2022 · Auto-generated from design"
  Right:
    "Import Price List" button (bg=Surface-3, Upload icon)
    "Export BOQ" button (bg=#E84040, Download icon)

STATS ROW (4 cards):
  "Total Line Items" — 1,247 — auto-generated from design
  "Total Project Cost" — $284,650 — +3.2% vs estimate
  "Supplier Quotes" — 18 — 12 approved, 6 pending
  "Lead Time" — 14d — Critical: 3 items

COST BREAKDOWN CHART:
  Bar chart (SVG, no external library):
    Detectors 32% $92,450 (red)
    Panels 23% $64,200 (blue)
    Cables 25% $71,380 (green)
    Conduit 10% $28,450 (yellow)
    Fittings 6% $18,200 (purple)
    NAC 12% $34,800 (orange)
    Power 7% $18,650 (gray)
    Labor 4% $9,970 (gray)

PROCUREMENT TIMELINE:
  BOQ Generated → Quotes Requested → Comparison → PO → Delivery
  Each step: date, status, responsible party

BOQ CATEGORIES (8 cards, 4x2 grid):
  Fire Detectors | Control Panels | Cables & Wires | Conduit & Raceway
  Fittings & Accessories | Notification Appliances | Power Supplies | Installation Labor
  Each: icon, count, total cost, click to expand detailed table

DETAILED BOQ TABLE:
  Columns: Item No | Description | Spec/NFPA Ref | Qty | Unit | Unit Price | Total | Supplier | Rating | Status
  Rows: expandable, show variants, alternatives, supplier comparison
  Actions: Edit price, Change supplier, Mark approved, Add alternative

SUPPLIER COMPARISON:
  Side-by-side table: Supplier | Unit Price | Lead Time | Rating | Certifications | Best Value
  Highlight: "Best Price" green, "Best Lead Time" blue, "Best Value" purple

COST ALERTS:
  Info: "3 items above estimate by >10%"
  Warning: "2 items have no supplier quote yet"
  Critical: "1 item (Beam Detectors) lead time exceeds project deadline"

APPROVAL WORKFLOW:
  Engineer Review → PM Approval → Client Approval → PO Issued
  Each step: status, date, approver name, digital signature hash

═══════════════════════════════════════════════════════════════════
SCREEN 7: MARINE MODULE — SOLAS / IMO / MED
═══════════════════════════════════════════════════════════════════

Module Identity: BAZspark Marine — Naval & Offshore Fire Detection Design
Color accent: #0EA5E9 (Ocean Blue) layered on base design system

[CONTEXT ISOLATION]: Marine module is ONLY accessible when project_type == "marine".
In Building Mode: Marine nav group is grayed out with tooltip "Switch to Marine project".

SIDEBAR INTEGRATION:
  Group label: "MARINE ⚓" Caption Text-3 uppercase #0EA5E9
  Nav items (all with ocean-blue active state):
    ⚓ Vessel Overview     (Anchor icon)
    🗺  Zone Mapping       (Map icon)
    🔴 Detector Grid      (Radio icon)
    📡 Gas / UGLD          (Radio2 icon)
    🔊 PA / Alarm Zones    (Volume2 icon)
    📋 Class Compliance    (ClipboardCheck icon)
    🌊 Offshore Platform   (Building2 icon)

7.1 VESSEL OVERVIEW:
  Vessel Type Selector (6 cards, 2x3 grid):
    Cargo Vessel | Passenger Ship | Tanker (Oil/Gas/Chemical)
    Offshore/FPSO | Ro-Ro/Ferry | Naval/Yacht
  Each: icon, SOLAS ref, key requirement, alert badge if applicable

  Vessel Profile Form (2-column):
    Vessel Name, IMO Number (7 digits validated), Flag State (ISO + emoji)
    Classification Society: multi-select pills (Lloyd's | DNV GL | BV | ABS | Class NK | RINA | CCS)
    Gross Tonnage, Ship Type, Year Built, Call Sign
    LOA, Beam, Depth, Freeboard Deck, Voyage Type
    Fire Zone Count, Accommodation Decks, Cargo Hold Count

  Import Plans: Dropzone for DXF/PDF/IFC — auto-parses fire zones
  Detected layers: FA_ZONES, FA_DETECTORS, FIRE_DOORS, FIRE_ZONES

7.2 ZONE MAPPING:
  Left: Zone List (VFZ / HFZ / Machinery Spaces)
    Each zone: ID badge, name, frames, area, detector count, compliance
  Right: Canvas — Ship plan view with zone boundaries
    VFZ: colored vertical bands | HFZ: horizontal lines per deck
    Fire doors: colored rectangles | Escape routes: dashed green
    Deck selector: Poop / Upper / Main / Lower / Tank Top

7.3 DETECTOR GRID:
  Standard tabs: SOLAS/IMO FSS | EN 54-5/7 | NFPA 72 §29 | ISO 7240
  Left: Detection Rules by SOLAS space category
    Accommodation Spaces (§9.2.2.2.1): Smoke mandatory, spacing ≤11m/≤22m
    Service Spaces (§9.2.2.2.2): Smoke or heat
    Control Stations (§9.2.2.2.3): Smoke, 2min response
    Machinery Spaces Cat A (§9.2.2.2.4): Smoke+Heat+Flame, 2 detectors/500m³
    Pump Room (Tankers): Flame ONLY — smoke PROHIBITED (red banner)
    Cargo Holds: by cargo type (smoke/CO/heat)
    Open Deck: MCP only, max 20m spacing
  Right: Canvas with detector symbols per IEC 60849 / IMO
    Smoke: circle S #0EA5E9 | Heat: circle H #F59E0B | Flame: circle F #E84040
    CO: circle CO #A78BFA | MCP: square hand #22C55E | UGLD: hexagon wave #38BDF8

7.4 GAS / UGLD:
  ATEX Zone Classification: Zone 0 (continuous) / Zone 1 (occasional) / Zone 2 (unlikely)
  Gas Type Matrix: LNG/LPG/Crude/H₂/CO/H₂S with LEL/UEL/Set Point/Detector Type
  UGLD Configuration: threshold dB slider, wind speed limit, coverage radius
  Canvas: ATEX zones overlay, gas detector positions, wind rose

7.5 PA / ALARM ZONES (SOLAS §6):
  General Emergency Alarm: 7 short + 1 long blast visual animation
  PA Zone: SPL calculator, speaker placement, muster list integration
  Coverage map: SPL heatmap (green=75dBA+, yellow=65-75, red<65)

7.6 FIXED SUPPRESSION INTERFACES:
  Table: Suppression System vs Detection Interlock per Space
  CO₂ Total Flood | Watermist | FM-200 | Deluge
  Each: SOLAS ref + detection requirements + interlock signal spec

7.7 CLASS COMPLIANCE REPORT:
  Checklist by society: IMO/SOLAS | Lloyd's | DNV GL | BV | ABS
  Each: expandable checklist with ☑/☐ items
  Certification Status: "READY FOR CLASS SURVEY ✓" or "ACTION REQUIRED — 3 items"
  Generate Submission Package: PDF + detector schedule + DXF + BOQ

7.8 OFFSHORE PLATFORM (conditional):
  Platform type: Fixed | Semi-sub | Jack-up | FPSO | FLNG
  SIL requirements: IEC 61511 mandatory, SIL 2 badge
  F&G Architecture diagram: Detectors → F&G Controller → DCS → Shutdown
  Open path IR, UV/IR flame, UGLD arrays, weatherproof MCPs

═══════════════════════════════════════════════════════════════════
SCREEN 8: AI ENGINEERING AGENT [P1 IMPROVEMENT — Background-First]
═══════════════════════════════════════════════════════════════════

Agent Identity: BAZspark AI — Conversational Fire Safety Engineering
Color accent: #A78BFA (Purple)

[BACKGROUND-FIRST BEHAVIOR]:
  - AI runs analysis continuously in background
  - UI shows ONLY: Purple glow indicator (subtle, top header)
  - CRITICAL violations: instant toast notification (red, dismissible)
  - ALL other suggestions: batched until explicit trigger

ENTRY POINTS:
  1. Sidebar nav item: "🧠 AI Engineering Agent" with "Ask BAZspark" badge
  2. Floating button: bottom-right 52px circle, bg=#A78BFA, BrainCircuit icon
     Badge: count of proactive suggestions (red pulse — CRITICAL only)
  3. Inline "Ask BAZspark" next to every NFPA/SOLAS reference
  4. Right-click on canvas: "Analyze with AI"
  5. Violation cards: "Fix with AI →" button
  6. Run Analysis (⌘+Enter): triggers full AI scan + suggestion panel

MAIN INTERFACE (3-column):

LEFT COLUMN (280px) — Context & Suggestions:
  "Current Context" card: project, vessel type, standard, active room
  "Proactive Suggestions" (auto-generated, COLLAPSED by default):
    Expand: Click purple glow indicator OR Run Analysis (⌘+Enter)
    [CRITICAL — red]: "Pump room detection non-compliant" — [Fix] [Show]
    [WARNING — amber]: "Battery calculation may be incorrect" — [Recalculate] [Explain]
    [INFO — blue]: "Cable routing optimization available" — [Apply] [Preview]
    [LEARNING — purple]: "Pattern recognized from similar projects" — [Apply] [View]
  "NFPA/SOLAS Quick Reference": searchable, recently used sections

CENTER COLUMN (flex:1) — CHAT INTERFACE:
  Conversation area (scrollable, max-height fills screen):
    User message: right-aligned, bg=purple/10, border-right purple, avatar initials
    Agent message: left-aligned, bg=Surface-2, border Border, avatar BrainCircuit icon

    Content types:
      1. Plain text: 14px Text-1, 1.7 line-height, markdown
      2. Code block: bg=Surface, JetBrains Mono 13px, copy button, language label
      3. Compliance result: green/red card with ShieldCheck/AlertTriangle
      4. Comparison table: full-width styled HTML table
      5. Action buttons: "Apply Fix" | "View in Canvas" | "Export" (inline)
      6. File attachment: icon + name + size + "Analyzed" badge
      7. Think-out-loud: collapsible "Reasoning" section, 12px Text-3 italic
      8. Typing indicator: three pulsing purple dots

  Pre-seeded example conversation:
    User: "Check if my vessel's accommodation detection meets SOLAS"
    Agent: [Analyzing...] → Full compliance check with fix buttons
    User: "Fix the paint locker issue"
    Agent: Replacing smoke → heat, with undo/view options

  INPUT AREA (fixed bottom):
    Attachment bar: drag & drop files (DXF, PDF, IFC, JSON, images), max 5 files, 50MB
    Quick action chips: "Check NFPA" | "Calculate battery" | "Optimize routing" | "SOLAS review" | "Generate report" | "Find violations" | "Explain §17.7.3.2.1" | "Compare vessels"
    Input row: Paperclip icon | Auto-expanding textarea (Shift+Enter newline, Enter send) | Microphone toggle (voice input) | Send button (purple circle, ArrowUp)
    Bottom disclaimer: "BAZspark AI may make mistakes. Always verify with licensed FPE." Caption Text-3 italic

RIGHT COLUMN (260px) — Tools & History:
  "Active Tools": toggles for NFPA Calculator, Project Scanner, Coverage Verifier, Report Generator, Cable Router, Marine Validator, Memory Search
  "Session History": last 10 sessions with message count, click to restore
  "Saved Responses": user-bookmarked agent responses

AGENT CONFIGURATION (Settings sub-tab):
  LLM Provider: OpenAI / Anthropic / Gemini / Local (Ollama)
  Model: dropdown per provider
  API Key: masked + test button
  Temperature: slider 0–1 (default 0.1 for engineering precision)
  Max tokens: number (default 4000)
  System prompt: textarea (pre-filled with NFPA/SOLAS context)
  Memory: toggle (uses mem0 / project memory)
  Proactive suggestions: toggle + frequency (realtime / hourly / manual)
  Voice input: toggle + language select (Arabic / English)

═══════════════════════════════════════════════════════════════════
SCREEN 9: DIGITAL TWIN & BIM
═══════════════════════════════════════════════════════════════════

9.1 DIGITAL TWIN:
  PAGE HEADER: "Digital Twin" — Building/Vessel B-12 · Real-time Sensor Status

  SPLIT VIEW (left 280px, right flex):
    Left: Building/Vessel Hierarchy tree
      Building → Floors → Rooms → Devices
      Each: online/offline status dot, detector count, last reading

    Right: 3D View (CSS 3D transform, mouse-draggable)
      Building floors as stacked rectangles
      Click floor: zoom to floor plan
      Device status: green (normal), yellow (warning), red (alarm), gray (offline)
      Hover device: tooltip with ID, type, last reading, status
      Legend: Normal / Warning / Alarm / Offline / Maintenance

    Live Sensor Feed (below hierarchy):
      Real-time readings: D-01 Lobby OK 4.2% | D-15 Corridor MAINT 12.1%
      Color-coded: green <5%, yellow 5-15%, red >15%

9.2 BIM IMPORT:
  Dropzone: "Drop BIM file here" — .rvt, .ifc, .dwg, .dxf, .json, max 500MB
  Geometry Preview: SVG plan view with room outlines
  Element Mapping: Revit Category → BAZspark Type (auto-mapped, editable)
    Rooms → Room | Walls → Obstacle | Doors → Opening | Windows → Opening
    Floors → Level | MEP Equipment → Device
  Import & Analyze button

═══════════════════════════════════════════════════════════════════
SCREEN 10: FACP DESIGN
═══════════════════════════════════════════════════════════════════

PAGE HEADER: "FACP Design" — Panel Configuration · Circuit Routing · Capacity Audit

SPLIT VIEW (left 1fr, right 1fr):
  Left: Panel Configuration
    Panel Model: Notifier NFS2-3030 / Simplex 4100ES / Siemens FC922
    SLC Capacity: 4 loops (readonly)
    Max Devices per Loop: 318 (readonly)
    NAC Circuits: 8 (readonly)
    Loop utilization: progress bars (SLC-1: 31/318, SLC-2: 142/318)

  Right: Circuit Diagram (SVG)
    FACP box with thunderbolt icon
    SLC loops: Class A (blue outgoing, orange return) or Class B (single path)
    Device nodes: circles with ID labels
    Isolator positions: ISO-1, ISO-2 diamonds
    Segment counts, isolator counts, capacity status

═══════════════════════════════════════════════════════════════════
SCREEN 11: REPORTS
═══════════════════════════════════════════════════════════════════

Report Types (3x3 grid cards):
  Building Reports: NFPA 72 Compliance | Cable Schedule | Battery Calculation | As-Built
  Marine Reports: SOLAS Compliance Certificate | Class Survey Submission | MED Equipment Schedule | Fire Control Plan | Gas Detection Report | Muster List Cross-Reference
  General: Full Project Report | Executive Summary | Client Presentation

Report Preview (full-width):
  Header: project name, date, engineer, digital signature area
  Sections: Executive Summary | Detector Placement | Cable Routing | Compliance Status
  Tables: styled with NFPA/SOLAS references
  Footer: SHA-256 hash, "Digitally signed by [Engineer]", page numbers
  Export: PDF (with digital signature) | DXF | Excel | Revit JSON

═══════════════════════════════════════════════════════════════════
SCREEN 12: SETTINGS — ALL BACKEND SETTINGS SURFACED
═══════════════════════════════════════════════════════════════════

Layout: Left settings nav (200px) + right content

SETTINGS NAV (categories):
  General | NFPA Configuration | NEC Standards | Marine Standards | AI & Memory |
  Pipeline | Security | Notifications | Export | About | RBAC

TAB: NFPA Configuration
  Detection Coverage (§17.7): Spacing S, R=0.7×S, wall distance S/2, dead air space
  Battery (§10.6.7): 24h standby, 5min alarm, safety factor 1.25×
  Voltage Drop (§10.6.4): Max 10%, ref temp 75°C, wire resistance table
  Fault Isolation (§12.3.1): Max 32 devices, SLC/NAC Class default

TAB: Marine Standards
  Flag state default | Classification society default
  Battery standby: "12h" readonly (SOLAS vs NFPA 72's 24h) with explanation
  MED type approval database: sync button
  ATEX zone defaults: Zone 1 default detector type
  Pyrotechnic signal: reminder toggle (SOLAS Chapter III)

TAB: AI & Memory
  LLM Provider: OpenAI/Gemini/Local + API key + model selector
  Temperature: 0.1 slider | Max tokens: 4000
  Proactive suggestions: toggle + frequency (realtime / hourly / manual)
  Voice input: toggle + Arabic/English
  Memory: toggle (mem0 / project memory)

TAB: Security
  AUDIT_HMAC_KEY: masked + generate + strength indicator
  Session timeout | Rate limiting | Environment badge (Development/Production)
  RBAC: User roles (Admin/Engineer/Viewer), permissions matrix

TAB: Export
  Default format: IFC | DXF | JSON | PDF | Revit JSON
  Revit integration: endpoint URL + test connection
  AutoCAD: DXF version (R2018/R2021)
  Schedule formats: checkboxes

TAB: Pipeline
  8 stage toggles (enable/disable each)
  Stage timeout settings (seconds)
  "Run Full Pipeline Test" button → live progress display

═══════════════════════════════════════════════════════════════════
SCREEN 13: AUDIT LOG & SELF-HEALING
═══════════════════════════════════════════════════════════════════

AUDIT LOG:
  SHA-256 Chain verification status (green check / red X)
  Table: Timestamp | Event | Rule | Room/Zone | Severity | Hash (12 chars)
  Export Audit Chain button with SHA-256 integrity seal
  Filter: All | Fired | Violations | By NFPA | By SOLAS

SELF-HEALING:
  Circuit Breaker state: CLOSED/OPEN/HALF-OPEN — animated state diagram
  Metrics: Success rate%, Failure count, Last failure time, Latency
  Recent events: scrollable log with colored dots
  Manual controls: "Reset Circuit", "Force Check" buttons
  AI Memory status: provider, entries, search

═══════════════════════════════════════════════════════════════════
KEYBOARD SHORTCUTS — GLOBAL
═══════════════════════════════════════════════════════════════════

Navigation:
  ⌘1 / Ctrl1     → Dashboard
  ⌘2 / Ctrl2     → Projects
  ⌘3 / Ctrl3     → Detectors
  ⌘, / Ctrl,     → Settings
  ⌘B / CtrlB     → Toggle Left Panel (collapse/expand)
  ⌘I / CtrlI     → Toggle Right Panel (collapse/expand)
  ⌘Shift+F       → Full Focus Mode (hide both panels)
  ⌘K / CtrlK     → Global Search
  ?              → Show Shortcuts Help
  Esc            → Close Modal / Cancel

Room Design / Canvas:
  Ctrl + Wheel   → Zoom In / Out (CAD muscle memory)
  Middle Click   → Pan Canvas (hold and drag)
  Double Middle  → Fit to View
  + / −          → Zoom In / Out (keyboard)
  F              → Fit Canvas
  G              → Toggle Grid
  ⌘Z / CtrlZ     → Undo
  ⌘⇧Z / Ctrl⇧Z   → Redo
  Del            → Delete Selected
  ⌘Enter         → Run Analysis
  Space          → Pan Canvas (hold)
  Arrow Keys     → Nudge Selected Object

General:
  ⌘S / CtrlS     → Save
  ⌘E / CtrlE     → Export
  ⌘N / CtrlN     → New Project
  ⌘P / CtrlP     → Print / Preview

AI Agent:
  ⌘ShiftA        → Open AI Agent Panel
  ⌘ShiftF        → Send File to AI
  /              → Focus AI Input (when panel open)

═══════════════════════════════════════════════════════════════════
TECHNICAL NOTES FOR STITCH / DEVELOPER
═══════════════════════════════════════════════════════════════════

Framework: React 18 + TypeScript + Tailwind CSS
State: Zustand (recommended for this scale) or Redux Toolkit
No mock data — all values from real API hooks:
  useHealth, useProjects, useDevices, useMarine, useAIAgent, useBOQ

API Endpoints (30+ routers):
  GET /api/health → system status
  GET /api/projects → project list
  GET /api/projects/:id/devices → device list
  POST /api/projects/:id/analyze → run analysis
  GET /api/marine/vessel/:id → vessel data
  GET /api/marine/zones → zone list
  GET /api/ai/status → AI provider status
  POST /api/ai/chat → send message to agent
  GET /api/boq/:projectId → bill of quantities
  WebSocket /ws → live event feed
  WebSocket /ws/marine → marine sensor feed

All NFPA/SOLAS values computed, not hardcoded:
  Coverage radius = 0.7 × S (from backend DensityOptimizer V7.3)
  Voltage drop = I × 2 × R × L (live in component)
  Battery Ah = (standby_current × 24h) + (alarm_current × 5min/60) × 1.25
  SOLAS battery: 12h standby (vs NFPA 72's 24h)
  Marine spacing: ≤11m from bulkhead, ≤22m between detectors (SOLAS §9.2.2.2.1)

Validation:
  room_id: non-empty, max 256 chars
  area_m2: >0, finite, <1,000,000
  ceiling_height_m: 0.1–30m
  polygon coordinates: finite, within ±1,000,000m
  wire gauges: AWG 6-18 only
  ps_voltage: >0, finite
  IMO number: 7 digits, validated format

Error Boundaries: Every major section (not full-page crash)
Accessibility: ARIA labels, keyboard navigation, focus management
Dark mode only (no light mode — engineering tool)
Responsive: min-width 1440px (P1 improvement from 1280px)
Performance: Virtualized lists for 1000+ items, debounced search, lazy-loaded 3D

═══════════════════════════════════════════════════════════════════
P1 IMPROVEMENTS SUMMARY (FROM EVALUATION)
═══════════════════════════════════════════════════════════════════

1. VIEWPORT & PANELS:
   - min-width: 1440px (was 1280px)
   - Left panel collapsible: ⌘B
   - Right panel collapsible: ⌘I
   - Full focus mode: ⌘Shift+F
   - Canvas expands to 100% when panels hidden

2. CONTEXT ISOLATION:
   - Marine tab REMOVED from DOM in Building Mode
   - NFPA tab REMOVED from DOM in Marine Mode
   - Project type set at creation, switch requires confirmation

3. CANVAS CAD INTERACTION:
   - Ctrl + Wheel = Zoom
   - Middle Click + Drag = Pan
   - Double Middle = Fit
   - Right Click = Context menu ("Analyze with AI")
   - Status bar: real-time cursor coordinates

4. AI BACKGROUND-FIRST:
   - Only CRITICAL violations show instantly (toast)
   - All other suggestions batched until Run Analysis (⌘+Enter)
   - Purple glow indicator replaces sidebar noise
   - AI panel expands on demand, not automatically

═══════════════════════════════════════════════════════════════════
END OF STITCH-READY PROMPT v8.1
═══════════════════════════════════════════════════════════════════
