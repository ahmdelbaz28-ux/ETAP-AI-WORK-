# 🛠️ AhmedETAP — Developer Guide

> Practical reference for engineers working on the AhmedETAP codebase.
> For project-wide reference, see [`PROJECT_INDEX.md`](../PROJECT_INDEX.md).

---

## 1. Environment Setup

```bash
# Clone
git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
cd ETAP-AI-WORK-

# Python virtualenv (requires Python 3.12)
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/macOS

# Dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt   # dev extras: pytest, ruff, mypy

# Frontend
cd ui && npm install && cd ..
```

---

## 2. Running the Stack Locally

| Command | What it starts |
|:---|:---|
| `python engineering_service.py` | FastAPI backend on `localhost:8000` |
| `cd ui && npm run dev` | React frontend on `localhost:5173` |
| `celery -A worker.celery_app worker` | Celery async worker |
| `redis-server` | Redis cache (required for caching + Celery) |
| `docker compose up` | **Everything** — all services via Docker Compose |

### Environment Variables (minimum for local dev)

```env
ENVIRONMENT=development
PORT=8000
SECRET_KEY=dev-secret-change-in-prod
DATABASE_URL=sqlite+aiosqlite:///./etap.db
REDIS_URL=redis://localhost:6379/0
```

---

## 3. Code Style & Quality

The project uses **ruff** for linting and formatting (configured in `ruff.toml`):

```bash
# Check for issues
ruff check .

# Auto-fix safe issues
ruff check . --fix

# Format code
ruff format .

# Type checking
mypy .
```

### Pre-commit (recommended)
```bash
pip install pre-commit
pre-commit install
# Runs ruff + mypy automatically on every commit
```

---

## 4. Writing & Running Tests

Tests live in `tests/`. Always prefix test functions with `test_`.

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=. --cov-report=term-missing --cov-report=html

# Run only fast unit tests
pytest -m unit

# Run a specific test file
pytest tests/test_load_flow.py -v

# Run a specific test function
pytest tests/test_load_flow.py::test_newton_raphson_converges -v
```

### Adding Tests

1. Create `tests/test_<module>.py`
2. Import pytest fixtures from `tests/conftest.py`
3. Use `@pytest.mark.unit` / `@pytest.mark.integration` markers

---

## 5. Adding a New API Endpoint

1. **Create (or select) a router file** in `api/`
2. **Define the route** using FastAPI decorators:

```python
# api/my_feature.py
from fastapi import APIRouter, Depends
from api.dependencies import get_current_user

router = APIRouter(prefix="/my-feature", tags=["My Feature"])

@router.post("/action")
async def my_action(data: MySchema, user=Depends(get_current_user)):
    """Perform a new action."""
    return {"result": "ok"}
```

3. **Register in** `api/routes.py`:
```python
from api.my_feature import router as my_feature_router
app.include_router(my_feature_router, prefix="/api/v1")
```

4. **Re-run the indexer** to update the index:
```bash
python indexer.py
```

---

## 6. Adding a New AI Agent

1. Create `agents/my_agent.py`:

```python
class MyAgent:
    """My specialist agent."""

    async def run(self, task: dict) -> dict:
        """Execute the agent's primary task."""
        ...
```

2. Register in the orchestrator `agents/orchestrator.py`
3. Add an API endpoint in `api/agents.py`
4. Write tests in `tests/test_agents.py`

---

## 7. Adding a New Power System Study Type

1. **Implement the numerical engine** in `load_flow/` or `fault_analysis/`
2. **Add a study handler** in `services/study_service.py`
3. **Expose via API** in `api/studies.py`
4. **Create a specialist agent** in `agents/`
5. **Add tests** with a representative small network case

---

## 8. Updating the Project Index

The index is auto-updated by GitHub Actions on every push to `main`.
To update it manually during development:

```bash
python indexer.py
# Generates:
#   PROJECT_INDEX.json  (machine-readable, 516 KB)
#   PROJECT_INDEX.md    (human-readable,  116 KB)
```

---

## 9. Debugging Tips

| Problem | Solution |
|:---|:---|
| `Connection refused :8000` | Check `python engineering_service.py` is running |
| `Redis connection error` | Run `redis-server` or start via Docker |
| `JWT expired` | Re-authenticate via `POST /api/v1/auth/login` |
| `Study timeout` | Increase `CELERY_TASK_TIME_LIMIT` in `.env` |
| Import errors | Activate virtualenv: `.venv\Scripts\activate` |

Full diagnostics: [`docs/TROUBLESHOOTING_GUIDE.md`](TROUBLESHOOTING_GUIDE.md)

---

## 10. Git Workflow

```bash
# Feature branch
git checkout -b feat/your-feature-name

# Commit with conventional commits format
git commit -m "feat(load-flow): add Newton-Raphson convergence tolerance option"
git commit -m "fix(api): correct JWT expiry validation"
git commit -m "docs: update API_REFERENCE for new predict endpoint"
git commit -m "test(agents): add orchestrator unit tests"

# Push and open a PR
git push origin feat/your-feature-name
```

### Commit Message Prefixes

| Prefix | Use for |
|:---|:---|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation changes |
| `test:` | Adding or updating tests |
| `refactor:` | Code restructuring (no behavior change) |
| `perf:` | Performance improvement |
| `ci:` | CI/CD configuration changes |
| `chore:` | Maintenance tasks |

---

## 11. Documentation Files Map

| Need | File |
|:---|:---|
| System design | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |
| API endpoints | [`docs/API_REFERENCE.md`](API_REFERENCE.md) |
| Deployment ops | [`docs/OPERATIONS_RUNBOOK.md`](OPERATIONS_RUNBOOK.md) |
| Security model | [`docs/SECURITY_OPERATIONS_MANUAL.md`](SECURITY_OPERATIONS_MANUAL.md) |
| Standards reference | [`docs/COMPLIANCE.md`](COMPLIANCE.md) |
| Incident response | [`docs/INCIDENT_RESPONSE_RUNBOOK.md`](INCIDENT_RESPONSE_RUNBOOK.md) |
| Debugging | [`docs/TROUBLESHOOTING_GUIDE.md`](TROUBLESHOOTING_GUIDE.md) |
| Recovery | [`docs/DISASTER_RECOVERY_PLAN.md`](DISASTER_RECOVERY_PLAN.md) |
| SLA/SLO | [`docs/SLA_SLO_DOCUMENT.md`](SLA_SLO_DOCUMENT.md) |
| Full code index | [`PROJECT_INDEX.md`](../PROJECT_INDEX.md) |
