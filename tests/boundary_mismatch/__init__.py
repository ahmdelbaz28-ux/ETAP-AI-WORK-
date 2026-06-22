"""Boundary mismatch tests — detect API ↔ frontend type drift.

Inspired by harness's QA agent guide (6 boundary mismatch patterns).
These tests catch bugs that TypeScript generics and `npm run build` cannot:
- API response shape vs frontend expected type
- File path vs link href
- State transition completeness
- API endpoint vs frontend hook 1:1 mapping
- Sync vs async response shapes
- snake_case ↔ camelCase consistency
"""
