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

### Changed
- Moved 18 generated reports from root to docs/
- Moved internal notes to docs/internal/
- Updated README.md with correct repository URLs
- Improved CONTRIBUTING.md with detailed guidelines

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
