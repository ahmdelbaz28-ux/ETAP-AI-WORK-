import json
import re
from pathlib import Path


def main() -> None:
    file_path = Path("api/scada.py")
    original = file_path.read_text(encoding="utf-8")
    # Patterns for the original lines (allow flexible whitespace)
    pat_measure = r"measurements\s*=\s*db\.get_all_measurements\(\)\s*if\s*hasattr\(db,\s*'get_all_measurements'\)\s*else\s*\[\]"
    pat_switch = r"switches\s*=\s*db\.get_all_switches\(\)\s*if\s*hasattr\(db,\s*'get_all_switches'\)\s*else\s*\[\]"
    replaced = re.sub(pat_measure, "measurements = list(db.measurements.values())", original)
    replaced = re.sub(pat_switch, "switches = list(db.switch_devices.values())", replaced)
    if replaced != original:
        file_path.write_text(replaced, encoding="utf-8")
        print(json.dumps({"modified": True}))
    else:
        print(json.dumps({"modified": False}))


if __name__ == "__main__":
    main()
