# GitHub Repository Optimization

This document captures the recommended GitHub presentation settings for the ETAP AI Engineering Platform repository.

## Repository description

Enterprise-grade AI engineering platform for validated power-system studies, ETAP automation, GIS enrichment, and autonomous technical workflows.

## Topics and tags

```text
power-systems
electrical-engineering
etap
arc-flash
load-flow
short-circuit
protection-coordination
gis
digital-twin
ai-agents
rag
fastapi
mastra
docker
kubernetes
cybersecurity
engineering
```

## Recommended labels

| Label | Color | Purpose |
|---|---|---|
| `engineering` | `#2563eb` | Power-system study and calculation work |
| `etap-integration` | `#7c3aed` | ETAP automation and COM workflow issues |
| `gis-integration` | `#059669` | GIS ingestion, validation, and enrichment |
| `security` | `#dc2626` | Authentication, authorization, secrets, audit |
| `documentation` | `#64748b` | Docs, diagrams, README, examples |
| `validation` | `#16a34a` | Test and engineering validation coverage |
| `deployment` | `#0891b2` | Docker, Kubernetes, cloud, infrastructure |
| `ui` | `#9333ea` | Frontend and user experience |
| `good first issue` | `#0e7490` | Contributor-friendly tasks |
| `help wanted` | `#f97316` | Community contribution opportunities |

## Release readiness checklist

- [ ] Update `CHANGELOG.md`
- [ ] Create a GitHub release with summary, highlights, and migration notes
- [ ] Attach deployment notes and validation evidence
- [ ] Tag the release commit
- [ ] Verify Docker image build and push workflow
- [ ] Verify UI build and backend test status
- [ ] Confirm README and docs links render correctly

## Wiki readiness

Recommended wiki pages:

1. Home
2. Architecture Overview
3. ETAP Integration Guide
4. GIS Integration Guide
5. Security Model
6. Deployment Patterns
7. Operations Runbook
8. Contributor Guide
9. Engineering Validation
10. Release Process

## Social preview

Use `docs/assets/banner.svg` as the repository social preview after exporting or converting it to PNG if GitHub requires a raster image.
