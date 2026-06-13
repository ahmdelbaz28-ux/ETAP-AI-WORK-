# Contributing to ETAP AI Engineering Platform

Thank you for your interest in contributing! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Requesting Features](#requesting-features)

## Code of Conduct

This project adheres to the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/ETAP-AI-WORK-.git`
3. Create a branch: `git checkout -b feature/my-feature`
4. Make your changes
5. Run tests: `pnpm test && python validation_suite.py`
6. Commit: `git commit -m 'feat: add new feature'`
7. Push: `git push origin feature/my-feature`
8. Open a Pull Request

## Development Setup

### Prerequisites

- Python 3.13+
- Node.js 22+
- pnpm
- Docker (optional)

### Installation

```bash
# Clone the repo
git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
cd ETAP-AI-WORK-

# Install Python dependencies
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Install Node.js dependencies
pnpm install

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Run validation
python validation_suite.py
```

### Running Locally

```bash
# Terminal 1: Python backend
python3 engineering_service.py --host 0.0.0.0 --port 8000

# Terminal 2: Mastra frontend
pnpm dev

# Or with Docker
./quickstart.sh
```

## Coding Standards

### Python

- Follow PEP 8
- Use type hints
- Write docstrings for public functions
- Maximum line length: 88 characters (Black default)

### TypeScript

- Use strict mode
- Follow Airbnb style guide
- Prefer `const` over `let`
- Use meaningful variable names

### Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

### Branch Naming

- `feature/description` — New features
- `fix/description` — Bug fixes
- `docs/description` — Documentation
- `refactor/description` — Refactoring

## Testing

### Running Tests

```bash
# Python validation suite
python validation_suite.py

# Python unit tests
pytest tests/unit_tests.py -v

# TypeScript tests
pnpm test

# UI tests
cd ui && npx vitest run
```

### Test Requirements

- All new features must include tests
- Bug fixes must include a regression test
- Maintain or improve code coverage
- Tests must pass before merging

## Pull Request Process

1. **Create a descriptive PR** with:
   - Clear title following conventional commits
   - Description of changes
   - Link to related issues
   - Screenshots (if applicable)

2. **Ensure CI passes**:
   - TypeScript type check
   - Python validation
   - Dashboard tests
   - Shell script syntax

3. **Request review** from maintainers

4. **Address feedback** promptly

5. **Squash and merge** after approval

## Reporting Bugs

Use the [Bug Report](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/issues/new?template=bug_report.yml) template.

Include:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details
- Logs/screenshots

## Requesting Features

Use the [Feature Request](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/issues/new?template=feature_request.yml) template.

Include:
- Problem statement
- Proposed solution
- Alternatives considered
- Use cases

## Questions?

Open a [Discussion](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/discussions) or contact maintainers.
