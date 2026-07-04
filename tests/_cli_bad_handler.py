"""Helper module for CLI tests — contains a handler class requiring constructor args.

This module is loaded by ``_load_handlers("tests._cli_bad_handler")`` in
``acp_runtime/acp_tests/test_cli.py`` to verify that the CLI surfaces a clear
error when a handler class cannot be instantiated with no arguments.

Must define a ``BadHandler`` class with a required constructor argument and at
least one ``@capability`` method so that ``discover_capabilities`` finds it.
"""

from __future__ import annotations

from acp.runtime import capability


class BadHandler:
    def __init__(self, required_arg: int) -> None:
        self.required_arg = required_arg

    @capability("bad.cap", scopes=())
    async def run(self) -> None:
        """Intentional no-op.

        This handler exists only to verify that the CLI surfaces a clear
        error when a handler class cannot be instantiated with no
        arguments (``required_arg`` has no default). The body never
        executes because construction fails first.
        """
