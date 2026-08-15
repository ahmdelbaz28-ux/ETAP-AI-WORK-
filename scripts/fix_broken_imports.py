#!/usr/bin/env python3
"""
Fix broken multi-line imports in Python files.

Pattern: A block of indented names like:
    SOMETHING,
    OtherThing,
)

that is missing its `from <module> import (` line.

Strategy:
1. Detect each broken import block
2. Use the first imported name to search the codebase for its definition
3. Reconstruct the `from <module> import (` line
"""

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path("/home/z/my-project/ETAP-AI-WORK")

def find_syntax_error_files():
    """Use ruff to find files with invalid-syntax errors."""
    result = subprocess.run(
        ["python3", "-m", "ruff", "check", "--output-format=concise", "tests/", "backend/", "api/", "integrations/", "parsers/", "integration/", "scripts/"],
        capture_output=True, text=True, timeout=120,
        cwd=REPO_ROOT
    )
    
    files = set()
    for line in result.stdout.strip().split('\n'):
        if 'invalid-syntax' in line:
            parts = line.split(':')
            if len(parts) >= 1:
                files.add(parts[0])
    
    return sorted(files)


def find_symbol_module(symbol_name):
    """Search the codebase for the module that defines a given symbol."""
    # Search for class/function/variable definitions
    patterns = [
        f"class {symbol_name}",       # class definition
        f"def {symbol_name}",         # function definition
        f"{symbol_name} =",           # variable assignment
        f"{symbol_name}:",            # typed variable
    ]
    
    candidates = {}
    for pattern in patterns:
        try:
            result = subprocess.run(
                ["rg", "-l", "--type", "py", pattern, 
                 "--glob", "!tests/**", "--glob", "!__pycache__/**", "--glob", "!.git/**"],
                capture_output=True, text=True, timeout=10,
                cwd=REPO_ROOT
            )
            for filepath in result.stdout.strip().split('\n'):
                if filepath and filepath.endswith('.py') and not filepath.startswith('tests/'):
                    # Convert file path to module path
                    rel = Path(filepath)
                    parts = list(rel.with_suffix('').parts)
                    # Remove __init__ from parts
                    if parts and parts[-1] == '__init__':
                        parts = parts[:-1]
                    module = '.'.join(parts)
                    candidates[module] = candidates.get(module, 0) + 1
        except:
            pass
    
    if not candidates:
        return None
    
    # Return the most common module
    return max(candidates, key=candidates.get)


def fix_file(filepath):
    """Fix broken imports in a single file."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    changed = False
    i = 0
    new_lines = []
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this line starts a broken import block
        # Pattern: line starts with 4+ spaces and a name, followed by comma
        # and the previous line does NOT end with "import (" or "import \\"
        stripped = line.strip()
        prev_stripped = new_lines[-1].strip() if new_lines else ""
        
        if (stripped and 
            not stripped.startswith('#') and
            not stripped.startswith('"""') and
            not stripped.startswith("'''") and
            (stripped.endswith(',') or (stripped.rstrip(',').isidentifier() and i + 1 < len(lines) and lines[i+1].strip() == ')')) and
            line[0] == ' ' and  # indented
            not prev_stripped.endswith('import (') and
            not prev_stripped.endswith('import \\') and
            not prev_stripped.endswith('(') and
            'import' not in prev_stripped):
            
            # This looks like a broken import block
            # Collect all the imported names
            imported_names = []
            j = i
            while j < len(lines):
                s = lines[j].strip()
                if s == ')':
                    # End of import block
                    j += 1
                    break
                if s.endswith(','):
                    imported_names.append(s[:-1].strip())
                elif s == ')':
                    break
                else:
                    # Last name without comma before )
                    imported_names.append(s.strip())
                j += 1
            
            if imported_names and j <= len(lines):
                # Try to find the module for the first imported name
                first_name = imported_names[0]
                module = find_symbol_module(first_name)
                
                if module:
                    # Reconstruct the import
                    indent = ' ' * (len(line) - len(line.lstrip()))
                    new_lines.append(f"from {module} import (\n")
                    for k in range(i, j):
                        new_lines.append(lines[k])
                    changed = True
                    print(f"  Fixed: from {module} import ({first_name}, ...) in {filepath}")
                    i = j
                    continue
                else:
                    # Can't find module, comment out the broken block
                    print(f"  WARNING: Can't find module for {first_name} in {filepath}, commenting out")
                    for k in range(i, j):
                        new_lines.append(f"# BROKEN IMPORT: {lines[k]}")
                    changed = True
                    i = j
                    continue
        
        new_lines.append(line)
        i += 1
    
    if changed:
        with open(filepath, 'w') as f:
            f.writelines(new_lines)
    
    return changed


def main():
    os.chdir(REPO_ROOT)
    
    print("Finding files with syntax errors...")
    files = find_syntax_error_files()
    print(f"Found {len(files)} files with syntax errors\n")
    
    fixed = 0
    for filepath in files:
        full_path = REPO_ROOT / filepath
        if not full_path.exists():
            continue
        print(f"Processing {filepath}...")
        if fix_file(str(full_path)):
            fixed += 1
    
    print(f"\nFixed {fixed} files out of {len(files)}")


if __name__ == "__main__":
    main()
