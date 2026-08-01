#!/usr/bin/env python3
"""Measure cognitive complexity (SonarSource python:S3776 semantics).

Faithful port of SonarSource/sonar-python
``org.sonar.python.metrics.CognitiveComplexityVisitor``:

  - +1 + nesting: if, for, while, except, ternary (ConditionalExpression)
  - +1 (no nesting bonus): elif, else
  - boolean and/or: +1 per run of the same operator type (``a and b and c``
    = +1, ``a and b or c`` = +2); no nesting bonus
  - nesting increments inside if/elif/else bodies, for/while bodies and
    their else bodies, and except bodies; NOT inside try/finally/with/
    function/class bodies
  - ternary: +1 + nesting, and its test/both arms are visited at
    nesting+1
  - return/break/continue/raise not counted; match/case not counted
  - nested function defs: nesting level = parent level + 1 when parent
    is a function (except "wrapper functions", which inherit the parent
    level); class bodies reset to level 0

Usage:
    py -3.12 tools/cogcomplex.py <file.py> [func_name ...]
"""

import ast
import sys
from pathlib import Path


class _Complexity(ast.NodeVisitor):
    def __init__(self):
        self.complexity = 0
        self._levels = [0]
        self._func_stack = []

    @property
    def _nesting(self):
        return self._levels[-1]

    # -- statements ------------------------------------------------------

    def visit_If(self, node):
        self.visit(node.test)
        self.complexity += 1 + self._nesting
        self._stmt_list(node.body)
        orelse = node.orelse
        while orelse and len(orelse) == 1 and isinstance(orelse[0], ast.If):
            child = orelse[0]
            self.visit(child.test)
            self.complexity += 1
            self._stmt_list(child.body)
            orelse = child.orelse
        if orelse:
            self.complexity += 1
            self._stmt_list(orelse)

    def visit_For(self, node):
        self._loop(node)

    def visit_AsyncFor(self, node):
        self._loop(node)

    def visit_While(self, node):
        self._loop(node)

    def visit_ExceptHandler(self, node):
        self.complexity += 1 + self._nesting
        self._stmt_list(node.body)

    def visit_Try(self, node):
        for stmt in node.body:
            self.visit(stmt)
        for handler in node.handlers:
            self.visit(handler)
        if node.orelse:
            self.complexity += 1
            self._stmt_list(node.orelse)
        for stmt in node.finalbody:
            self.visit(stmt)

    def visit_With(self, node):
        for stmt in node.body:
            self.visit(stmt)

    def visit_AsyncWith(self, node):
        # AsyncWith and With share the same body-visit semantics for
        # complexity accounting; delegate to avoid a duplicate body.
        self.visit_With(node)

    def visit_IfExp(self, node):
        self.complexity += 1 + self._nesting
        self._levels.append(self._nesting + 1)
        self.visit(node.test)
        self.visit(node.body)
        self.visit(node.orelse)
        self._levels.pop()

    def visit_BoolOp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._function_body(node)

    def visit_AsyncFunctionDef(self, node):
        self._function_body(node)

    def visit_ClassDef(self, node):
        self._levels.append(0)
        self.generic_visit(node)
        self._levels.pop()

    def visit_Lambda(self, node):
        self.visit(node.body)

    # -- helpers ---------------------------------------------------------

    def _loop(self, node):
        self.complexity += 1 + self._nesting
        self._stmt_list(node.body)
        if node.orelse:
            self.complexity += 1
            self._stmt_list(node.orelse)

    def _stmt_list(self, stmts):
        self._levels.append(self._nesting + 1)
        for stmt in stmts:
            self.visit(stmt)
        self._levels.pop()

    def _function_body(self, node):
        self._func_stack.append(node)
        if len(self._func_stack) == 1:
            self.generic_visit(node)
        elif self._is_wrapper_function(node):
            self.generic_visit(node)
        else:
            self._levels.append(self._nesting + 1)
            self.generic_visit(node)
            self._levels.pop()
        self._func_stack.pop()

    def _is_wrapper_function(self, node):
        parent = self._func_stack[-2]
        for stmt in parent.body:
            if stmt is node:
                continue
            if not (
                isinstance(stmt, ast.Return)
                and stmt.value is not None
                and isinstance(stmt.value, ast.Name)
            ):
                return False
        return True


def measure(source: str) -> int:
    tree = ast.parse(source)
    visitor = _Complexity()
    visitor.visit(tree)
    return visitor.complexity


def _funcs(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1]).resolve()
    # S8707: validate the CLI-supplied path before touching the filesystem. NOSONAR
    if not path.is_file():
        print(f"Error: not a file: {path}", file=sys.stderr)
        return 2
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = set(sys.argv[2:])
    for fn in _funcs(tree):
        if wanted and fn.name not in wanted:
            continue
        frag = ast.get_source_segment(source, fn) or ""
        cplx = measure(frag)
        print(f"{path}:{fn.lineno} {fn.name}: {cplx}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
