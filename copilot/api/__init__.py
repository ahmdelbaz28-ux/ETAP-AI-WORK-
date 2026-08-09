"""FastAPI Backend — Engineering Copilot REST API."""

from copilot.api.routes import CopilotAPI, create_app

__all__ = [
    "CopilotAPI",
    "create_app",
]
