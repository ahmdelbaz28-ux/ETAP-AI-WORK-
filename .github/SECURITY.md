# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 2.1.x   | ✅ Active           |
| < 2.1   | ❌ Not supported    |

## Reporting a Vulnerability

If you discover a security vulnerability in AhmedETAP:

1. **DO NOT** open a public GitHub issue.
2. Email the maintainer directly: **ahmdelbaz28@gmail.com**
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Affected files/versions
   - Suggested fix (if any)
4. You will receive an acknowledgment within 48 hours.
5. A fix will be released within 30 days for High/Critical issues.

## Security Architecture

### Defense in Depth

The platform applies defense in depth across 5 layers:

1. **Network** — Nginx reverse proxy, rate limiting, TLS termination, security headers
2. **Application** — FastAPI middleware (CORS, CSP, HSTS, X-Frame-Options), API key auth, JWT
3. **Data** — Row-Level Security (RLS) in Supabase, encrypted at rest
4. **Secrets** — Environment variables only, never committed; pre-commit secret scanning
5. **Observability** — Langfuse traces, LangWatch monitoring, SIEM syslog forwarding

### Secret Management

#### Where secrets live

| Environment | Storage |
|-------------|---------|
| Local dev | `.env` file (gitignored) |
| HF Space | Hugging Face Space secrets (encrypted) |
| Vercel | Vercel project environment variables (encrypted) |
| Production (K8s) | Kubernetes Secrets (encrypted at rest with EncryptionConfiguration) |
| GitHub Actions | Repository secrets (encrypted, masked in logs) |

#### What is NEVER committed

- API keys (OpenAI, Anthropic, Google, NVIDIA, Hugging Face)
- Database connection strings with credentials
- JWT signing keys
- Fernet encryption keys
- Supabase service role keys
- Neo4j passwords
- Vercel tokens
- GitHub PATs
- `.env`, `.env.local`, `.env.production`, `.env.staging`

#### Pre-commit hooks (mandatory)

The repo includes `.pre-commit-config.yaml` with the following checks that run before every commit:

- **TruffleHog** — verified secret detection (blocks commit)
- **detect-secrets** — baseline + new secret detection (blocks commit)
- **detect-private-key** — private key file detection (blocks commit)
- **Bandit** — Python SAST scan (Medium+ severity blocks commit)
- **Ruff** — linting + formatting
- **Custom security_scan.py** — project-specific checks

Install pre-commit hooks locally:
```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg
```

### Authentication & Authorization

#### API Key Authentication

- Every non-public endpoint requires `X-API-Key` header
- API keys are stored as HMAC-SHA256 hashes (never plaintext)
- Rate-limited per client IP (default: 100 req/min)

#### JWT Tokens

- Signed with HS256 using `JWT_SECRET_KEY` (min 32 chars)
- 30-minute expiry for access tokens
- Refresh tokens: 7-day expiry, rotated on use
- Stored in HTTP-only, Secure, SameSite=Strict cookies (web UI)

#### Multi-Factor Authentication (MFA)

- TOTP-based (RFC 6238) via `pyotp`
- Backup codes (10 single-use, hashed with bcrypt)
- Enforced for admin role

### Row-Level Security (Supabase)

All Supabase tables have RLS policies enabled:

- Users can only see their own data
- Service role key bypasses RLS (server-side only, never exposed to client)
- Anon key can only access public endpoints

### CORS Configuration

Allowed origins are explicitly whitelisted:

```python
allow_origins = [
    "https://huggingface.co",
    "https://*.hf.space",  # HF Space subdomains
    "http://localhost:3000",  # Local dev (Vite)
    "http://localhost:5173",  # Local dev (Vite alt)
]
allow_credentials = False  # API-only, no cookies
allow_methods = ["*"]
allow_headers = ["*"]
```

Production deployments should override this with environment-specific origins via `ENGINEERING_SERVICE_CORS_ORIGINS`.

### Security Headers

The following headers are added to every HTTP response:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `SAMEORIGIN` | Prevent clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer leakage |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force HTTPS (HSTS, HTTPS only) |
| `Content-Security-Policy` | (see below) | Limit resource loading |

### LLM Safety Guardrails

The platform includes defense-in-depth against LLM abuse:

- **Input length limit** (`LLM_MAX_INPUT_CHARS=50000`) — refuse oversized inputs
- **Model allowlist** (`LLM_APPROVED_MODELS`) — refuse unapproved models
- **Agent tag requirement** (`LLM_REQUIRE_AGENT_TAG=true`) — refuse untagged calls
- **Override mode off** (`LANGFUSE_OVERRIDE_MODE=false`) — local YAML wins over remote prompts
- **Integrity hash check** on remote Langfuse prompts before use

### CI/CD Security

The CI/CD pipeline enforces:

1. **TruffleHog** secret scan on every push and PR (blocking)
2. **Bandit** SAST scan (Medium+ severity blocks)
3. **pip-audit** Python dependency vulnerability check (blocking)
4. **npm audit** Node dependency vulnerability check (blocking)
5. **Trivy** filesystem + container image scan (CRITICAL+HIGH blocks)
6. **CodeQL** semantic analysis (weekly)
7. **Dependency Review** on PRs (high-severity vulns block merge)

### Incident Response

#### If a secret is leaked

1. **Rotate the secret immediately** at its source (DO NOT just delete the commit)
2. Audit logs for misuse (Langfuse, SIEM, Supabase dashboard)
3. Force-logout all users if JWT secret was leaked
4. Notify users if PII was exposed
5. Post-mortem: how did the leak happen? Add a guard to prevent recurrence

#### Runbooks

- `docs/INCIDENT_RESPONSE_RUNBOOK.md` — step-by-step for security incidents
- `docs/DISASTER_RECOVERY_RUNBOOK.md` — DR procedures
- `docs/SECURITY_OPERATIONS_MANUAL.md` — SecOps playbook

## Environment Variables Reference

### Required (Production)

| Variable | Description |
|----------|-------------|
| `JWT_SECRET_KEY` | 32+ char secret for JWT signing |
| `ENCRYPTION_KEY` | Fernet key for at-rest encryption |
| `DATABASE_URL` | PostgreSQL connection string (Supabase session-mode pooler) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (server-side only) |
| `HF_TOKEN` | Hugging Face token (for Space sync) |
| `VERCEL_TOKEN` | Vercel deployment token |
| `VERCEL_ORG_ID` | Vercel org ID |
| `VERCEL_PROJECT_ID` | Vercel project ID |

### Optional (LLM providers — at least one required)

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `GOOGLE_API_KEY` | Google Gemini API key |
| `NVIDIA_API_KEY` | NVIDIA NIM API key |

### Optional (Observability)

| Variable | Description |
|----------|-------------|
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `LANGWATCH_API_KEY` | LangWatch API key |
| `SMITHERY_API_KEY` | Smithery MCP API key |

### Optional (Infrastructure)

| Variable | Description |
|----------|-------------|
| `NEO4J_URI` | Neo4j connection URI |
| `NEO4J_PASSWORD` | Neo4j password |
| `REDIS_URL` | Redis connection URL |
| `QDRANT_HOST` | Qdrant vector DB host |
| `QDRANT_API_KEY` | Qdrant API key |

## Generating Strong Secrets

```bash
# JWT secret (32+ chars, hex)
python -c "import secrets; print(secrets.token_hex(32))"

# Fernet encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Postgres password
openssl rand -base64 24

# Redis password
openssl rand -base64 24
```
