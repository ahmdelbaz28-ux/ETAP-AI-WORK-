"""Real handler module for integration / end-to-end tests.

Provides capabilities covering:
    * Simple arithmetic (math.sum, math.multiply, math.divide)
    * Public echo (public.echo)
    * Admin-only stats (admin.stats)
    * Progress-emitting long operation (math.progress)
    * Error-raising capability (error.raise)
"""
from __future__ import annotations

import anyio

from acp.runtime import capability, ProgressEmitter


class IntegrationHandler:
    """Handler used by the integration test suite."""

    @capability("math.sum", scopes=("math.read",))
    async def sum(self, a: int, b: int) -> int:
        return a + b

    @capability("math.multiply", scopes=("math.read", "math.write"))
    async def multiply(self, a: int, b: int) -> int:
        return a * b

    @capability("math.divide", scopes=("math.read",))
    async def divide(self, a: float, b: float) -> float:
        if b == 0:
            raise ValueError("Division by zero")
        return a / b

    @capability("math.progress", scopes=("math.read",))
    async def progress(self, steps: int = 5, emitter: ProgressEmitter | None = None) -> str:
        """Emit progress events and return a completion message."""
        if emitter is None:
            return "done"
        for i in range(1, steps + 1):
            await emitter.emit(i, steps, f"step {i}/{steps}")
            await anyio.sleep(0.001)
        return "complete"

    @capability("public.echo")
    async def echo(self, message: str) -> str:
        return message

    @capability("admin.stats", scopes=("admin",))
    async def stats(self) -> dict:
        return {"status": "ok", "version": "1.0.0"}

    @capability("error.raise", scopes=("math.read",))
    async def raise_error(self, message: str = "boom") -> None:
        raise RuntimeError(message)
