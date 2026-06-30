import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SECURE_EXECUTOR = PROJECT_ROOT / 'security' / 'secure_executor.py'

params = {
    "voltage_kv": 4.16,
    "bolted_fault_current_ka": 20.0,
    "arc_duration_sec": 0.183,
    "working_distance_mm": 610.0,
    "electrode_config": "VCB",
    "enclosure_type": "box",
}
code = (
    "import json\n"
    "from engine.engine import PowerSystemEngine\n"
    "engine = PowerSystemEngine()\n"
    f"result = engine.run_study(study_type='arc_flash', **{json.dumps(params)})\n"
    "print(json.dumps(result))\n"
)
proc = subprocess.run([sys.executable, str(SECURE_EXECUTOR)], input=code, capture_output=True, text=True, timeout=30, cwd=str(PROJECT_ROOT), env={**os.environ, 'PYTHONPATH': str(PROJECT_ROOT)})
print('returncode', proc.returncode)
print('stdout', proc.stdout[:500])
print('stderr', proc.stderr[:500])
