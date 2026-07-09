import ast, os, sys

bugs = []
count = 0

for root, dirs, files in os.walk('api'):
    for f in files:
        if not f.endswith('.py'):
            continue
        count += 1
        path = os.path.join(root, f)
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                content = fh.read()
            ast.parse(content)
        except SyntaxError as e:
            bugs.append(f'SYNTAX ERROR: {path}: {e}')
            continue

        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            lower = s.lower()
            # Bare except
            if lower == 'except:' or lower.startswith('except :'):
                bugs.append(f'{path}:{i}: Bare except clause')
            # Hardcoded passwords / secrets assigned directly
            if '=' in s:
                var_part = s.split('=')[0].strip()
                val_part = s.split('=', 1)[1].strip()
                is_secret_var = any(k in var_part.lower() for k in 
                    ['password', 'secret', 'api_key', 'api_secret'])
                is_secret_val = ('"' in val_part or "'" in val_part) and len(val_part) > 20
                if is_secret_var and is_secret_val:
                    has_env_call = any(x in s for x in ['os.getenv', 'environ.get', 'os.environ'])
                    if not has_env_call:
                        bugs.append(f'{path}:{i}: Possible hardcoded credential: {s[:80]}')

print(f'Files scanned: {count}')
print(f'Issues found: {len(bugs)}')
for b in bugs:
    print(f'  {b}')