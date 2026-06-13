"""Helper module for CLI tests — contains a handler class requiring constructor args."""
from acp.runtime import capability


class BadHandler:
    def __init__(self, required_arg: int) -> None:
        self.required_arg = required_arg

    @capability("bad.cap", scopes=())
    async def run(self) -> None:
        pass
