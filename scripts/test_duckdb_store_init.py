"""
DuckDBStore initialization smoke test.

Expected:
- Import DuckDBStore successfully
- Instantiate it without errors
- Verify it is accessible (basic attribute/method presence)

Usage:
  python scripts/test_duckdb_store_init.py

Optional env vars:
  DUCKDBSTORE_IMPORT_PATH  - explicit import path to DuckDBStore, e.g.
                               "some_package.some_module:DuckDBStore"
  DUCKDBSTORE_DB_PATH      - database path passed to constructor if supported
  DUCKDBSTORE_CONSTRUCTOR_KWARGS_JSON - JSON string of extra constructor kwargs.

The script uses a small set of common fallback import paths if DUCKDBSTORE_IMPORT_PATH
is not provided.
"""

from __future__ import annotations

import importlib
import json
import os
import traceback
from typing import Any, Optional, Tuple


def _parse_import_path(spec: str) -> Tuple[str, str]:
    """
    Supports:
      "pkg.mod:DuckDBStore"
      "pkg.mod.DuckDBStore"   (last segment treated as symbol)
    """
    if ":" in spec:
        mod_path, sym = spec.split(":", 1)
        return mod_path, sym
    # dot notation
    parts = spec.strip().split(".")
    if len(parts) < 2:
        raise ValueError(f"Invalid import spec: {spec}")
    mod_path = ".".join(parts[:-1])
    sym = parts[-1]
    return mod_path, sym


def _try_import(import_path: str) -> Any:
    mod_path, sym = _parse_import_path(import_path)
    mod = importlib.import_module(mod_path)
    return getattr(mod, sym)


def _instantiate(cls: Any) -> Any:
    db_path = os.environ.get("DUCKDBSTORE_DB_PATH", "./duckdb_store_test.db")
    extra_kwargs_json = os.environ.get("DUCKDBSTORE_CONSTRUCTOR_KWARGS_JSON", "").strip()
    extra_kwargs = json.loads(extra_kwargs_json) if extra_kwargs_json else {}

    # Try common constructor signatures:
    #   DuckDBStore(db_path=...)
    #   DuckDBStore(path=...)
    #   DuckDBStore("./file.db")
    #   DuckDBStore()
    try:
        return cls(db_path=db_path, **extra_kwargs)
    except TypeError:
        pass

    try:
        return cls(path=db_path, **extra_kwargs)
    except TypeError:
        pass

    try:
        return cls(db_path, **extra_kwargs)
    except TypeError:
        pass

    return cls(**extra_kwargs)


def main() -> int:
    candidates = []

    explicit = os.environ.get("DUCKDBSTORE_IMPORT_PATH", "").strip()
    if explicit:
        candidates.append(explicit)

    # Fallback guesses (may or may not match your repo).
    # This is only a smoke test runner; prefer providing DUCKDBSTORE_IMPORT_PATH.
    candidates.extend(
        [
            "duckdb_store:DuckDBStore",
            "duckdb_store:DuckDBStorage",
            "core.duckdb_store:DuckDBStore",
            "core.stores.duckdb_store:DuckDBStore",
            "storage.duckdb_store:DuckDBStore",
            "storage.stores.duckdb_store:DuckDBStore",
            "stores.duckdb_store:DuckDBStore",
            "persistence.duckdb_store:DuckDBStore",
        ]
    )

    last_err: Optional[BaseException] = None

    for spec in candidates:
        try:
            DuckDBStore = _try_import(spec)
            store = _instantiate(DuckDBStore)

            # Accessibility checks: accept any of these, depending on implementation.
            ok = False
            for attr in ("connect", "ping", "health_check", "is_connected", "get_connection"):
                if hasattr(store, attr):
                    ok = True
                    break

            # If no known health method exists, still ensure store instance exists.
            print(
                json.dumps(
                    {
                        "success": True,
                        "import_spec": spec,
                        "store_type": getattr(DuckDBStore, "__name__", str(DuckDBStore)),
                        "store_repr": repr(store)[:500],
                        "accessibility_checked": ok,
                        "error": None,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        except Exception as e:
            last_err = e

    print(
        json.dumps(
            {
                "success": False,
                "error": "Failed to import/instantiate DuckDBStore from all candidates.",
                "last_error": str(last_err) if last_err else None,
                "traceback": traceback.format_exc(),
            },
            ensure_ascii=False,
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
