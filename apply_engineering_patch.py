import json
import os
import sys


def main():
    # Path to the target file relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_path = os.path.join(script_dir, 'engineering_service.py')

    if not os.path.isfile(target_path):
        print(json.dumps({"modified": False, "error": "File not found"}))
        sys.exit(1)

    with open(target_path, encoding='utf-8') as f:
        lines = f.readlines()

    modified = False
    lines_added = 0

    # 1. Insert import after the fastapi import line
    for i, line in enumerate(lines):
        if line.lstrip().startswith('from fastapi import'):
            import_line = 'from core.metrics import REQUEST_ERRORS_TOTAL, REQUEST_LATENCY_SECONDS\n'
            # Avoid duplicate insertion
            if i + 1 < len(lines) and lines[i + 1] == import_line:
                break
            lines.insert(i + 1, import_line)
            modified = True
            lines_added += 1
            break

    # 2. Insert latency and error tracking after elapsed_ms line
    for i, line in enumerate(lines):
        if 'elapsed_ms = (time.perf_counter() - start) * 1000' in line:
            indent = line[:len(line) - len(line.lstrip())]
            insertion = [
                f"{indent}# Record request latency in seconds\n",
                f"{indent}REQUEST_LATENCY_SECONDS.labels(method=request.method, route=request.url.path).observe(elapsed_ms / 1000)\n",
                f"{indent}# Increment error counter for HTTP >=400\n",
                f"{indent}if status_code >= 400:\n",
                f"{indent}    REQUEST_ERRORS_TOTAL.labels(method=request.method, route=request.url.path).inc()\n",
            ]
            # Avoid duplicate insertion
            if lines[i+1:i+1+len(insertion)] != insertion:
                lines[i+1:i+1] = insertion
                modified = True
                lines_added += len(insertion)
            break

    if modified:
        with open(target_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(json.dumps({"modified": True, "lines_added": lines_added}))
    else:
        print(json.dumps({"modified": False, "lines_added": 0}))

if __name__ == '__main__':
    main()
