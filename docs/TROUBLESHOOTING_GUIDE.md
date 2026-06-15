# Troubleshooting Guide

## Table of Contents

1. Introduction
2. Common Issues and Solutions
3. Installation Problems
4. Configuration Issues
5. ETAP Integration Issues
6. Calculation Engine Issues
7. Security/Authentication Issues
8. Performance Issues
9. Deployment Issues
10. Docker/Container Issues
11. Error Code Reference
12. Diagnostic Procedures
13. Support Escalation Process

---

## 1. Introduction

### Purpose

This Troubleshooting Guide provides comprehensive diagnostic and resolution procedures for the ETAP AI Engineering Platform. It is intended for system administrators, DevOps engineers, and support personnel responsible for operating and maintaining the platform.

### Scope

This guide covers all components of the ETAP AI Platform including:
- Multi-Agent Orchestration System (agents/orchestrator.py)
- ETAP COM Automation Interface (etap_integration/etap_com.py)
- Calculation Engines (load_flow, fault_analysis, relays)
- RAG Knowledge Engine (knowledge/rag_engine.py)
- Security Framework (security/security_framework.py)
- Reporting Engine (reporting/advanced_reports.py)
- Mastra AI Agent Framework (src/mastra/)
- Docker/Kubernetes Deployment Infrastructure

### Prerequisites

Before troubleshooting, ensure you have:
- Access to log files (default: `./logs/`)
- Access to the monitoring dashboard (if configured)
- Administrative access to the host system
- ETAP credentials (for ETAP-related issues)
- Environment configuration (.env file contents)

### Log File Locations

| Component | Log Location | Format |
|-----------|-------------|--------|
| Python Backend | `./logs/python-backend.log` | JSON |
| Mastra Server | `./logs/mastra-server.log` | JSON |
| ETAP COM | `./logs/etap-com.log` | JSON |
| Security/Auth | `./logs/security.log` | JSON |
| Calculation Engine | `./logs/calculation.log` | JSON |
| RAG Engine | `./logs/rag-engine.log` | JSON |
| Docker (container) | `docker logs etap-platform` | stdout/stderr |

---

## 2. Common Issues and Solutions

### Issue 2.1: Platform fails to start

**Symptoms:**
- `docker-compose up` exits immediately
- `python main.py` crashes on startup
- Health check endpoint returns 503

**Root Causes:**
- Missing or misconfigured `.env` file
- Port conflict (ports 3000 or 8000 already in use)
- Missing Python or Node.js dependencies
- Database file is corrupted

**Resolution Procedure:**

1. Check if another process is using required ports:
   ```
   netstat -ano | findstr :3000
   netstat -ano | findstr :8000
   ```
   Kill the occupying process: `taskkill /PID <PID> /F`

2. Verify environment configuration:
   ```
   diff .env.example .env
   ```
   Ensure all required variables are set: OPENAI_API_KEY, JWT_SECRET_KEY, DATABASE_URL.

3. Validate Python dependencies:
   ```
   pip check
   pip install -r requirements.txt --force-reinstall
   ```

4. Check Node.js dependencies:
   ```
   pnpm install --force
   pnpm build
   ```

5. Verify database integrity:
   ```
   python -c "import sqlite3; conn = sqlite3.connect('mastra.db'); conn.execute('SELECT 1'); conn.close()"
   ```
   If corrupted, restore from backup: `cp backups/mastra_latest.db ./mastra.db`

6. Check the startup logs for specific errors:
   ```
   cat logs/python-backend.log | grep ERROR
   cat logs/mastra-server.log | grep ERROR
   ```

**Verification Steps:**
```
curl http://localhost:3000/health
# Expected: {"status": "healthy", "version": "1.0.0"}
```

**Prevention Measures:**
- Run `./quickstart.sh` which validates all prerequisites before starting
- Use Docker health checks to auto-restart on failure
- Configure log rotation to prevent disk-full conditions

---

### Issue 2.2: API requests time out

**Symptoms:**
- HTTP 504 Gateway Timeout errors
- `asyncio.TimeoutError` in logs
- Frontend shows "Request Timed Out" messages

**Root Causes:**
- Calculation engine is overloaded with large systems (500+ buses)
- Orchestrator agent is stuck on a non-converging study
- ETAP COM operation is hung waiting for ETAP to respond
- Insufficient worker threads in the async pool

**Resolution Procedure:**

1. Check active workflow count:
   ```
   curl http://localhost:8000/metrics | grep active_workflows
   ```

2. List stuck tasks:
   ```
   python -c "from agents.orchestrator import get_orchestrator; o=get_orchestrator(); print(o.get_stuck_tasks(timeout_minutes=5))"
   ```

3. Cancel hung workflows:
   ```
   curl -X POST http://localhost:8000/api/v1/tasks/<task_id>/cancel
   ```

4. Increase timeout configuration in `.env`:
   ```
   TASK_TIMEOUT_SECONDS=300
   WORKFLOW_TIMEOUT_SECONDS=600
   ```

5. Restart the affected service:
   ```
   docker-compose restart etap-platform
   ```

**Verification Steps:**
```
curl http://localhost:3000/health/detailed
# Check that all components report "healthy"
```

**Prevention Measures:**
- Set realistic timeouts based on system size
- Implement circuit breakers for long-running operations
- Monitor active task count and set alerts at 80% of capacity

---

### Issue 2.3: Reports fail to generate

**Symptoms:**
- Report generation returns error
- PDF/DOCX/XLSX output files are empty or corrupt
- `ReportAgent` execution status shows `FAILED`

**Root Causes:**
- Missing report template files
- Disk space full in `./reports/` directory
- Required Python libraries not installed (reportlab, python-docx, openpyxl)
- Special characters in data that break the report formatter

**Resolution Procedure:**

1. Check disk space:
   ```
   df -h ./reports
   dir ./reports
   ```

2. Verify report dependencies:
   ```
   pip list | findstr reportlab
   pip list | findstr python-docx
   pip list | findstr openpyxl
   ```

3. Clear the report queue:
   ```
   rm -rf ./reports/pending/*
   ```

4. Test with a minimal report:
   ```
   python -c "
   from reporting.advanced_reports import ReportAgent
   agent = ReportAgent()
   result = agent.generate_test_report()
   print(f'Test report: {result}')
   "
   ```

5. Check for encoding issues in input data (looking for non-ASCII characters in system names).

**Verification Steps:**
```
python -c "
from reporting.advanced_reports import get_report_agent
agent = get_report_agent()
# Verify the agent initializes without errors
print('ReportAgent ready')
"
```

**Prevention Measures:**
- Set up automatic disk usage monitoring on the reports volume
- Sanitize input data before passing to report generators
- Run monthly report generation tests via cron

---

## 3. Installation Problems

### Issue 3.1: pip install fails

**Symptoms:**
- `pip install -r requirements.txt` exits with errors
- Conflicting dependency versions
- Package not found errors

**Common Errors and Solutions:**

**Error: `Microsoft Visual C++ 14.0 is required`**
- Install Microsoft C++ Build Tools from https://visualstudio.microsoft.com/visual-cpp-build-tools/
- Or use pre-compiled wheels: `pip install --only-binary=:all: -r requirements.txt`

**Error: `No matching distribution found for chromadb`**
- Ensure Python 3.10 or 3.11 is installed: `python --version`
- Install with platform specifier: `pip install chromadb --index-url https://pypi.org/simple/`

**Error: `sentence-transformers requires torch`**
- Install PyTorch first: `pip install torch --index-url https://download.pytorch.org/whl/cpu`
- Then proceed with requirements

**Resolution Steps:**

1. Create a clean virtual environment:
   ```
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. Upgrade pip and setuptools:
   ```
   python -m pip install --upgrade pip setuptools wheel
   ```

3. Install requirements in stages:
   ```
   pip install numpy pandas scipy
   pip install -r requirements.txt
   ```

**Verification:**
```
python -c "import chromadb; import torch; import transformers; print('All core modules loaded')"
```

---

### Issue 3.2: pnpm install fails

**Symptoms:**
- `pnpm install` exits with non-zero code
- Native module build failures (node-gyp)
- Version mismatches in lockfile

**Resolution Steps:**

1. Verify Node.js version:
   ```
   node --version  # Required: >= 18.x
   ```

2. Clear pnpm cache and node_modules:
   ```
   rm -rf node_modules
   pnpm store prune
   ```

3. Install with frozen lockfile:
   ```
   pnpm install --frozen-lockfile
   ```

4. For node-gyp errors on Windows, install build tools:
   ```
   npm install --global windows-build-tools
   ```

**Verification:**
```
pnpm build
# Expected: Build completed successfully
```

---

## 4. Configuration Issues

### Issue 4.1: Environment variables not loading

**Symptoms:**
- `KeyError` on environment variable access
- Default values being used instead of configured values
- `None` returned for required settings

**Resolution Steps:**

1. Verify the `.env` file exists and has correct permissions:
   ```
   dir .env
   ```

2. Check for syntax errors in `.env` (no spaces around `=`, no quotes unless needed):
   ```
   # BAD
   API_KEY = "my-key"
   # GOOD
   API_KEY=my-key
   ```

3. Test loading in Python:
   ```
   python -c "
   from dotenv import load_dotenv
   import os
   load_dotenv()
   assert os.getenv('OPENAI_API_KEY') is not None, 'OPENAI_API_KEY not set'
   assert os.getenv('JWT_SECRET_KEY') is not None, 'JWT_SECRET_KEY not set'
   print('Environment loaded successfully')
   "
   ```

**Required Environment Variables:**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| OPENAI_API_KEY | Yes | - | OpenAI API key for LLM access |
| JWT_SECRET_KEY | Yes | - | Secret for JWT token signing |
| DATABASE_URL | No | file:mastra.db | Database connection string |
| LOG_LEVEL | No | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| CACHE_TTL | No | 3600 | Cache time-to-live in seconds |
| RATE_LIMIT | No | 100 | API rate limit per minute |
| ETAP_EXECUTABLE | No | auto-detect | Path to ETAP executable |

---

### Issue 4.2: Database connection failures

**Symptoms:**
- `SQLAlchemy` connection errors in logs
- `mastra.db` file is missing or locked
- Read/write permission errors

**Resolution Steps:**

1. Check if the database file exists and is accessible:
   ```
   dir mastra.db
   ```

2. Verify SQLite file integrity:
   ```
   python -c "
   import sqlite3
   conn = sqlite3.connect('mastra.db')
   cursor = conn.execute('PRAGMA integrity_check')
   print(cursor.fetchone())
   conn.close()
   "
   ```
   Expected result: `('ok',)`

3. If the database is locked, check for other processes:
   ```
   python -c "
   import psutil
   for proc in psutil.process_iter(['pid', 'name']):
       if 'python' in proc.info['name']:
           print(f'Python process: {proc.info[\"pid\"]}')
   "
   ```

4. For permission issues, set correct ACLs on Windows:
   ```
   icacls mastra.db /grant "Everyone:(R,W)"
   ```

5. Restore from backup if corrupted:
   ```
   copy /Y backups\mastra_latest.db mastra.db
   ```

---

## 5. ETAP Integration Issues

### Issue 5.1: ETAP COM connection fails

**Symptoms:**
- `ERR-001: ETAP_COM_CONNECTION_FAILED`
- `pythoncom.com_error` in logs
- ETAP window does not open
- `ETAPAutomation` fails on `__enter__`

**Root Causes:**
- ETAP is not installed on the machine
- ETAP COM components are not registered
- Running on Linux/macOS (COM is Windows-only)
- ETAP version incompatibility
- Antivirus blocking COM instantiation
- ETAP already running without automation permissions

**Resolution Procedure:**

1. Verify ETAP is installed:
   ```
   python -c "
   import winreg
   with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\ETAP') as key:
       version = winreg.QueryValueEx(key, 'Version')
       print(f'ETAP Version: {version}')
   "
   ```

2. Register ETAP COM components:
   ```
   cd "C:\Program Files\ETAP\ETAP xx.x"
   regsvr32 ETAPAutomation.dll
   ```

3. Test COM instantiation:
   ```
   python -c "
   import pythoncom
   import win32com.client
   pythoncom.CoInitialize()
   try:
       etap = win32com.client.Dispatch('ETAP.Application')
       print('ETAP COM Dispatch successful')
       etap.Quit()
   except Exception as e:
       print(f'COM Dispatch failed: {e}')
   finally:
       pythoncom.CoUninitialize()
   "
   ```

4. Check if ETAP is already running (only one instance allowed):
   ```
   tasklist | findstr etap.exe
   ```
   If running, either use the existing instance or close it: `taskkill /F /IM etap.exe`

5. Verify that ETAP is configured for automation:
   - Open ETAP manually
   - Go to Tools > Options > Automation
   - Ensure "Enable COM Automation" is checked
   - Note: This setting may require restarting ETAP

6. If running as a service, ensure the service has "Allow service to interact with desktop" checked, or run the ETAP agent as the logged-in user.

**Verification Steps:**

```
python -c "
from etap_integration.etap_com import ETAPAutomation
with ETAPAutomation(visible=False) as etap:
    version = etap.get_version()
    print(f'ETAP connected: {version}')
"
```

**Log Files to Check:**
- `./logs/etap-com.log`
- Windows Event Viewer: Applications and Services Logs

**Prevention Measures:**
- Ensure ETAP is installed as part of the deployment process
- Pre-register COM components during setup
- Use a dedicated service account with desktop interaction permissions
- Implement retry logic in `etap_com.py` with exponential backoff

---

### Issue 5.2: ETAP project fails to open

**Symptoms:**
- `ERR-002: ETAP_PROJECT_OPEN_FAILED`
- `FileNotFoundError` or `COMError` in logs
- ETAP shows "Unable to open project" dialog

**Root Causes:**
- Project file path is invalid or contains spaces
- Project file is from a newer/older version of ETAP
- Project file is corrupted
- Insufficient file permissions
- Unicode characters in path

**Resolution Steps:**

1. Verify the project file exists:
   ```
   dir "C:\Projects\MyProject.edb"
   ```

2. Check file permissions:
   ```
   icacls "C:\Projects\MyProject.edb"
   ```

3. Test opening in ETAP manually:
   - Open ETAP
   - File > Open > Select project
   - Note any error messages from ETAP itself

4. Check ETAP version compatibility:
   ```
   python -c "
   with open('C:\\Projects\\MyProject.edb', 'rb') as f:
       header = f.read(50)
       print(f'File header: {header[:20].hex()}')
       # ETAP version is encoded in the header
   "
   ```

5. If the file path contains spaces, use the short path (8.3 format):
   ```
   python -c "
   import win32api
   short_path = win32api.GetShortPathName(r'C:\My Long Path\Project.edb')
   print(f'Short path: {short_path}')
   "
   ```

6. For corrupted files, restore from backup:
   ```
   copy /Y "C:\Backups\Projects\MyProject.edb" "C:\Projects\MyProject.edb"
   ```

**Verification:**
```
python -c "
from etap_integration.etap_com import ETAPAutomation
with ETAPAutomation(visible=False) as etap:
    proj = etap.open_project(r'C:\Projects\MyProject.edb')
    assert proj is not None, 'Failed to open project'
    print(f'Project opened: {proj.name}')
    proj.close()
"
```

---

### Issue 5.3: ETAP study execution fails

**Symptoms:**
- `ERR-003: ETAP_STUDY_EXECUTION_FAILED`
- Study returns `success=False` with error message
- ETAP shows calculation errors
- Results contain NaN or infinite values

**Root Causes:**
- Load flow diverges due to system data issues
- Missing study configuration parameters
- ETAP license limit reached (concurrent study cap)
- Input data validation errors in ETAP

**Resolution Steps:**

1. Check ETAP license status:
   ```
   python -c "
   from etap_integration.etap_com import ETAPAutomation
   with ETAPAutomation(visible=False) as etap:
       license_info = etap.get_license_info()
       print(f'License: {license_info}')
   "
   ```

2. Run study with verbose logging enabled:
   ```
   python -c "
   from etap_integration.etap_com import ETAPAutomation, ETAPStudyType
   with ETAPAutomation(visible=False) as etap:
       proj = etap.open_project(r'C:\Projects\MyProject.edb')
       proj.set_log_level('DEBUG')
       result = proj.run_study(ETAPStudyType.LOAD_FLOW)
       print(f'Success: {result.success}')
       print(f'Errors: {result.error}')
       print(f'Log: {result.log}')
   "
   ```

3. Validate the system data before running the study:
   - Check for isolated buses (no connection to any source)
   - Verify generator ratings and dispatch settings
   - Check load values are reasonable
   - Verify transformer tap settings

4. For load flow divergence:
   - Increase the maximum iteration count: `proj.set_study_parameter('MaxIterations', 50)`
   - Use a flat start instead of previous solution: `proj.set_study_parameter('StartType', 'Flat')`
   - Switch to Newton-Raphson instead of Fast Decoupled

5. Reset study parameters to defaults:
   ```
   python -c "
   from etap_integration.etap_com import ETAPAutomation
   with ETAPAutomation(visible=False) as etap:
       proj = etap.open_project(r'C:\Projects\MyProject.edb')
       proj.reset_study_settings('load_flow')
       print('Study settings reset to default')
   "
   ```

**Verification:**
```
python -c "
from etap_integration.etap_com import ETAPAutomation, ETAPStudyType
with ETAPAutomation(visible=False) as etap:
    proj = etap.open_project(r'C:\Projects\MyProject.edb')
    result = proj.run_study(ETAPStudyType.LOAD_FLOW)
    assert result.success, f'Study failed: {result.error}'
    print(f'Study completed: {len(result.data[\"buses\"])} buses analyzed')
"
```

---

### Issue 5.4: ETAP COM times out

**Symptoms:**
- Operations hang indefinitely
- `pywintypes.com_error: (-2147221008, 'Call was rejected by callee.')`
- Timeout errors after 30+ seconds

**Root Causes:**
- ETAP is busy with another operation (modal dialog open)
- ETAP is showing a message box waiting for user input
- ETAP crash but process still running
- COM marshaling delays with large data transfers

**Resolution Steps:**

1. Check if ETAP has a modal dialog open:
   ```
   python -c "
   import win32gui, win32process
   import psutil
   for proc in psutil.process_iter(['pid', 'name']):
       if 'etap' in proc.info['name'].lower():
           def enum_windows(hwnd, _):
               if win32gui.IsWindowVisible(hwnd):
                   _, pid = win32process.GetWindowThreadProcessId(hwnd)
                   if pid == proc.info['pid']:
                       text = win32gui.GetWindowText(hwnd)
                       if text and 'ETAP' in text:
                           print(f'ETAP window: {text}')
           win32gui.EnumWindows(enum_windows, None)
   "
   ```

2. Close any open modal dialogs programmatically:
   ```
   python -c "
   import win32com.client
   shell = win32com.client.Dispatch('Shell.Application')
   shell.Windows().Item(0).Quit()  # Close open dialogs
   "
   ```

3. Kill orphaned ETAP processes:
   ```
   taskkill /F /IM etap.exe
   ```

4. Implement shorter COM timeouts in `etap_com.py`:
   - Set `pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)`
   - Use async COM calls with timeout wrappers

**Prevention:**
- Always run ETAP with `visible=False` to suppress dialog boxes
- Implement watchdog timers in the COM interface
- Use the `ETAPAutomation` context manager which ensures cleanup

---

## 6. Calculation Engine Issues

### Issue 6.1: Load flow does not converge

**Symptoms:**
- `ERR-010: LOAD_FLOW_DIVERGENCE`
- Newton-Raphson iteration count exceeds maximum
- Voltage magnitudes oscillate or diverge
- `converged=False` returned

**Root Causes:**
- System has isolated buses (not connected to any source)
- Slack bus reference angle is unstable
- Generator reactive power limits are too restrictive
- Transformer tap settings are outside feasible range
- Load values exceed generation capacity
- High R/X ratio causing numerical instability

**Resolution Procedure:**

1. Verify system connectivity:
   ```
   python -c "
   from core_model.system import System
   sys = System.load('path/to/system.json')
   islands = sys.find_islands()
   for i, island in enumerate(islands):
       print(f'Island {i}: {len(island.buses)} buses, has_slack={island.has_slack_bus()}')
   "
   ```

2. Check for buses outside voltage limits:
   ```
   python -c "
   from load_flow.load_flow import LoadFlowEngine
   engine = LoadFlowEngine()
   engine.load_system('path/to/system.json')
   violations = engine.check_voltage_limits(0.95, 1.05)
   print(f'Voltage violations found: {len(violations)}')
   for v in violations[:5]:
       print(f'  Bus {v[\"bus\"]}: {v[\"voltage\"]:.4f} pu')
   "
   ```

3. Increase max iterations or adjust tolerance:
   ```python
   engine.parameters.max_iterations = 50
   engine.parameters.tolerance = 1e-4
   engine.parameters.acceleration_factor = 1.2
   ```

4. Switch solution method if using Fast Decoupled, try Newton-Raphson:
   ```python
   engine.parameters.method = 'NEWTON_RAPHSON'
   ```

5. Gradually apply loads (continuation power flow approach):
   ```python
   engine.parameters.load_scaling_factor = 0.5  # Start at 50% load
   engine.parameters.scaling_enabled = True
   ```

6. Check for numerical issues:
   - Ensure per-unit values are within reasonable ranges
   - Verify base MVA is consistent across all components
   - Check transformer impedances are in correct units

**Verification Steps:**
```
python -c "
from load_flow.load_flow import LoadFlowEngine
engine = LoadFlowEngine()
engine.load_system('path/to/system.json')
engine.parameters.max_iterations = 50
result = engine.solve()
assert result.converged, f'Load flow did not converge after {engine.iteration_count} iterations'
print(f'Converged in {engine.iteration_count} iterations. Max voltage: {result.max_voltage:.4f} pu')
"
```

**Log Files to Check:**
- `./logs/calculation.log` - Search for "LOAD_FLOW_DIVERGENCE"
- `./logs/python-backend.log` - Orchestrator task logs

**Prevention Measures:**
- Validate system connectivity before running load flow
- Set realistic voltage limits based on system voltage level
- Implement automatic method switching (NR -> FD -> DC)
- Use continuation power flow for ill-conditioned systems

---

### Issue 6.2: Short circuit results are incorrect

**Symptoms:**
- `ERR-012: SHORT_CIRCUIT_CALCULATION_ERROR`
- Fault currents are unrealistically high (>100 kA)
- Zero-sequence values are NaN or zero
- IEC 60909 correction factors produce unexpected results

**Root Causes:**
- Missing ground paths in transformer connections
- Incorrect generator subtransient reactance values
- Zero-sequence network not properly constructed
- Missing neutral grounding impedance data
- Voltage factor (c) selection incorrect per IEC 60909

**Resolution Steps:**

1. Verify generator data:
   ```python
   from core_model.system import System
   sys = System.load('system.json')
   for gen in sys.generators:
       if gen.xd_subtransient is None or gen.xd_subtransient == 0:
           print(f'Warning: Generator {gen.id} missing subtransient reactance')
   ```

2. Check transformer grounding configuration:
   ```python
   for tx in sys.transformers:
       if tx.winding1_connection == 'Y' and not tx.winding1_grounded:
           print(f'Warning: Transformer {tx.id} ungrounded wye on primary')
       if tx.winding2_connection == 'Y' and not tx.winding2_grounded:
           print(f'Warning: Transformer {tx.id} ungrounded wye on secondary')
   ```

3. Validate zero-sequence network:
   ```python
   from fault_analysis.fault import FaultAnalyzer
   analyzer = FaultAnalyzer(sys)
   z_network = analyzer.build_zero_sequence_network()
   if z_network.is_singular():
       print('Zero-sequence network is singular - check grounding')
   ```

4. Verify IEC 60909 voltage factor (c):
   ```
   | Voltage Level | c_max (for max fault) | c_min (for min fault) |
   |---------------|----------------------|----------------------|
   | LV (<=1kV)    | 1.10                 | 0.95                 |
   | MV (1-35kV)   | 1.10                 | 1.00                 |
   | HV (>35kV)    | 1.10                 | 1.00                 |
   ```

5. Test with a simple 3-bus system to verify the algorithm:
   ```python
   from fault_analysis.test_fault_debug import test_simple_fault
   test_simple_fault()
   ```

**Verification:**
```
python -c "
from fault_analysis.fault import FaultAnalyzer
from core_model.system import System
sys = System.load('system.json')
analyzer = FaultAnalyzer(sys)
results = analyzer.calculate_all_faults()
for bus, faults in results.items():
    for ftype, data in faults.items():
        current = abs(data['fault_current'])
        assert 0.1 < current < 100, f'Implausible fault current: {current} kA'
print('Short circuit results validated')
"
```

---

### Issue 6.3: Harmonic analysis yields invalid THD

**Symptoms:**
- `ERR-014: HARMONIC_ANALYSIS_ERROR`
- THD values exceed 100%
- Resonant frequencies detected at fundamental
- Harmonic impedance matrix is singular

**Root Causes:**
- Missing harmonic source data (current injection values)
- Incorrect frequency-dependent impedance models
- Resonance near fundamental frequency (system design issue)
- Insufficient harmonic orders analyzed

**Resolution Steps:**

1. Verify harmonic source data:
   ```python
   from fault_analysis.harmonic_analysis import HarmonicAnalyzer
   analyzer = HarmonicAnalyzer(sys)
   sources = analyzer.get_harmonic_sources()
   for bus, source in sources.items():
       print(f'Bus {bus}: {len(source.spectrum)} harmonics')
       if max(source.spectrum.keys()) < 50:
           print(f'  Warning: Only analyzing up to {max(source.spectrum.keys())}th harmonic')
   ```

2. Check for resonance near 50/60 Hz:
   ```python
   impedance_scan = analyzer.scan_impedance(1, 5000)  # 1 Hz to 5 kHz
   resonances = impedance_scan.find_resonances()
   for r in resonances:
       if abs(r.frequency - 50) < 5 or abs(r.frequency - 60) < 5:
           print(f'CRITICAL: Resonance near fundamental at {r.frequency} Hz')
   ```

3. Increase harmonic order range:
   ```python
   analyzer.parameters.max_harmonic_order = 50  # Up to 50th harmonic
   ```

4. Verify frequency-dependent parameters:
   - Transformer leakage reactance: X(f) = X_rated * f/f_rated
   - Line resistance: R(f) = R_dc * (1 + k * sqrt(f))
   - Capacitor impedance: X_c(f) = X_c_rated / (f/f_rated)

**Verification:**
```
python -c "
from fault_analysis.harmonic_analysis import HarmonicAnalyzer
analyzer = HarmonicAnalyzer(sys)
results = analyzer.analyze()
thd_v = results['max_thd_voltage']
thd_i = results['max_thd_current']
assert thd_v < 100, f'THD > 100%: {thd_v}%'
print(f'Max THDv: {thd_v:.2f}%, Max THDi: {thd_i:.2f}%')
"
```

---

### Issue 6.4: OPF solver fails

**Symptoms:**
- `ERR-016: OPF_SOLVER_FAILED`
- `SLSQP` or `LP` solver returns non-optimal status
- Generator dispatch results violate constraints
- Dual variables/infinity in sensitivity analysis

**Root Causes:**
- Problem is infeasible (load exceeds generation capacity)
- Line flow limits are too restrictive
- Generator cost curves are non-convex
- Voltage constraints conflict with reactive power limits
- DC-OPF approximation invalid for system (high R/X)

**Resolution Steps:**

1. Check problem feasibility:
   ```
   python -c "
   from load_flow.optimal_power_flow import OPFEngine
   opf = OPFEngine(sys)
   feasibility = opf.check_feasibility()
   print(f'Feasible: {feasibility.is_feasible}')
   if not feasibility.is_feasible:
       for constraint in feasibility.violated_constraints:
           print(f'  Constraint violated: {constraint}')
   "
   ```

2. Compare total generation capacity vs total load:
   ```python
   total_load = sum(bus.load.p for bus in sys.buses)
   total_gen = sum(gen.p_max for gen in sys.generators)
   print(f'Total load: {total_load} MW, Total gen capacity: {total_gen} MW')
   if total_load > total_gen:
       print('ERROR: Load exceeds generation capacity')
   ```

3. Relax constraint limits progressively:
   ```python
   opf.parameters.line_flow_limit_multiplier = 1.2  # 20% headroom
   opf.parameters.voltage_limit_tolerance = 0.02     # +/- 0.02 pu tolerance
   ```

4. Try AC-OPF with different initial guess:
   ```python
   opf.parameters.initialization = 'flat_start'
   opf.parameters.method = 'SLSQP'
   opf.parameters.max_iterations = 1000
   ```

5. For non-convex cost curves, convert to piecewise linear approximation:
   ```python
   for gen in sys.generators:
       if gen.cost_curve_type == 'quadratic':
           gen.linearize_cost_curve(n_segments=10)
   ```

**Verification:**
```
python -c "
from load_flow.optimal_power_flow import OPFEngine
opf = OPFEngine(sys)
result = opf.solve()
assert result.status == 'optimal', f'OPF failed: {result.status}'
print(f'Optimal cost: ${result.total_cost:.2f}/hr')
print(f'Total losses: {result.total_losses:.2f} MW')
"
```

---

## 7. Security/Authentication Issues

### Issue 7.1: Authentication fails (JWT)

**Symptoms:**
- `ERR-020: AUTHENTICATION_FAILED`
- HTTP 401 Unauthorized responses
- `Invalid token` or `Token expired` errors
- Cannot access any API endpoints

**Root Causes:**
- JWT secret key changed (invalidation of all tokens)
- Token expired beyond its TTL
- Clock skew between client and server
- Token tampered with (signature mismatch)
- Missing `Bearer` prefix in Authorization header

**Resolution Steps:**

1. Verify JWT_SECRET_KEY is set:
   ```
   python -c "
   import os; assert os.getenv('JWT_SECRET_KEY'), 'JWT_SECRET_KEY not set'
   print(f'JWT_SECRET_KEY configured: {os.getenv(\"JWT_SECRET_KEY\")[:8]}...')
   "
   ```

2. Test token generation and validation:
   ```
   python -c "
   from security.security_framework import AuthManager
   auth = AuthManager()
   token = auth.generate_token(user_id='test', role='engineer')
   print(f'Token generated: {token[:50]}...')
   payload = auth.validate_token(token)
   assert payload is not None, 'Token validation failed'
   print(f'Token valid for user: {payload[\"user_id\"]}')
   "
   ```

3. Check clock skew:
   ```
   python -c "
   import time, datetime
   print(f'Server time: {datetime.datetime.utcnow()}')
   # Compare with NTP time if possible
   "
   ```

4. If secret key was rotated, invalidate all existing tokens by incrementing the token version.

5. Verify the Authorization header format:
   ```
   curl -H "Authorization: Bearer <token>" http://localhost:3000/api/v1/analyze
   ```

**Verification:**
```
curl -H "Authorization: Bearer $(python -c 'from security.security_framework import AuthManager; print(AuthManager().generate_token(\"test\", \"admin\"))')" http://localhost:3000/health
# Expected: 200 OK
```

---

### Issue 7.2: RBAC permission denied

**Symptoms:**
- HTTP 403 Forbidden
- `Insufficient permissions` error
- User role cannot access resources they need

**Root Causes:**
- User assigned incorrect role
- Permission not granted for the specific action
- Resource ownership mismatch
- Role hierarchy not properly configured

**Resolution Steps:**

1. Check user's current role and permissions:
   ```
   python -c "
   from security.security_framework import AuthManager
   auth = AuthManager()
   user = auth.get_user('username')
   print(f'User role: {user.role}')
   print(f'Permissions: {user.list_permissions()}')
   "
   ```

2. List all available permissions:
   ```
   python -c "
   from security.security_framework import RBACManager
   rbac = RBACManager()
   for role, perms in rbac.get_all_permissions().items():
       print(f'{role}: {len(perms)} permissions')
   "
   ```

3. Upgrade user role if appropriate:
   ```
   python -c "
   from security.security_framework import AuthManager
   auth = AuthManager()
   auth.update_user_role('username', 'admin')
   print('User upgraded to admin')
   "
   ```

4. Check if resource ownership is enforced and the user owns the resource.

**Verification:**
```
python -c "
from security.security_framework import AuthManager, check_permission
result = check_permission('username', 'run:etap_study')
print(f'Permission granted: {result}')
"
```

---

## 8. Performance Issues

### Issue 8.1: Slow load flow calculations

**Symptoms:**
- Load flow takes >30 seconds for systems under 100 buses
- CPU utilization is low during calculations (not CPU-bound)
- Memory usage grows unexpectedly

**Root Causes:**
- Jacobian matrix construction is inefficient
- Using Newton-Raphson when Fast Decoupled would suffice
- Large impedance values causing near-singular matrix
- Python overhead in hot loops

**Resolution Steps:**

1. Switch solver method for better performance:
   ```python
   engine.parameters.method = 'FAST_DECOUPLED'  # 2-5x faster for transmission systems
   ```

2. Enable sparse matrix solvers:
   ```python
   from scipy.sparse.linalg import spsolve
   engine.use_sparse = True
   ```

3. If memory is the issue, reduce system size or enable out-of-core computation:
   ```python
   engine.parameters.memory_limit_mb = 1024
   engine.parameters.use_incremental_solving = True
   ```

4. Profile the calculation to find bottlenecks:
   ```
   python -m cProfile -o profile.out load_flow/load_flow.py
   python -c "
   import pstats
   p = pstats.Stats('profile.out')
   p.sort_stats('cumtime').print_stats(20)
   "
   ```

5. Cache the Jacobian matrix if topology hasn't changed:
   ```python
   engine.cache_jacobian = True  # Reuse Jacobian for similar operating points
   ```

**Benchmark Comparison:**
```
| Method | 14 Bus | 100 Bus | 500 Bus |
|--------|--------|---------|---------|
| Newton-Raphson (dense) | 0.8s | 4.5s | 28s |
| Fast Decoupled | 0.3s | 1.2s | 8s |
| NR + Sparse | 0.2s | 0.8s | 5s |
```

---

### Issue 8.2: High memory usage

**Symptoms:**
- Memory usage exceeds 4GB
- OOM (Out of Memory) killer terminates processes
- Swap usage is high

**Root Causes:**
- Large system model with many buses/lines
- Fault analysis storing all Z-bus matrices
- RAG engine loading large embedding models
- Report generation with high-resolution images

**Resolution Steps:**

1. Monitor memory usage per component:
   ```
   python -c "
   import psutil
   proc = psutil.Process()
   print(f'Memory: {proc.memory_info().rss / 1024**3:.2f} GB')
   for child in proc.children():
       print(f'  Child: {child.memory_info().rss / 1024**3:.2f} GB')
   "
   ```

2. Reduce embedding model size in RAG:
   ```
   # In .env
   EMBEDDING_MODEL=all-MiniLM-L6-v2  # Smaller model (80MB vs 400MB)
   ```

3. Limit concurrent studies:
   ```
   # In .env
   MAX_CONCURRENT_STUDIES=2
   ```

4. Clear caches periodically:
   ```
   python -c "
   from knowledge.rag_engine import RAGEngine
   engine = RAGEngine()
   engine.clear_cache()
   print('RAG cache cleared')
   "
   ```

5. Enable memory limits in Docker:
   ```yaml
   # In docker-compose.yml
   services:
     etap-platform:
       mem_limit: 4g
       mem_reservation: 2g
   ```

---

## 9. Deployment Issues

### Issue 9.1: Kubernetes pod crashes on startup

**Symptoms:**
- `CrashLoopBackOff` status
- Pod exits with non-zero code immediately
- Liveness probe fails

**Root Causes:**
- Secrets not mounted or missing keys
- PersistentVolumeClaims not bound
- Resource limits too restrictive
- Missing ConfigMap entries

**Resolution Steps:**

1. Check pod logs:
   ```
   kubectl logs -l app=etap-platform --tail=100
   ```

2. Verify secrets are mounted:
   ```
   kubectl exec -it <pod-name> -- env | grep -E 'OPENAI|JWT|DATABASE'
   ```

3. Check PVC status:
   ```
   kubectl get pvc
   kubectl describe pvc reports-pvc
   ```

4. Verify resource requests are not exceeding node capacity:
   ```
   kubectl describe nodes | grep -A 5 Capacity
   ```

5. Test locally with the same configuration:
   ```
   docker run --rm -it etap-platform:latest python -c "from main import app; print('App loaded')"
   ```

**Verification:**
```
kubectl rollout status deployment/etap-platform
kubectl get pods -l app=etap-platform
# Expected: 3/3 Running
```

---

### Issue 9.2: Docker build fails

**Symptoms:**
- `docker build` exits with error
- Layer caching issues
- Network timeout during apt-get or pip install

**Resolution Steps:**

1. Retry with no cache:
   ```
   docker build --no-cache -t etap-platform:latest .
   ```

2. Use a different base image if dependencies conflict:
   ```dockerfile
   FROM python:3.11-slim-bookworm
   ```

3. Add retry logic to apt-get:
   ```dockerfile
   RUN apt-get update && apt-get install -y --no-install-recommends \
       nodejs npm gcc g++ || \
       (sleep 5 && apt-get update && apt-get install -y --no-install-recommends \
           nodejs npm gcc g++)
   ```

4. Use pip mirrors for faster installs:
   ```
   pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
   ```

**Verification:**
```
docker images | findstr etap-platform
# Expected: etap-platform   latest   <hash>   10 minutes ago
```

---

## 10. Docker/Container Issues

### Issue 10.1: Container exits immediately

**Symptoms:**
- Container runs for < 1 second then stops
- No output in docker logs
- Exit code 1 or 137

**Root Causes:**
- Entrypoint script fails
- Missing environment variables
- Port binding conflicts
- OOM kill (exit code 137)

**Resolution Steps:**

1. Run interactively to see error:
   ```
   docker run --rm -it --entrypoint /bin/bash etap-platform:latest
   # Then manually start the service
   python main.py
   ```

2. Check exit code meaning:
   - Exit 0: Normal termination
   - Exit 1: Application error (check logs)
   - Exit 137: OOM killed (increase memory)
   - Exit 139: Segmentation fault

3. Verify port mapping:
   ```
   docker run --rm -p 3000:3000 -p 8000:8000 --env-file .env etap-platform:latest
   ```

**Verification:**
```
docker ps --filter "status=running" --filter "name=etap-platform"
```

---

### Issue 10.2: Volume mount permission issues

**Symptoms:**
- Permission denied errors in logs
- Reports directory not writable
- Database file cannot be created

**Root Causes:**
- Host directory doesn't exist
- UID/GID mismatch between container and host
- SELinux/AppArmor blocking mounts

**Resolution Steps:**

1. Create directories on host before mounting:
   ```
   mkdir -p ./reports ./knowledge_db ./logs
   ```

2. For Windows, ensure shared drives are configured in Docker Desktop.

3. Test volume mount explicitly:
   ```
   docker run --rm -v C:\Users\EWS-01\Desktop\my-awesome-agent\reports:/app/reports etap-platform:latest ls -la /app/reports
   ```

4. If using Docker Desktop, reset credentials or shared drives in Docker Desktop settings.

**Verification:**
```
docker exec -it <container_id> touch /app/reports/test.txt
echo "Write test successful"
```

---

## 11. Error Code Reference

### ERR-001 to ERR-010: ETAP Integration Errors

| Code | Message Template | Component | Severity | Description | Recommended Action | Log File |
|------|-----------------|-----------|----------|-------------|-------------------|----------|
| ERR-001 | `ETAP_COM_CONNECTION_FAILED: {reason}` | ETAP COM | Fatal | ETAP COM interface failed to initialize | Verify ETAP installation, register COM components, check antivirus | etap-com.log |
| ERR-002 | `ETAP_PROJECT_OPEN_FAILED: {path} - {reason}` | ETAP COM | Error | Unable to open ETAP project file | Verify file exists, check version compatibility, restore from backup | etap-com.log |
| ERR-003 | `ETAP_STUDY_EXECUTION_FAILED: {study_type} - {reason}` | ETAP COM | Error | ETAP study did not complete successfully | Check study parameters, validate input data, review ETAP calculation log | etap-com.log |
| ERR-004 | `ETAP_LICENSE_ERROR: {detail}` | ETAP COM | Fatal | ETAP license check failed | Verify license server, check concurrent usage count, contact ETAP support | etap-com.log |
| ERR-005 | `ETAP_VERSION_MISMATCH: expected {expected}, found {actual}` | ETAP COM | Error | ETAP version does not match expected | Install supported ETAP version or update compatibility layer | etap-com.log |
| ERR-006 | `ETAP_RESULT_EXTRACTION_FAILED: {study_type} - {field}` | ETAP COM | Error | Failed to extract results from completed study | Check result format, verify study completed with data | etap-com.log |
| ERR-007 | `ETAP_PROJECT_SAVE_FAILED: {path} - {reason}` | ETAP COM | Warning | Unable to save project changes | Check disk space, file permissions | etap-com.log |
| ERR-008 | `ETAP_COM_TIMEOUT: {operation} exceeded {timeout}s` | ETAP COM | Error | ETAP COM operation timed out | Check ETAP for modal dialogs, kill orphaned processes, increase timeout | etap-com.log |

### ERR-009 to ERR-019: Calculation Engine Errors

| Code | Message Template | Component | Severity | Description | Recommended Action | Log File |
|------|-----------------|-----------|----------|-------------|-------------------|----------|
| ERR-009 | `SYSTEM_MODEL_INVALID: {detail}` | Core Model | Fatal | Power system model fails validation | Validate JSON structure, check required fields, verify bus connectivity | calculation.log |
| ERR-010 | `LOAD_FLOW_DIVERGENCE: {detail}` | Load Flow | Error | Load flow solver did not converge | Check system connectivity, increase iterations, verify slack bus, switch solver method | calculation.log |
| ERR-011 | `LOAD_FLOW_SINGULAR_JACOBIAN` | Load Flow | Error | Jacobian matrix is singular | Check for isolated buses, verify slack bus assignment, review impedance values | calculation.log |
| ERR-012 | `SHORT_CIRCUIT_CALCULATION_ERROR: {detail}` | Fault Analysis | Error | Short circuit calculation failed | Check zero-sequence network, verify generator reactances, validate grounding | calculation.log |
| ERR-013 | `IEC60909_C_FACTOR_ERROR: {voltage}` | Fault Analysis | Warning | IEC 60909 voltage factor c is outside standard range | Review c factor selection per IEC 60909 Table 1 | calculation.log |
| ERR-014 | `HARMONIC_ANALYSIS_ERROR: {detail}` | Harmonic Analysis | Error | Harmonic analysis calculation failed | Check harmonic source data, verify impedance scanning, increase frequency range | calculation.log |
| ERR-015 | `IEEE519_COMPLIANCE_FAILED: {detail}` | Harmonic Analysis | Warning | IEEE 519 compliance check failed | Review THD/TDD values, identify dominant harmonics, design filters | calculation.log |
| ERR-016 | `OPF_SOLVER_FAILED: {detail}` | OPF | Error | Optimal power flow solver did not reach optimal solution | Check problem feasibility, relax constraints, verify cost curves are convex | calculation.log |
| ERR-017 | `PROTECTION_COORDINATION_ERROR: {detail}` | Protection | Error | Protection coordination calculation failed | Verify relay settings, check TCC curve data, validate time grading margins | calculation.log |
| ERR-018 | `ARC_FLASH_CALCULATION_ERROR: {detail}` | Fault Analysis | Error | Arc flash calculation failed per IEEE 1584 | Verify equipment parameters, check bolted fault currents, validate gap distances | calculation.log |
| ERR-019 | `PER_UNIT_CONVERSION_ERROR: {detail}` | Network Solver | Error | Per-unit conversion produced invalid values | Check base values (MVA, kV), verify impedance units (ohm vs pu) | calculation.log |

### ERR-020 to ERR-029: Security Errors

| Code | Message Template | Component | Severity | Description | Recommended Action | Log File |
|------|-----------------|-----------|----------|-------------|-------------------|----------|
| ERR-020 | `AUTHENTICATION_FAILED: {reason}` | Security | Error | User authentication failed | Verify credentials, check JWT token validity, ensure JWT_SECRET_KEY is configured | security.log |
| ERR-021 | `TOKEN_EXPIRED` | Security | Warning | JWT token has expired | Re-authenticate or refresh token | security.log |
| ERR-022 | `TOKEN_INVALID: {reason}` | Security | Error | JWT token validation failed | Check token signature, verify issuer, ensure token not tampered | security.log |
| ERR-023 | `AUTHORIZATION_FAILED: {user} - {required_permission}` | Security | Error | User lacks required permissions | Review RBAC role assignment, upgrade user permissions if appropriate | security.log |
| ERR-024 | `INVALID_CREDENTIALS: {user}` | Security | Error | Invalid username or password | Reset password, verify user account exists | security.log |
| ERR-025 | `ACCOUNT_LOCKED: {user} - {reason}` | Security | Warning | User account is locked | Unlock account via admin console, wait for lockout period | security.log |
| ERR-026 | `INPUT_VALIDATION_FAILED: {field} - {reason}` | Security | Error | Input validation rejected the provided data | Review input format, sanitize special characters, ensure types match schema | security.log |
| ERR-027 | `SQL_INJECTION_DETECTED: {input_preview}` | Security | Fatal | SQL injection attempt was blocked | Review input, ensure parameterized queries are used | security.log |
| ERR-028 | `CSRF_TOKEN_MISMATCH` | Security | Error | CSRF token validation failed | Refresh page, verify CSRF token in form submissions | security.log |
| ERR-029 | `RATE_LIMIT_EXCEEDED: {client_ip} - {endpoint}` | Security | Warning | API rate limit was exceeded for this client | Reduce request frequency, implement backoff strategy | security.log |

### ERR-030 to ERR-040: Data and Storage Errors

| Code | Message Template | Component | Severity | Description | Recommended Action | Log File |
|------|-----------------|-----------|----------|-------------|-------------------|----------|
| ERR-030 | `INPUT_VALIDATION_FAILED: {field} - {reason}` | Core | Error | User input failed validation | Review input requirements, sanitize data, check allowed values | python-backend.log |
| ERR-031 | `DATABASE_CONNECTION_FAILED: {url}` | Database | Fatal | Unable to connect to the database | Check database URL, verify database server is running, check credentials | python-backend.log |
| ERR-032 | `DATABASE_MIGRATION_FAILED: {version} - {reason}` | Database | Fatal | Database migration could not be applied | Verify migration file integrity, check database state, restore from backup | python-backend.log |
| ERR-033 | `DATABASE_CORRUPTION: {detail}` | Database | Fatal | Database integrity check failed | Restore from most recent backup, run recovery tools | python-backend.log |
| ERR-034 | `CACHE_CORRUPTION: {cache_name}` | Core | Warning | Cache data is corrupted or invalid | Clear cache and allow it to repopulate | python-backend.log |
| ERR-035 | `FILE_NOT_FOUND: {path}` | Core | Error | Required file does not exist | Verify file path, check file system, restore from backup | python-backend.log |
| ERR-036 | `DISK_FULL: {path} - {free_space}` | Core | Fatal | Disk space exhausted on the storage volume | Free up disk space, increase volume size, enable log rotation | python-backend.log |
| ERR-037 | `SERIALIZATION_ERROR: {type} - {reason}` | Core | Error | Failed to serialize/deserialize data | Check data format compatibility, verify schema version | python-backend.log |
| ERR-038 | `IMPORT_ERROR: {module} - {reason}` | Core | Fatal | Required Python module failed to import | Install missing dependency, check Python version compatibility | python-backend.log |

### ERR-041 to ERR-050: System and Infrastructure Errors

| Code | Message Template | Component | Severity | Description | Recommended Action | Log File |
|------|-----------------|-----------|----------|-------------|-------------------|----------|
| ERR-041 | `RAG_ENGINE_FAILURE: {detail}` | RAG | Error | RAG knowledge engine failed to respond | Check vector database connectivity, verify embedding model loaded | rag-engine.log |
| ERR-042 | `RAG_EMBEDDING_FAILED: {text_preview}` | RAG | Error | Text embedding generation failed | Check embedding model, reduce input text size, verify API key | rag-engine.log |
| ERR-043 | `VECTOR_DB_CONNECTION_FAILED: {detail}` | RAG | Error | Vector database connection failed | Check ChromaDB/FAISS status, verify database path exists | rag-engine.log |
| ERR-044 | `LLM_API_ERROR: {provider} - {status_code}` | LLM | Error | LLM API call failed | Check API key validity, verify API endpoint, handle rate limiting | python-backend.log |
| ERR-045 | `LLM_RESPONSE_PARSE_ERROR: {raw_response}` | LLM | Warning | LLM response could not be parsed | Retry request with clearer prompt, check for malformed JSON in response | python-backend.log |
| ERR-046 | `ORCHESTRATOR_TASK_FAILED: {task_id} - {agent} - {reason}` | Orchestrator | Error | An agent task within the orchestrator failed | Check individual agent logs, review task parameters | python-backend.log |
| ERR-047 | `WORKFLOW_TIMEOUT: {workflow_id} - {duration}` | Orchestrator | Warning | Complete workflow exceeded maximum execution time | Review workflow complexity, increase timeout, optimize individual steps | python-backend.log |
| ERR-048 | `REPORT_GENERATION_FAILED: {format} - {reason}` | Reporting | Error | Report generation failed | Check template files, verify disk space, review input data | python-backend.log |
| ERR-049 | `REPORT_TEMPLATE_NOT_FOUND: {template_name}` | Reporting | Error | Report template is missing | Reinstall templates from repository, check template directory | python-backend.log |
| ERR-050 | `RATE_LIMIT_EXCEEDED: {client_id} - {endpoint}` | API | Warning | Client has exceeded the allowed request rate | Implement exponential backoff, increase rate limit for trusted clients | python-backend.log |

---

## 12. Diagnostic Procedures

### Procedure 12.1: Full System Health Check

Run this comprehensive diagnostic to assess the health of all platform components:

```
python -c "
import sys, os
from pathlib import Path

print('=== ETAP AI Platform Health Check ===')
print()

# 1. Environment
print('[1/7] Environment Check')
print(f'  Python: {sys.version}')
print(f'  CWD: {os.getcwd()}')
print(f'  .env exists: {os.path.exists(\".env\")}')
print(f'  OPENAI_API_KEY set: {os.getenv(\"OPENAI_API_KEY\") is not None}')
print(f'  JWT_SECRET_KEY set: {os.getenv(\"JWT_SECRET_KEY\") is not None}')
print()

# 2. Dependencies
print('[2/7] Dependency Check')
modules = ['numpy', 'scipy', 'pandas', 'reportlab', 'chromadb', 'torch', 'transformers']
for mod in modules:
    try:
        __import__(mod)
        print(f'  {mod}: OK')
    except ImportError as e:
        print(f'  {mod}: MISSING - {e}')
print()

# 3. Log Files
print('[3/7] Log File Check')
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)
print(f'  Log directory: {log_dir.absolute()}')
print(f'  Writable: {os.access(str(log_dir), os.W_OK)}')
print()

# 4. Core Modules
print('[4/7] Core Module Check')
try:
    from core_model.system import System
    print('  Core Model: OK')
except Exception as e:
    print(f'  Core Model: FAIL - {e}')

try:
    from load_flow.load_flow import LoadFlowEngine
    print('  Load Flow: OK')
except Exception as e:
    print(f'  Load Flow: FAIL - {e}')

try:
    from fault_analysis.fault import FaultAnalyzer
    print('  Fault Analysis: OK')
except Exception as e:
    print(f'  Fault Analysis: FAIL - {e}')

try:
    from security.security_framework import AuthManager
    print('  Security: OK')
except Exception as e:
    print(f'  Security: FAIL - {e}')

try:
    from knowledge.rag_engine import RAGEngine
    print('  RAG Engine: OK')
except Exception as e:
    print(f'  RAG Engine: FAIL - {e}')

try:
    from reporting.advanced_reports import ReportAgent
    print('  Reporting: OK')
except Exception as e:
    print(f'  Reporting: FAIL - {e}')
print()

# 5. ETAP COM
print('[5/7] ETAP COM Check')
try:
    from etap_integration.etap_com import ETAPAutomation
    print('  ETAP COM module: OK')
    try:
        with ETAPAutomation(visible=False) as etap:
            ver = etap.get_version()
            print(f'  ETAP connection: OK (version: {ver})')
    except Exception as e:
        print(f'  ETAP connection: FAIL - {e}')
except Exception as e:
    print(f'  ETAP COM module: FAIL - {e}')
print()

# 6. Database
print('[6/7] Database Check')
db_paths = ['mastra.db', 'mastra.duckdb']
for db in db_paths:
    if os.path.exists(db):
        size = os.path.getsize(db)
        print(f'  {db}: OK ({size/1024:.1f} KB)')
    else:
        print(f'  {db}: NOT FOUND')
print()

# 7. API Endpoint
print('[7/7] API Health Check')
import urllib.request
try:
    response = urllib.request.urlopen('http://localhost:3000/health', timeout=5)
    print(f'  API health: OK ({response.status})')
except Exception as e:
    print(f'  API health: FAIL - {e}')

print()
print('=== Health Check Complete ===')
"
```

### Procedure 12.2: Log Collection Bundle

When reporting an issue, use this procedure to collect all relevant information:

```
# Create diagnostic bundle
mkdir -p ./diag-$(date +%Y%m%d-%H%M%S)
cd ./diag-$(date +%Y%m%d-%H%M%S)

# Collect logs
copy ..\logs\*.log .
docker logs etap-platform > docker-etap-platform.log 2>&1 2>NUL

# Collect configuration (redacted)
python -c "
import os
with open('../.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key = line.split('=')[0]
            print(f'{key}=***REDACTED***')
" > env-redacted.txt

# Collect system info
systeminfo > system-info.txt
python --version > python-version.txt
node --version > node-version.txt 2>NUL
pip list > pip-list.txt
pnpm list --depth=0 > pnpm-list.txt 2>NUL

# Collect running processes (ETAP related)
tasklist | findstr /I etap > etap-processes.txt
netstat -ano | findstr ":3000 :8000" > port-usage.txt

echo Diagnostic bundle created in %cd%
```

### Procedure 12.3: Component Isolation Test

To determine if an issue is caused by a specific component:

1. **Isolate Python engines** - Test without ETAP:
   ```
   python -c "
   from load_flow.load_flow import LoadFlowEngine
   engine = LoadFlowEngine()
   # Test with built-in test system
   result = engine.run_test_case('ieee_14_bus')
   print(f'Load Flow standalone: converged={result.converged}')
   "
   ```

2. **Isolate ETAP COM** - Test without agents:
   ```
   python -c "
   from etap_integration.etap_com import ETAPAutomation
   with ETAPAutomation(visible=False) as etap:
       print(f'ETAP standalone: {etap.get_version()}')
   "
   ```

3. **Isolate RAG** - Test without LLM:
   ```
   python -c "
   from knowledge.rag_engine import RAGEngine
   rag = RAGEngine()
   result = rag.query('What are the voltage limits per IEEE standards?', use_llm=False)
   print(f'RAG standalone: {len(result[\"sources\"])} sources found')
   "
   ```

4. **Isolate Security** - Test without database:
   ```
   python -c "
   from security.security_framework import AuthManager
   auth = AuthManager(use_database=False)
   token = auth.generate_token('test', 'admin')
   payload = auth.validate_token(token)
   print(f'Security standalone: valid={payload is not None}')
   "
   ```

---

## 13. Support Escalation Process

### Tier 1: Self-Service (First Response)

**Response Time:** < 30 minutes
**Scope:**
- Verify `.env` configuration
- Check log files for error codes
- Restart services
- Verify network connectivity
- Check disk space and resource usage

**Actions:**
1. Reference this Troubleshooting Guide for the specific error code
2. Run the Health Check diagnostic (Section 12.1)
3. Collect log bundle (Section 12.2)
4. Attempt restart: `docker-compose restart etap-platform`

### Tier 2: Engineering Team

**Response Time:** < 4 hours (business hours)
**Scope:**
- Code-level debugging
- ETAP COM issues
- Calculation engine algorithm issues
- Database corruption recovery
- Complex configuration problems
- Performance optimization

**Escalation Trigger:**
- Error code not documented in this guide
- Tier 1 procedures did not resolve the issue
- Data loss or corruption
- Security vulnerability suspected
- ETAP version incompatibility

**Contact:**
- Email: engineering@yourcompany.com
- Slack: #etap-platform-engineering
- Jira: https://yourcompany.atlassian.net/projects/ETAP

### Tier 3: ETAP Support (ETAP-Specific Issues)

**Response Time:** < 8 hours (business hours)
**Scope:**
- ETAP software bugs
- ETAP licensing issues
- COM API limitations
- ETAP calculation engine discrepancies

**Escalation Trigger:**
- Confirmed ETAP software bug
- ETAP license server issues
- COM API unexpected behavior
- Results mismatch with ETAP manual calculations

**Contact:**
- ETAP Support Portal: https://support.etap.com
- ETAP Support Phone: +1-949-900-1000
- Reference: Provide ETAP version, log bundle, and error code

### Tier 4: Vendor/Emergency

**Response Time:** < 1 hour (24/7)
**Scope:**
- Production system down
- Security breach in progress
- Complete data loss

**Escalation Trigger:**
- P1 incident declared (complete service outage)
- Security breach confirmed
- Customer data compromised

**Contact:**
- Emergency Phone: +1-XXX-XXX-XXXX
- On-Call Engineer: Available via PagerDuty
- Email: emergency@yourcompany.com

### Escalation Flow Diagram

```
User Reports Issue
    |
    v
[Tier 1] Self-Service (30 min)
    |--- Run diagnostic procedures
    |--- Consult error code reference
    |--- Attempt standard resolution
    |
    ├── Resolved? → Close ticket
    |
    └── Not resolved?
            |
            v
    [Tier 2] Engineering Team (4 hrs)
        |--- Review logs and diagnostics
        |--- Code-level debugging
        |--- ETAP COM investigation
        |
        ├── Resolved? → Document solution
        |
        └── Not resolved?
                |
                v
        [Tier 3] ETAP Support (8 hrs)
            |--- ETAP-specific debugging
            |--- Licensing verification
            |
            ├── Resolved? → Update knowledge base
            |
            └── Not resolved?
                    |
                    v
            [Tier 4] Vendor/Emergency (1 hr)
                |--- Crisis management
                |--- Root cause analysis
                └── Post-mortem review
```

### SLA Summary

| Tier | Response Time | Resolution Time | Availability |
|------|--------------|-----------------|--------------|
| T1 - Self-Service | 30 min | 2 hrs | Business hours |
| T2 - Engineering | 4 hrs | 8 hrs | Business hours |
| T3 - ETAP Support | 8 hrs | 24 hrs | Business hours |
| T4 - Emergency | 1 hr | 4 hrs | 24/7 |

---

## Appendix: Quick Reference Card

### Most Common Fixes

| Symptom | Most Likely Cause | Quick Fix |
|---------|------------------|-----------|
| Service won't start | Missing JWT_SECRET_KEY | Add to .env |
| ETAP connection fails | ETAP not installed | Install ETAP or register COM |
| Load flow diverges | Isolated buses | Check system connectivity |
| Auth fails (401) | Token expired | Re-authenticate |
| Slow calculations | Large system, dense solver | Enable sparse matrices |
| Memory high | Large embedding model | Switch to all-MiniLM-L6-v2 |
| Reports fail | Disk full | Clean reports directory |
| Docker crash | OOM limit | Increase memory limit |
| Database corruption | Unexpected shutdown | Restore from backup |

### Key Commands Reference

```
# Health check
curl http://localhost:3000/health

# View logs
tail -f logs/python-backend.log

# Restart platform
docker-compose restart

# Force rebuild
docker-compose up -d --build

# Backup database
copy mastra.db backups/mastra_$(date +%Y%m%d).db

# Test ETAP connection
python -c "from etap_integration.etap_com import ETAPAutomation; ETAPAutomation()"

# Run tests
pytest tests/ -v

# Clear cache
python -c "from knowledge.rag_engine import RAGEngine; RAGEngine().clear_cache()"
```

---

**Document Version:** 1.0  
**Last Updated:** June 8, 2026  
**Maintained By:** Engineering Team  
**Classification:** Internal - Operations  
**Review Frequency:** Quarterly
