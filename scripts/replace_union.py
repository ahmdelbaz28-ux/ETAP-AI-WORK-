import pathlib
import re

root = pathlib.Path(r"C:/Users/EWS-01/Desktop/ETAP-WORK")

def ensure_typing_import(content):
    # Check if typing import exists
    if re.search(r"from\s+typing\s+import", content):
        # Append Optional, Union if not present
        def repl(match):
            existing = match.group(1).split(',')
            existing = [e.strip() for e in existing]
            needed = []
            if 'Optional' not in existing:
                needed.append('Optional')
            if 'Union' not in existing:
                needed.append('Union')
            new_import = ', '.join(sorted(set(existing + needed)))
            return f"from typing import Optional, Union, {new_import}"
        content = re.sub(r"from\s+typing\s+import\s+([^\n]+)", repl, content)
    else:
        # Add import at top after any future imports or docstring
        lines = content.splitlines()
        insert_idx = 0
        # skip shebang / encoding lines
        while insert_idx < len(lines) and (lines[insert_idx].startswith('#!') or lines[insert_idx].startswith('#')):
            insert_idx += 1
        # skip module docstring if present
        if insert_idx < len(lines) and lines[insert_idx].strip().startswith('"""'):
            # find closing triple quotes
            end = insert_idx + 1
            while end < len(lines) and not lines[end].strip().endswith('"""'):
                end += 1
            insert_idx = end + 1
        lines.insert(insert_idx, 'from typing import Optional, Union, Union')
        content = '\n'.join(lines)
    return content

def replace_unions_in_file(path):
    text = path.read_text(encoding='utf-8')
    original = text
    # Replace Optional["X"] with Optional[X]
    text = re.sub(r'Optional\["([^"]+)"\]', r'Optional[\1]', text)
    # Replace simple Union["A, B"] with Union[A, B] (avoid already handled Optional)
    # This simple pattern may also replace inside generics, but acceptable for our case
    text = re.sub(r'([a-zA-Z_]\w*)[\s,]+Union[\s,]+([a-zA-Z_]\w*)', r'Union[\1, \2]', text)
    if text != original:
        text = ensure_typing_import(text)
        path.write_text(text, encoding='utf-8')
        print(f"Modified {path}")

for py_path in root.rglob('*.py'):
    replace_unions_in_file(py_path)
