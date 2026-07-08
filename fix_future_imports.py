import pathlib, re, sys

def fix_file(path):
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    # Find __future__ import lines
    future_lines = [i for i, l in enumerate(lines) if re.match(r'\s*from __future__ import annotations', l)]
    if not future_lines:
        return False
    # Remove duplicates, keep first
    first = future_lines[0]
    # Remove other future lines
    for i in reversed(future_lines[1:]):
        del lines[i]
    # Determine insertion point: after any module docstring (triple quotes) and comments
    insert_at = 0
    # Skip shebang if present
    if lines and lines[0].startswith('#!'):
        insert_at = 1
    # Skip encoding comment
    if len(lines) > insert_at and re.match(r'#.*coding[:=]', lines[insert_at]):
        insert_at += 1
    # Skip initial comments
    while insert_at < len(lines) and lines[insert_at].strip().startswith('#'):
        insert_at += 1
    # Skip module docstring if present
    if insert_at < len(lines) and (lines[insert_at].strip().startswith('"""') or lines[insert_at].strip().startswith("'''")):
        # Find closing triple quotes
        delim = lines[insert_at].strip()[:3]
        end = insert_at
        while end < len(lines) and delim not in lines[end]:
            end += 1
        end += 1
        insert_at = end
    # Remove the original future line
    del lines[first]
    # Insert at determined position
    lines.insert(insert_at, 'from __future__ import annotations')
    new_text = '\n'.join(lines) + '\n'
    path.write_text(new_text, encoding='utf-8')
    return True

def main():
    root = pathlib.Path('.')
    for py in root.rglob('*.py'):
        try:
            if fix_file(py):
                print(f'Fixed {py}')
        except Exception as e:
            print(f'Error fixing {py}: {e}', file=sys.stderr)

if __name__ == '__main__':
    main()
