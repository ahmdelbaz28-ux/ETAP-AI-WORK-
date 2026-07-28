# Security Fixes Implementation Plan

## Issue 1: Production Secrets Leaked in Original Message ⚠️ CRITICAL
**Status**: CRITICAL - Must rotate ALL secrets immediately
**Action**: All 20+ production secrets (GitHub PAT, HuggingFace token, Vercel token, Neo4j password, Supabase keys, Langfuse keys, Daytona token, Codesandbox token) must be rotated immediately at their respective providers. This is an operational task, not a code fix.

## Issue 2: JWT Secret Weak/Fallback — api/dependencies.py:32-56
**Status**: VERIFIED - REAL ISSUE
**Problem**: Fallback generates guessable key from hostname. `.env.example` has known placeholder.
**Fix**: 
- Remove fallback entirely in production/staging
- Require JWT_SECRET_KEY in production
- Generate strong random default for dev only

## Issue 3: Reset Token Leak in API Response — api/auth.py:988-992
**Status**: VERIFIED - REAL ISSUE
**Problem**: Default returns reset_token in HTTP response body. Any proxy/APM/browser extension can capture it.
**Fix**: 
- Default AUTH_RETURN_RESET_TOKEN=false
- Only return token in development with explicit opt-in

## Issue 4: Token Blacklist Disabled Without Redis — api/auth.py:129-157
**Status**: VERIFIED - REAL ISSUE
**Problem**: `_blacklist_token` silently returns when Redis unavailable. Logout doesn't invalidate refresh tokens on HF Space.
**Fix**: 
- Implement in-memory fallback with warning log
- Add in-memory token blacklist with TTL cleanup

## Issue 5: Rate Limiting Weak Without Redis — api/auth.py:467-510
**Status**: VERIFIED - REAL ISSUE
**Problem**: In-memory fallback doesn't work across replicas. 5 replicas = 5x rate limit.
**Fix**: 
- Implement distributed rate limiting with Redis
- Add in-memory fallback with replica-aware limits (divide by replica count)
- Add warning when Redis unavailable

## Issue 6: CUA Loop Without Timeout — hf-space/app.py:669-677
**Status**: VERIFIED - REAL ISSUE
**Problem**: No `asyncio.wait_for()` timeout. Hung CUA task can exhaust thread pool.
**Fix**: 
- Add `asyncio.wait_for()` with configurable timeout (default 5 minutes)
- Add proper timeout handling and cleanup

## Issue 7: SQLite Fallback = Silent Data Loss — api/database.py
**Status**: VERIFIED - REAL ISSUE
**Problem**: Auto-fallback to SQLite in /tmp on HF Space. /tmp wiped on restart = total data loss.
**Fix**: 
- Remove silent fallback
- Fail fast with clear error if PostgreSQL unavailable
- Require explicit opt-in for SQLite in production

## Issue 8: Weak API Key Obfuscation in Frontend — ui/src/lib/api-config.ts:83
**Status**: VERIFIED - REAL ISSUE
**Problem**: XOR with static key "ETAP-SEC-2024-OBFUSCATION" in JS bundle. Not encryption - trivially reversible.
**Fix**: 
- Remove client-side "encryption" entirely
- Store API keys only in backend (encrypted with Fernet)
- Frontend sends key ID, backend resolves to actual key

## Issue 9: JWT Bypass in verify_api_key — api/shared_handlers.py:361-375
**Status**: VERIFIED - REAL ISSUE
**Problem**: Any "Bearer " string bypasses API key check. No JWT validation.
**Fix**: 
- Validate JWT signature and claims in verify_api_key
- Or remove bypass entirely, require valid API key

## Issue 10: Memory Leak in _LOGIN_ATTEMPTS — api/auth.py:84
**Status**: VERIFIED - REAL ISSUE
**Problem**: Global dict `_LOGIN_ATTEMPTS` never cleaned up. Grows unbounded.
**Fix**: 
- Add TTL-based cleanup
- Use LRU cache with max size
- Or use Redis with TTL

## Issue 11: Subprocess with PowerShell -Command — security/secure_powershell_executor.py:88-101
**Status**: VERIFIED - REAL ISSUE
**Problem**: `-Command` with raw string allows obfuscation bypass. Regex validator is brittle.
**Fix**: 
- Use `-File` with temp script file instead of `-Command`
- Or implement constrained runspace / whitelisted cmdlets
- Add stricter AST validation

## Issue 12: Agents etap_expert/etap_gui Fail Silently — api/shared_handlers.py:651-678
**Status**: VERIFIED - REAL ISSUE
**Problem**: Generic 500 error on import failures. No fallback. etap_gui needs Gemini Vision key.
**Fix**: 
- Add graceful degradation with clear error messages
- Check dependencies at startup
- Return structured error with actionable guidance