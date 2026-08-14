# ETAP Configuration Guide

## Environment Variables

All configuration is handled through environment variables. Copy `.env.example` to `.env` and customize.

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `API_KEY` | API key for authentication. Required in production. | `sk-...your-key...` |
| `EVIDENCE_HMAC_KEY` | HMAC-SHA256 key for audit log integrity. Must be cryptographically generated. | `openssl rand -hex 32` |
| `APP_ENV` | Environment mode. `production` or `development`. | `production` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_PATH` | Override audit database path | `data/audit.db` |
| `LOG_LEVEL` | Logging verbosity | `WARNING` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins | — |
| `MEMORY_LLM_PROVIDER` | LLM provider for memory service | `gemini` |
| `MEMORY_LLM_MODEL` | LLM model for memory service | `gemini-2.0-flash` |
| `GEMINI_API_KEY` | Gemini API key for optional AI features | — |
| `PDF_MAX_FILE_SIZE_BYTES` | Max PDF file size | `52428800` |
| `DWG_MAX_FILE_SIZE_BYTES` | Max DWG file size | `52428800` |
| `IMAGE_MAX_FILE_SIZE_BYTES` | Max image file size | `10485760` |

## Production Configuration

### Security Requirements

1. **API Key**: Generate with `openssl rand -hex 32`. Never use dev keys.
2. **HMAC Key**: Generate with `openssl rand -hex 32`. Dev fallback is blocked in production.
3. **CORS**: Wildcards (`*`) are ALWAYS rejected in production. Specify explicit origins.
4. **Secrets**: Use a secrets manager (Vault, AWS Secrets, etc.) — NOT `.env` files.

### Docker Configuration

```yaml
# docker-compose.yml requires:
API_KEY: ${API_KEY:?ERROR: must be set}
EVIDENCE_HMAC_KEY: ${EVIDENCE_HMAC_KEY:?ERROR: must be set}
```

The container runs as non-root `etap` user with read-only filesystem and tmpfs for `/tmp`.

## Development Configuration

Set `APP_ENV=development` to relax certain security checks:
- CORS wildcards allowed (for local development only)
- HMAC key defaults to dev key (WARNING: not for production)
- Debug logging enabled