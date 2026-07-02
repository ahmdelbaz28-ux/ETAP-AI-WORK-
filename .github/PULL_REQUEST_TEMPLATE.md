## Summary

Brief description of the changes and **why** they are needed.

## Type of Change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Security fix
- [ ] Dependency update
- [ ] CI/CD change

## Related Issues

Closes #(issue number)
Refs #(issue number)

## Changes Made

- Change 1
- Change 2
- Change 3

## Testing

### Automated Tests
- [ ] Unit tests pass (`pytest -q`)
- [ ] Integration tests pass
- [ ] UI type-check passes (`cd ui && npx tsc --noEmit`)
- [ ] UI builds successfully (`cd ui && npm run build`)
- [ ] Validation suite passes (`python validation_suite.py`)

### Manual Testing
- [ ] Tested locally with `ENVIRONMENT=development`
- [ ] Tested in staging environment
- [ ] Verified all affected endpoints respond correctly
- [ ] Verified no regressions in existing functionality

## Security Checklist

**Required for all PRs:**

- [ ] No hardcoded secrets, API keys, or passwords in the diff
- [ ] No new `console.log`/`print` statements that could leak sensitive data
- [ ] No new `eval()`, `exec()`, or `subprocess(shell=True)` calls
- [ ] No new SQL queries with f-string interpolation (use parameterized queries)
- [ ] No new `os.system()` calls
- [ ] No new `yaml.load()` without `Loader=` argument
- [ ] No new `pickle.load/loads()` on untrusted data
- [ ] New environment variables documented in `.env.example`
- [ ] New dependencies added to `requirements.txt` with version pins

**Required for PRs touching auth/security/API:**

- [ ] Authentication check added to new endpoints
- [ ] Rate limiting considered for new endpoints
- [ ] Input validation added (Pydantic models or explicit checks)
- [ ] Output sanitization considered (no sensitive data in responses)
- [ ] CORS implications reviewed
- [ ] RASP rules updated if new attack vectors introduced

**Required for PRs touching infrastructure:**

- [ ] Docker images use non-root user
- [ ] No secrets in Dockerfiles or docker-compose
- [ ] Helm values use existingSecret for sensitive data
- [ ] Nginx config updated if new routes/paths added
- [ ] Health check endpoints updated if new services added

## Code Quality Checklist

- [ ] Code follows project style guidelines (ruff for Python, ESLint for TS)
- [ ] Self-reviewed the code
- [ ] Comments added for complex logic
- [ ] Documentation updated (README, API_REFERENCE, ARCHITECTURE)
- [ ] No new warnings introduced (`ruff check . && ruff format --check .`)
- [ ] Type hints added to new Python functions
- [ ] TypeScript types added to new functions/components

## Breaking Changes

If this PR introduces breaking changes, describe:
1. What breaks
2. Migration path for users
3. Whether a deprecation warning was added in a prior release

## Deployment Notes

Any special deployment instructions:
- [ ] Database migration required (`alembic upgrade head`)
- [ ] Environment variables need to be set
- [ ] Docker images need to be rebuilt
- [ ] HF Space needs manual restart
- [ ] Vercel deployment will auto-trigger

## Screenshots (if applicable)

<!-- Add screenshots showing UI changes, before/after comparisons -->

## Reviewer Notes

<!-- Anything specific reviewers should focus on, or context that would help review -->
