
"""Syntax and dependency validation script for the entire codebase."""
import ast
import os
import sys


def validate_python_syntax():
    results = []
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules' and d != '__pycache__']
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding='utf-8') as fh:
                        ast.parse(fh.read())
                    results.append(('OK', path, ''))
                except SyntaxError as e:
                    results.append(('SYNTAX_ERROR', path, str(e)))
                except Exception as e:
                    results.append(('ERROR', path, str(e)))
    return results

def check_imports():
    results = []
    py_files = []
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules' and d != '__pycache__']
        for f in files:
            if f.endswith('.py'):
                py_files.append(os.path.join(root, f))

    for path in py_files:
        try:
            with open(path, encoding='utf-8') as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith('.'):
                        # Relative import - check within package
                        results.append(('RELATIVE_IMPORT', path, node.module))
                    elif node.module:
                        # Absolute import - check if it's a local module
                        parts = node.module.split('.')
                        if os.path.exists(os.path.join('.', *parts[:-1] or parts, '__init__.py')) or                            os.path.exists(os.path.join('.', *parts) + '.py'):
                            results.append(('LOCAL_IMPORT', path, node.module))
        except Exception as e:
            results.append(('PARSE_ERROR', path, str(e)))
    return results

def detect_circular_deps():
    """Simple circular dependency detection for local packages."""
    packages = {}
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules' and d != '__pycache__']
        if '__init__.py' in files:
            pkg = root.replace(os.sep, '.').lstrip('.')
            imports = []
            for f in files:
                if f.endswith('.py'):
                    fpath = os.path.join(root, f)
                    try:
                        with open(fpath, encoding='utf-8') as fh:
                            tree = ast.parse(fh.read())
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ImportFrom) and node.module:
                                if node.module.startswith(pkg.split('.')[0]):
                                    imports.append(node.module)
                    except (OSError, UnicodeDecodeError, SyntaxError) as parse_err:
                        # Don't lose parse failures silently; track them so
                        # the caller can surface them in the final report.
                        print(f'  [PARSE_ERROR] {fpath}: {type(parse_err).__name__}: {parse_err}')
            packages[pkg] = imports

    circular = []
    for pkg, imports in packages.items():
        for imp in imports:
            imp_base = imp.split('.')[0] if imp else ''
            pkg_base = pkg.split('.')[0] if pkg else ''
            if imp_base == pkg_base and imp != pkg:
                # Same top-level package -> intra-package cycle candidate.
                # Record the edge (pkg -> imp) so the caller can warn the user.
                circular.append((pkg, imp))
    return packages, circular

if __name__ == '__main__':
    print('=' * 70)
    print('PYTHON SYNTAX VALIDATION REPORT')
    print('=' * 70)

    syntax_results = validate_python_syntax()
    errors = [r for r in syntax_results if r[0] != 'OK']
    oks = [r for r in syntax_results if r[0] == 'OK']

    print(f'Total Python files scanned: {len(syntax_results)}')
    print(f'Syntax OK: {len(oks)}')
    print(f'Errors: {len(errors)}')
    print()

    if errors:
        print('SYNTAX ERRORS:')
        for e in errors:
            print(f'  [{e[0]}] {e[1]}')
            print(f'    {e[2]}')
        print()

    print('=' * 70)
    print('IMPORT RESOLUTION CHECK')
    print('=' * 70)
    import_results = check_imports()
    local_imports = [r for r in import_results if r[0] == 'LOCAL_IMPORT']
    print(f'Local module imports found: {len(local_imports)}')
    for li in local_imports:
        print(f'  {li[1]} -> {li[2]}')
    print()

    print('=' * 70)
    print('CIRCULAR DEPENDENCY CHECK')
    print('=' * 70)
    packages, circular = detect_circular_deps()
    for pkg, imports in packages.items():
        print(f'  {pkg} imports: {imports}')
    if circular:
        print('CIRCULAR DEPENDENCIES DETECTED:')
        for c in circular:
            print(f'  {c}')
    else:
        print('No circular dependencies detected at package level.')
    print()

    # Summary
    print('=' * 70)
    print('SUMMARY')
    print('=' * 70)
    critical = len(errors)
    print(f'Critical syntax errors: {critical}')
    print(f'Files validated: {len(syntax_results)}')
    if critical == 0:
        print('STATUS: ALL PYTHON FILES PASS SYNTAX VALIDATION')
    else:
        print('STATUS: CRITICAL ERRORS FOUND - FIX REQUIRED')

    sys.exit(1 if critical > 0 else 0)
