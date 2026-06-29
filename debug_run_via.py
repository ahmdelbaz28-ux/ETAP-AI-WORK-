import os, sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_arc_flash_single_engine import _run_via_run_python, STUDY_PARAMS

result = _run_via_run_python(STUDY_PARAMS)
print('Result keys:', list(result.keys()))
print('Result snippet:', {k: result[k] for k in list(result)[:5]})
