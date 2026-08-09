# Contributing to AhmedETAP

Thank you for your interest in contributing to AhmedETAP! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Commit Convention](#commit-convention)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Requesting Features](#requesting-features)

## Code of Conduct

This project adheres to our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold its standards.

## How to Contribute

### Types of Contributions

- **Bug Fixes** — Fix issues in existing functionality
- **Features** — Add new engineering studies, agents, or UI components
- **Documentation** — Improve guides, API docs, or inline comments
- **Tests** — Add test coverage for existing or new code
- **Performance** — Optimize solvers, caching, or frontend rendering
- **Security** — Identify and fix security vulnerabilities

### First-Time Contributors

Look for issues labeled `good-first-issue` or `help-wanted`.

## Development Setup

```bash
# Fork and clone
git clone https://github.com/<your-username>/AhmedETAP.git
cd AhmedETAP

# Create virtual environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install frontend dependencies
cd ui && pnpm install && cd ..

# Run validation
python validate_syntax.py
pytest -q
```

## Coding Standards

### Python
- Follow PEP 8 with `ruff` linter
- Type hints for all function signatures
- Docstrings for public APIs (Google style)
- Max line length: 100 characters

### TypeScript/React
- ESLint + Prettier for formatting
- Functional components with hooks
- TypeScript strict mode
- Tailwind CSS for styling

### Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add transient stability analysis
fix: resolve load flow convergence issue
docs: update API documentation
test: add arc flash validation tests
refactor: simplify relay coordination logic
```

## Pull Request Process

1. Create a feature branch: `git checkout -b feat/my-feature`
2. Make changes and validate: `pytest -q && cd ui && pnpm build`
3. Commit with conventional message
4. Push and open a Pull Request
5. Fill in the PR template
6. Ensure CI passes
7. Request review from maintainers

## Reporting Bugs

Use the [Bug Report template](https://github.com/ahmdelbaz28-ux/AhmedETAP/issues/new?template=bug_report.md) with:
- Steps to reproduce
- Expected vs actual behavior
- Environment details
- Screenshots if applicable

## Requesting Features

Use the [Feature Request template](https://github.com/ahmdelbaz28-ux/AhmedETAP/issues/new?template=feature_request.md) with:
- Problem description
- Proposed solution
- Alternatives considered
- Additional context
