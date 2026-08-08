# AhmedETAP — Release Process

## Versioning Strategy

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Incompatible API changes
- **MINOR** (0.X.0): Backwards-compatible new functionality
- **PATCH** (0.0.X): Backwards-compatible bug fixes

## Release Process

### 1. Prepare Release

```bash
# Update version in package.json
npm version <major|minor|patch> --no-git-tag-version

# Update CHANGELOG.md
# Add new section under [Unreleased]

# Commit changes
git add -A
git commit -m 'chore: prepare release v<X.Y.Z>'
```

### 2. Create Release Tag

```bash
git tag -a v<X.Y.Z> -m 'Release v<X.Y.Z>'
git push origin v<X.Y.Z>
```

### 3. Automated CI/CD

The `publish-engineering-service.yml` workflow automatically:
- Builds multi-arch Docker image (linux/amd64, linux/arm64)
- Pushes to GHCR with version tag
- Updates :latest tag

### 4. Deploy

```bash
# Deploy to Fly.io
./scripts/deploy-engineering-service.sh fly etap-eng-prod --region iad

# Or deploy to Render/Railway
./scripts/deploy-engineering-service.sh render
./scripts/deploy-engineering-service.sh railway
```

### 5. Post-Release

- [ ] Update documentation
- [ ] Notify stakeholders
- [ ] Monitor health checks
- [ ] Review error logs

## Hotfix Process

1. Create branch: `git checkout -b hotfix/v<X.Y.Z>`
2. Fix the issue
3. Bump patch version
4. Merge to main
5. Tag and deploy

## Release Checklist

- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped
- [ ] Tag created
- [ ] CI/CD pipeline successful
- [ ] Health checks passing
- [ ] Stakeholders notified
