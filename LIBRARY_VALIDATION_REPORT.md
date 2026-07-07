# Library Validation Report - ETAP AI Platform

## Executive Summary

This report validates the libraries used in the ETAP AI platform and identifies deprecated APIs and migration paths. The platform uses a variety of modern Python and JavaScript libraries for AI, engineering computations, and system integration.

## Python Libraries

### FastAPI (v0.111.0)
- **Status**: Validated
- **Deprecated APIs**: 
  - `pydantic.v1` support is deprecated and will be removed in future versions
  - FastAPI 0.128.0 drops support for `pydantic.v1` entirely
- **Migration Path**: Migrate all Pydantic v1 models to v2 equivalents
- **Recommendation**: Update to newer version to prepare for Pydantic v2-only support

### Pydantic (v2.7.4)
- **Status**: Validated
- **Deprecated APIs**:
  - `BaseModel.schema_json()` method is deprecated (v2.0+)
  - Use `model_json_schema()` combined with `json.dumps()` instead
  - Various Pydantic v1 compatibility functions are deprecated
- **Migration Path**: Replace `schema_json()` with `model_json_schema()` and `json.dumps()`

### NumPy (v1.26.4)
- **Status**: Validated
- **Deprecated APIs**:
  - `fastCopyAndTranspose` and `PyArray_CopyAndTranspose` are deprecated (1.24+)
  - Use `.T.copy()` method directly
- **Timeline**: According to NumPy's deprecation policy, NumPy 1.26 will reach end-of-support around September 2025
- **Recommendation**: Plan upgrade to NumPy 2.x series

### Pandas (v2.2.2)
- **Status**: Validated
- **Deprecated APIs**:
  - `.ix[]` indexer raises `FutureWarning`
  - Timedelta units 'M' and 'Y' are deprecated in `to_timedelta`, `Timedelta`, and `TimedeltaIndex`
  - Various legacy methods from pre-2.0 era
- **Migration Path**: Use `.loc[]` or `.iloc[]` instead of `.ix[]`, use alternative timedelta units

### SQLAlchemy (v2.0.30)
- **Status**: Validated
- **Deprecated APIs**:
  - `Engine.execute()` is deprecated (replaced by `Connection.execute()` or `Session.execute()`)
  - Passing string to `Connection.execute()` is deprecated (use `text()` construct)
  - Legacy autocommit behavior removed
  - Legacy calling style of `select()` is deprecated
- **Migration Path**: Update all database calls to use SQLAlchemy 2.0 patterns

### Redis-py (v5.0.7)
- **Status**: Validated
- **Deprecated APIs**:
  - Legacy response shapes maintained for backward compatibility
  - `legacy_responses=True` maintains backward compatibility but is transitional
- **Migration Path**: Set `legacy_responses=False` for unified response types regardless of wire protocol (RESP2/RESP3)

### Celery (v5.4.0)
- **Status**: Validated
- **Deprecated APIs**:
  - `celery.decorators` and `celery.task` modules removed in v5.0
  - Use `celery.shared_task` instead of `celery.task` decorator
  - `celery.Task` should be imported directly from `celery`
- **Migration Path**: Update imports from `celery.decorators` and `celery.task` to direct imports from `celery`

### OpenTelemetry (v1.30.0)
- **Status**: Validated
- **Deprecated APIs**:
  - Various internal API changes in importlib.metadata handling for Python 3.10+
  - Deprecation warnings for internal SelectableGroups usage
- **Migration Path**: Follow SemVer guidelines for upgrades

### LangChain (v0.2.11)
- **Status**: Validated but with significant changes
- **Major Changes**:
  - As of October 2024, LangGraph is now preferred for complex AI applications
  - Most existing LangChain chains and agents are deprecated
  - Migration guidance provided to LangGraph
- **Migration Path**: Consider migrating complex applications to LangGraph or use `langchain-classic` for legacy support

### ChromaDB (v0.5.3)
- **Status**: Validated
- **Notes**: No specific deprecated API information found in current documentation

### Cryptography (v42.0.8)
- **Status**: Validated
- **Deprecated APIs**:
  - Support for `verifier` and `signer` methods deprecated (since v2.0)
  - Use `sign` and `verify` methods instead for asymmetric key operations
  - Various cryptographic primitives moved to `/hazmat/decrepit/index` module
  - Algorithms like CAST5, SEED, IDEA, Blowfish, TripleDES, and ARC4 have been moved to deprecated module
- **Migration Path**: Migrate from `verifier`/`signer` to `sign`/`verify` methods

### SciPy (v1.13.1)
- **Status**: Validated
- **Deprecated APIs**:
  - `scipy.linalg.interpolative.rand` and `scipy.linalg.interpolative.seed` (scheduled for removal in v1.17.0)
  - Complex inputs to `scipy.spatial.cosine` and `scipy.spatial.correlation` (will raise error in v1.17.0)
  - `scipy.stats.find_repeats` deprecated (use `numpy.unique`/`numpy.unique_counts` instead)
  - `scipy.linalg.kron` deprecated in favor of `numpy.kron`
  - Multiple deprecated features scheduled for removal in v1.17.0 and beyond
- **Migration Path**: Replace deprecated functions with recommended alternatives

### Matplotlib (v3.9.0)
- **Status**: Validated
- **Deprecated APIs**:
  - Standardized deprecation warning system using `warn_deprecated` function
  - Parameter deprecation handled with `delete_parameter` decorator
  - Various API elements subject to deprecation following standard procedure
- **Migration Path**: Monitor deprecation warnings and update code accordingly

### Requests (v2.32.4)
- **Status**: Validated
- **Deprecated APIs**:
  - `get_connection` method deprecated and renamed to `_get_connection` to `get_connection_with_tls_context` (v2.32.2)
  - Functions in `requests.utils` marked for removal in version 3.0
  - Sessions used by functional API are now always closed
  - Restricted to HTTP/1.1 and HTTP/1.0 (no longer accepts HTTP/0.9)
- **Migration Path**: Update custom HTTPAdapters to use new connection methods

## JavaScript/Node.js Libraries

### Mastra Framework
- **Status**: Validated
- **Version**: 1.37.1 (core)
- **Notes**: Modern framework for AI engineering platform

### AI SDK
- **Status**: Validated
- **Components**: Anthropic integration, core AI functions
- **Version**: ai@6.0.209

## Security Considerations

Based on the pyproject.toml file, the project already addresses several security vulnerabilities:
- Requests: Updated to address CVE-2024-35195, CVE-2024-47081
- Cryptography: Updated to address 9 CVEs (CVE-2023-50782, CVE-2024-0727, GHSA-537c-gmf6-5ccf)
- PyPDF2 replaced with pypdf to address 30 CVEs
- NLTK updated to address 13 CVEs (PYSEC-2024-167 RCE, CVE-2026-33231/33232)
- lxml updated to address PYSEC-2026-87 (XXE)
- Starlette updated to address CVE-2024-47874 (DoS), CVE-2025-54121 (memory leak)

## Recommendations

1. **Immediate Actions**:
   - Audit codebase for Pydantic v1 usage and migrate to v2
   - Update SQLAlchemy calls to 2.0 patterns
   - Replace deprecated Pandas APIs
   - Update cryptography usage from `verifier`/`signer` to `sign`/`verify` methods

2. **Medium-term Actions**:
   - Plan migration to newer NumPy versions (2.x series)
   - Evaluate LangChain migration to LangGraph for complex applications
   - Update FastAPI to newer versions to align with Pydantic v2-only support
   - Replace deprecated SciPy functions with recommended alternatives

3. **Long-term Actions**:
   - Monitor library support timelines (NumPy 1.26 support ends ~Sep 2025)
   - Plan regular library updates to maintain security and compatibility
   - Prepare for Requests 3.0 transition (monitor `requests.utils` deprecations)

## Conclusion

The ETAP AI platform uses well-maintained libraries with active development. While several deprecated APIs exist, they follow standard deprecation policies with clear migration paths. The project maintains good security practices with regular updates addressing known vulnerabilities. Regular monitoring of deprecation warnings and scheduled library updates will ensure continued compatibility and security.