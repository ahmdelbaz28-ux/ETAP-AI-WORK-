# ACP Runtime Engine (Phase B)

Standalone Python 3.12+ implementation of the **Agent Communication Protocol** runtime layer.

This package contains the `acp.runtime` engine: capability discovery, async execution via `anyio`, deadline enforcement, cancellation propagation, and exception-to-error mapping. It is transport-agnostic and depends only on `anyio` and `pydantic`.

## Layout

```
acp_runtime/
├── pyproject.toml
├── acp/
│   ├── __init__.py            # public API
│   ├── errors.py              # AcpError hierarchy
│   ├── schema/                # pydantic v2 models
│   │   ├── capability.py
│   │   └── ids.py
│   └── runtime/               # ← Phase B
│       ├── handler.py         # @capability decorator + discovery
│       ├── deadline.py        # enforce_deadline_ms
│       ├── cancel.py          # cancellation helpers
│       ├── engine.py          # AcpRuntime (main engine)
│       └── progress.py        # ProgressEmitter
└── tests/
    ├── conftest.py
    ├── test_deadline.py       # timeout behavior
    ├── test_handler.py        # decorator + discovery
    ├── test_engine.py         # full engine integration
    └── test_cancellation.py   # cancellation propagation
```

## Install + run tests

```bash
cd acp_runtime
pip install -e ".[test]"
pytest -v
```

## Quick example

```python
import anyio
from acp.runtime import AcpRuntime, capability

class MathHandler:
    @capability("math.sum", scopes=("math.read",))
    async def sum(self, a: int, b: int) -> int:
        await anyio.sleep(0.001)
        return a + b

async def main():
    runtime = AcpRuntime([MathHandler()])
    result = await runtime.execute("math.sum", {"a": 1, "b": 2}, deadline_ms=1000)
    assert result == 3

anyio.run(main)
```
