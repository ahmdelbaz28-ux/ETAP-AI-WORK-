# 🖥️ ETAP GUI Agent Skill — Computer Use Agent (CUA) for ETAP

> **Mission**: Enable the AI agent to see the screen, control mouse/keyboard, and operate ETAP (and other engineering tools) like a human engineer.

---

## 🤖 What is the GUI Agent Skill?

A smart skill that lets the AI Agent:

| Capability | Details |
|---|---|
| 👁️ See the screen | Take screenshot and analyze with OCR + Vision |
| 🖱️ Control mouse | Click, Double-click, Right-click, Drag, Scroll |
| ⌨️ Control keyboard | Type, Hotkeys, Shortcuts |
| 📱 Open apps | ETAP, Revit, AutoCAD, SCADA, QGIS, ArcGIS |
| 🔍 Analyze problems | Read errors and identify solutions |
| ⚡ Execute solutions | Modify settings, run studies, generate reports |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│           AI REASONING ENGINE (LLM)         │
│     • Understands user request              │
│     • Plans multi-step workflows            │
│     • Verifies each step                    │
└────────────────────┬────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│         VISUAL PERCEPTION LAYER              │
│  • Screenshot capture (full/partial/region) │
│  • OCR text recognition                      │
│  • Icon/button detection                     │
│  • UI element classification                 │
└────────────────────┬────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│         ACTION EXECUTION LAYER              │
│  • Mouse: click, double-click, drag, scroll │
│  • Keyboard: type, hotkeys, shortcuts       │
│  • Window: open, close, resize, focus       │
│  • Application: launch, terminate, switch   │
└────────────────────┬────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│         FEEDBACK LOOP (Verification)         │
│  • Capture result screenshot                │
│  • Verify action succeeded                  │
│  • Detect errors/warnings                   │
│  • Adjust next step                         │
└─────────────────────────────────────────────┘
```

---

## 🔄 The CUA Loop (Computer Use Agent)

The agent operates in a continuous loop:

```
1. OBJECTIVE INPUT ← User says: "Open ETAP and run Load Flow"
         ↓
2. SCREENSHOT CAPTURE ← Capture screen
         ↓
3. VISUAL ANALYSIS ← Analyze: ETAP open? Bus A visible?
         ↓
4. ACTION DECISION ← Decide: open ETAP → go to One-Line → click Run
         ↓
5. ACTION EXECUTION ← Execute: Click, Type, Hotkey
         ↓
6. VERIFICATION ← Verify: study completed? errors?
         ↓
7. REPEAT OR EXIT ← if incomplete go to 2, if complete tell user
```

---

## 💻 Core Code (Python)

### Screen Capture & Analysis

```python
import pyautogui
import pytesseract
import cv2

def capture_full_screen():
    return pyautogui.screenshot()

def find_text_position(screenshot, target_text):
    # OCR reads text and finds its location
    text = pytesseract.image_to_string(screenshot)
    # Returns coordinates (x, y)
    return (x, y)
```

### Mouse & Keyboard Control

```python
class MouseController:
    def click(self, x, y):
        pyautogui.click(x, y)

    def double_click(self, x, y):
        pyautogui.doubleClick(x, y)

class KeyboardController:
    def type_text(self, text):
        pyautogui.typewrite(text)

    def hotkey(self, *keys):
        pyautogui.hotkey(*keys)  # Ctrl+S, Alt+F4, etc.
```

### ETAP Controller (full example)

```python
class ETAPController:
    def launch_etap(self, project_path=None):
        subprocess.Popen(["C:/.../ETAP.exe", project_path])
        time.sleep(15)  # Wait for loading

    def run_load_flow(self):
        # Navigate: Study Case → Load Flow
        self.click("Study Case")
        self.click("Load Flow")
        # Press F5 to run
        self.hotkey('f5')
        # Wait for convergence
        return self.wait_for_convergence()

    def get_bus_voltage(self, bus_name):
        # Find bus on One-Line
        screenshot = capture_full_screen()
        pos = find_text_position(screenshot, bus_name)
        # Double-click to open properties
        self.double_click(pos[0], pos[1])
        # Read voltage value
        return voltage
```

---

## 🎯 Usage Examples

### Example 1: Open ETAP and run a study

```python
agent = ETAPGUIAgent()
agent.open_etap("C:/Projects/MyProject.etz")
success, msg = agent.run_study("load_flow")
if success:
    voltage = agent.get_bus_voltage("Bus_A")
    print(f"Bus A Voltage: {voltage} pu")
agent.close_etap()
```

### Example 2: Batch settings modification

```python
transformers = [("T-1", "MVARating", 1500),
                ("T-2", "MVARating", 2000)]
for name, prop, value in transformers:
    agent.modify_element(name, prop, value)
```

### Example 3: Smart problem solving

```python
agent.solve_problem("voltage_drop")
# 1. Run Load Flow
# 2. Check Voltage
# 3. Suggest cable upgrade
# 4. Apply solution
# 5. Verify result
```

---

## 🔒 Safety Rules

| Rule | Details |
|---|---|
| Don't gamble | Don't operate breakers or change protection settings without human confirmation |
| Read-only by default | Start with Monitoring and Analysis, control after explicit permission |
| Failsafe | Move mouse to corner = immediate stop (pyautogui.FAILSAFE) |
| Timeout | Each operation has a time limit |
| Log everything | Record every action for Audit trail |

---

## 🔗 Integration with ETAP Expert Skill

```python
class ETAPIntelligentAgent:
    def __init__(self):
        # Knowledge (ETAP Expert Skill)
        self.knowledge = load_skill("etap-expert-skill.md")
        # Execution (GUI Agent)
        self.gui = ETAPGUIAgent()
        # Reasoning (LLM)
        self.llm = LLMVisionController(api_key)

    def handle_request(self, user_request):
        # 1. Analyze with Expert Skill
        analysis = self.analyze_with_skill(user_request)

        # 2. Execute in ETAP via GUI
        if analysis['requires_gui']:
            self.gui.open_etap()
            for step in analysis['steps']:
                self.execute_step(step)
            results = self.capture_results()
            return results
```

---

## 📦 Technical Requirements

```bash
# Install required libraries
pip install pyautogui
pip install pytesseract
pip install pillow
pip install opencv-python
pip install numpy
pip install pywin32  # for Windows
pip install openai   # for LLM integration

# Install Tesseract OCR
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Linux: sudo apt-get install tesseract-ocr
```

---

## ✅ Summary

| Feature | GUI Agent Skill |
|---|---|
| Supported apps | ETAP, Revit, AutoCAD, SCADA, QGIS, ArcGIS |
| Capabilities | See, Click, Type, Analyze, Solve |
| Safety | Failsafe, Confirmation, Logging |
| Intelligence | LLM integration for Decision Making |
| Integration | Works with ETAP Expert Skill |

---

## 🧠 Workflow Integration

### When to use the GUI Agent

The GUI Agent is invoked when the user request requires actual interaction with a desktop application (ETAP, Revit, AutoCAD, etc.). It is NOT invoked for:

- Pure knowledge questions (handled by ETAP Expert Skill)
- Numerical studies on a system spec (handled by PowerSystemEngine)
- API-only ETAP operations (handled by etap_integration/)

### Decision matrix

```
User Request
    ↓
┌─────────────────────────────────┐
│ Does the request require        │
│ interacting with a desktop app? │
└────────────┬────────────────────┘
             ↓
    ┌────────┴────────┐
    YES               NO
    ↓                 ↓
GUI Agent         Expert Skill
(needs human      (knowledge
confirmation)     only)
```

### Classification

The agent classifies user requests into 4 modes:

1. **analyze** — Read-only inspection (screenshots, OCR, reporting)
2. **monitor** — Continuous monitoring of running studies
3. **control** — Modify settings, run studies (requires explicit confirmation)
4. **solve** — Multi-step problem-solving workflow

### Response Formats

#### Format A: Analyze Request
```
👁️ GUI AGENT — ANALYZE MODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Your Request:** [question]
**Mode:** Analyze (read-only)
**Target App:** [ETAP / Revit / AutoCAD / SCADA / QGIS / ArcGIS]

**PLANNED STEPS:**
1. Launch [app]
2. Capture initial screenshot
3. OCR-analyze the screen
4. Identify UI elements
5. Report findings

**SAFETY:** Read-only — no modifications will be made.

**REQUIRES:** Human confirmation to proceed.
```

#### Format B: Monitor Request
```
📊 GUI AGENT — MONITOR MODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Your Request:** [question]
**Mode:** Monitor (passive observation)
**Target App:** [app]
**Duration:** [seconds/minutes]

**MONITORING POINTS:**
1. Study convergence status
2. Error/warning dialogs
3. Progress indicators
4. Result availability

**SAFETY:** Passive observation only.
```

#### Format C: Control Request (requires confirmation)
```
🖱️ GUI AGENT — CONTROL MODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Your Request:** [question]
**Mode:** Control (modifies application state)
**Target App:** [app]

**PLANNED ACTIONS:**
1. [action 1]
2. [action 2]
3. [action 3]

⚠️ WARNING: This will modify the application state.

**CONFIRMATION REQUIRED:** Reply "CONFIRM" to execute, "CANCEL" to abort.

**SAFETY RULES ACTIVE:**
- Failsafe enabled (mouse to corner = stop)
- Timeout: 60 seconds per action
- Full audit log will be recorded
```

#### Format D: Solve Request (multi-step)
```
⚡ GUI AGENT — SOLVE MODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Your Request:** [question]
**Mode:** Solve (multi-step problem-solving)
**Target App:** [app]

**WORKFLOW:**
1. Analyze current state
2. Identify problem
3. Propose solution
4. Apply solution (requires confirmation)
5. Verify result
6. Report outcome

**INTEGRATION:**
- ETAP Expert Skill: knowledge base
- GUI Agent: execution
- LLM Vision: decision making

⚠️ Steps 4 requires explicit confirmation.
```

---

## 🛠️ Fallback Behavior

When the GUI Agent cannot run (e.g., on a headless server, HF Space, or missing deps), it must:

1. Detect unavailable dependencies (pyautogui, pytesseract, etc.)
2. Return a clear "GUI agent unavailable" response
3. Suggest the ETAP Expert Skill as alternative
4. Never crash the application

```python
def answer(self, question: str) -> dict:
    if not self._deps_available():
        return {
            "classification": "unavailable",
            "format": "U",
            "response": (
                "⚠️ GUI AGENT UNAVAILABLE\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "The GUI Agent requires desktop dependencies "
                "(pyautogui, pytesseract, opencv) which are not "
                "available in this environment.\n\n"
                "**Suggested alternative:** Use the ETAP Expert Skill "
                "(study_type='etap_expert') for knowledge-based analysis.\n\n"
                "**To enable the GUI Agent:**\n"
                "1. Run on a desktop environment (Windows/Linux/macOS)\n"
                "2. Install: pip install pyautogui pytesseract opencv-python\n"
                "3. Install Tesseract OCR\n"
                "4. Set ETAP_GUI_AGENT_ENABLED=true"
            ),
            "fallback_reason": "dependencies_unavailable",
        }
    # ... normal processing
```

---

## 📋 Audit Log Format

Every GUI Agent action must be logged:

```json
{
  "timestamp": "2026-06-24T12:00:00Z",
  "action": "click",
  "target": "Study Case menu",
  "coordinates": [120, 45],
  "screenshot_before": "audit/before_001.png",
  "screenshot_after": "audit/after_001.png",
  "result": "success",
  "duration_ms": 250,
  "user_confirmed": true
}
```

---

## 🎯 Standards & Compliance

- **Safety**: pyautogui.FAILSAFE = True (always)
- **Privacy**: Screenshots stored locally only, never transmitted
- **Audit**: Every action logged with before/after screenshots
- **Timeout**: Default 60 seconds per action, configurable
- **Confirmation**: Control and Solve modes require explicit user confirmation

---

> **END OF ETAP GUI AGENT SKILL**
>
> This skill enables autonomous operation of engineering desktop applications
> with full safety, audit, and human-in-the-loop confirmation.
