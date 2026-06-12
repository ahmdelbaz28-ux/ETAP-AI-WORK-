# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub issue templates (bug report, feature request)
- Pull request template
- Dependabot configuration for dependency scanning
- CODEOWNERS file
- Security scanning workflow (CodeQL + Trivy)
- Code quality workflow (Python lint, TypeScript lint)
- GHCR multi-arch image publishing workflow
- ROADMAP.md with quarterly milestones
- RELEASE.md with release process documentation
- `pyproject.toml` with proper package discovery, dependencies, and test configuration
- `security/__init__.py` with lazy imports for cross-platform safety
- `ui/vitest.config.ts` and `ui/src/test-setup.ts` for UI component testing
- Missing `__init__.py` files in `agents/` and `etap_user_guide/` for package consistency

### Changed
- Moved 18 generated reports from root to docs/
- Moved internal notes to docs/internal/
- Updated README.md with correct repository URLs
- Improved CONTRIBUTING.md with detailed guidelines
- `etap_integration/__init__.py` refactored to lazy `__getattr__` pattern for cross-platform loading
- `etap_com.py:1199-1239`: Fixed `_validate_project_path` UNC path detection for cross-platform
- `etap_compatibility.py:9`: Moved `winreg` import behind platform guard
- `engine/async_executor.py`, `reporting/advanced_reports.py`, `tests/unit_tests.py`: Replaced 14 `datetime.utcnow()` calls with `datetime.now(timezone.utc)`
- `scripts/health-check.ts:353-367`: Updated Mastra status from `warn` to `info` with setup instructions
- `.github/workflows/code-quality.yml`: Hardened mypy type check (removed soft-fail `|| true`, added `--explicit-package-bases` and timeout), added syntax validation and validation suite steps
- `ui/package.json`: Added `test` and `test:watch` scripts for vitest

### Fixed
- Broken Dashboard.test.tsx (installed jsdom)
- Security.yml missing setup-python step
- Security.yml pywin32 filter for Linux CI
- CODEOWNERS trailing newline requirement

## [1.0.0] - 2026-06-04

### Added
- Initial release
- Multi-agent architecture with 9 specialized agents
- Load Flow, Short Circuit, Arc Flash, Harmonic Analysis, OPF
- IEEE 1584-2018, IEC 60909, IEEE 519-2022 compliance
- FastAPI engineering service
- Mastra framework integration
- JWT authentication and RBAC
- Docker support with multi-arch builds
- CI/CD with GitHub Actions
- Comprehensive documentation
