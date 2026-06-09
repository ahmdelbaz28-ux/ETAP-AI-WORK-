# Contributing to ETAP AI Engineering Platform

Thank you for your interest in contributing to the ETAP AI Engineering Platform! This document provides guidelines and information for contributors.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of background or identity.

### Our Standards

Examples of behavior that contributes to a positive environment:
- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

Examples of unacceptable behavior:
- The use of sexualized language or imagery
- Trolling, insulting/derogatory comments, and personal attacks
- Public or private harassment
- Publishing others' private information without permission
- Other conduct which could reasonably be considered inappropriate

---

## Getting Started

### Prerequisites

Before contributing, ensure you have:
- Python 3.8+ installed
- Node.js 18+ installed
- pnpm package manager
- Git installed
- Basic understanding of power systems engineering

### First Steps

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/etap-platform.git
   cd etap-platform
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/ORIGINAL_OWNER/etap-platform.git
   ```
4. **Set up development environment** (see below)

---

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check existing issues. When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce** the behavior
- **Expected vs actual behavior**
- **Screenshots** if applicable
- **Environment details** (OS, Python version, etc.)
- **Additional context**

**Example:**
```markdown
**Bug**: Load Flow fails to converge with large systems

**Steps to Reproduce**:
1. Create system with 100+ buses
2. Run load flow analysis
3. Observe non-convergence

**Expected**: Should converge within 50 iterations
**Actual**: Fails after 10 iterations

**Environment**: Python 3.9, Windows 10
```

### Suggesting Features

Feature suggestions should include:
- **Use case**: Why is this feature needed?
- **Proposed solution**: How should it work?
- **Alternatives considered**: Other approaches
- **Additional context**: Examples, mockups, etc.

### Code Contributions

1. **Find an issue** to work on (check "good first issue" labels)
2. **Comment on the issue** expressing interest
3. **Wait for assignment** from maintainers
4. **Fork and create branch** from `develop`
5. **Make your changes** following coding standards
6. **Write tests** for new functionality
7. **Update documentation** as needed
8. **Submit pull request**

---

## Development Setup

### Quick Start

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/etap-platform.git
cd etap-platform

# Install dependencies
make install

# Create .env file
cp .env.example .env
# Edit .env with your configuration

# Run tests
make test

# Start development servers
make run
```

### Manual Setup

```bash
# Python dependencies
pip install -r requirements.txt
pip install pytest pytest-cov black flake8 mypy

# Node.js dependencies
pnpm install

# Verify installation
python validation_suite.py
pytest tests/unit_tests.py -v
```

### IDE Configuration

#### VS Code
Install recommended extensions:
- Python
- Pylance
- ESLint
- Prettier
- Docker
- Kubernetes

Settings (`settings.json`):
```json
{
  "python.linting.enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

---

## Coding Standards

### Python Code

#### Style Guide
- Follow [PEP 8](https://pep8.org/)
- Use [Black](https://black.readthedocs.io/) for formatting
- Maximum line length: 88 characters
- Use type hints where applicable

#### Example
```python
from typing import List, Optional
import numpy as np


class LoadFlowSolver:
    """Newton-Raphson load flow solver."""
    
    def __init__(self, system: PowerSystem, max_iter: int = 50):
        """Initialize solver.
        
        Args:
            system: Power system model
            max_iter: Maximum iterations (default: 50)
        """
        self.system = system
        self.max_iter = max_iter
        self.converged: bool = False
    
    def solve(self, tolerance: float = 1e-6) -> bool:
        """Solve load flow problem.
        
        Args:
            tolerance: Convergence tolerance
            
        Returns:
            True if converged, False otherwise
        """
        # Implementation
        pass
```

#### Naming Conventions
- **Classes**: PascalCase (`LoadFlowSolver`)
- **Functions/Methods**: snake_case (`solve_load_flow`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_ITERATIONS`)
- **Private**: Leading underscore (`_internal_method`)

### TypeScript Code

#### Style Guide
- Use TypeScript strict mode
- Follow Airbnb TypeScript style guide
- Use Prettier for formatting
- Prefer interfaces over types

#### Example
```typescript
interface LoadFlowResult {
  converged: boolean;
  iterations: number;
  busResults: Map<number, BusResult>;
  lineResults: Map<number, LineResult>;
}

class LoadFlowAgent implements IAgent {
  private readonly maxIterations: number;
  
  constructor(config: AgentConfig) {
    this.maxIterations = config.maxIterations ?? 50;
  }
  
  async execute(system: PowerSystem): Promise<LoadFlowResult> {
    // Implementation
    return {
      converged: true,
      iterations: 5,
      busResults: new Map(),
      lineResults: new Map()
    };
  }
}
```

### Documentation

#### Docstrings (Python)
Use Google-style docstrings:

```python
def calculate_fault_current(
    voltage_kv: float,
    impedance_ohm: complex,
    fault_type: str = "three_phase"
) -> FaultResult:
    """Calculate short circuit fault current.
    
    Args:
        voltage_kv: System voltage in kV
        impedance_ohm: Fault impedance in ohms
        fault_type: Type of fault (three_phase, line_to_ground, etc.)
        
    Returns:
        FaultResult containing fault current and related parameters
        
    Raises:
        ValueError: If voltage_kv is negative
        ZeroDivisionError: If impedance is zero
        
    Example:
        >>> result = calculate_fault_current(115.0, complex(0.5, 2.0))
        >>> print(result.fault_current_ka)
        25.5
    """
    pass
```

#### JSDoc (TypeScript)
```typescript
/**
 * Calculate arc flash incident energy.
 * 
 * @param voltageKV - System voltage in kilovolts
 * @param faultCurrentKA - Bolted fault current in kiloamperes
 * @param durationSec - Arc duration in seconds
 * @returns Arc flash calculation results
 * @throws {ValidationError} If parameters are out of valid range
 * @example
 * ```typescript
 * const result = calculateArcFlash(4.16, 20.0, 0.5);
 * console.log(result.incidentEnergy); // 8.5 cal/cm²
 * ```
 */
function calculateArcFlash(
  voltageKV: number,
  faultCurrentKA: number,
  durationSec: number
): ArcFlashResult {
  // Implementation
}
```

---

## Testing Guidelines

### Writing Tests

#### Unit Tests
- Test one thing per test function
- Use descriptive test names
- Follow AAA pattern (Arrange, Act, Assert)
- Mock external dependencies

```python
def test_load_flow_convergence():
    """Test that load flow converges for simple 2-bus system."""
    # Arrange
    system = create_test_system()
    solver = LoadFlowSolver(system)
    
    # Act
    converged = solver.solve()
    
    # Assert
    assert converged is True
    assert abs(system.buses[2].voltage - 0.98) < 0.01
```

#### Integration Tests
- Test component interactions
- Use real data when possible
- Clean up after tests

#### Performance Tests
- Benchmark critical operations
- Set acceptable thresholds
- Monitor regression

### Running Tests

```bash
# All tests
make test

# Specific test file
pytest tests/test_load_flow.py -v

# With coverage
pytest --cov=. --cov-report=html

# Performance tests
pytest tests/performance/ -v --benchmark-only
```

### Test Coverage Requirements
- **Minimum**: 80% line coverage
- **Target**: 90% line coverage
- **Critical modules**: 95% coverage

---

## Documentation

### Updating Documentation

When making code changes:
1. Update relevant docstrings/comments
2. Update API documentation if endpoints change
3. Update README if features change
4. Add examples for new features
5. Update CHANGELOG.md

### Documentation Style
- Clear and concise
- Include code examples
- Explain "why" not just "what"
- Link to related documentation
- Keep up to date with code

---

## Commit Messages

### Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, semicolons, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

```bash
# Good commit messages
git commit -m "feat(load-flow): add Newton-Raphson solver implementation"
git commit -m "fix(fault-analysis): correct zero-sequence impedance calculation"
git commit -m "docs(api): update endpoint documentation for v1.1"
git commit -m "test(security): add authentication unit tests"

# Bad commit messages
git commit -m "fixed stuff"
git commit -m "WIP"
git commit -m "asdf"
```

### Scopes
Common scopes:
- `load-flow`
- `fault-analysis`
- `harmonic`
- `opf`
- `security`
- `api`
- `docs`
- `tests`
- `deps` (dependencies)

---

## Pull Request Process

### Before Submitting

1. **Update your branch**:
   ```bash
   git fetch upstream
   git rebase upstream/develop
   ```

2. **Run all checks**:
   ```bash
   make lint
   make test
   make validate
   ```

3. **Update documentation** if needed

4. **Add tests** for new functionality

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests passing
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Changes tested locally

## Related Issues
Closes #123
```

### Review Process
1. Mainters review code quality
2. Automated checks must pass
3. At least 1 approval required
4. Address review comments
5. Merge when approved

---

## Release Process

### Version Bumping

1. Update version in `package.json` and `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create release branch: `release/v1.x.x`
4. Create PR to `main`
5. Tag release after merge

### Release Checklist

- [ ] All tests passing
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version numbers bumped
- [ ] Docker image built and pushed
- [ ] Release notes published
- [ ] Announcement sent to community

---

## Community

### Communication Channels
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and ideas
- **Discord**: Real-time chat (link in README)
- **Email**: support@etap-platform.com

### Recognition

Contributors are recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project website
- Annual contributor spotlight

---

## Questions?

If you have questions about contributing:
1. Check existing documentation
2. Search GitHub Issues and Discussions
3. Ask in Discord community
4. Open a GitHub Issue

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to ETAP AI Engineering Platform! 🎉
