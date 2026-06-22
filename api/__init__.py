from .agents import router as agents_router
from .ai_ml import router as ai_ml_router
from .auth import router as auth_router
from .digital_twin import router as digital_twin_router
from .health import router as health_router
from .mfa import router as mfa_router
from .projects import router as projects_router
from .scada import router as scada_router
from .studies import router as studies_router
from .validation import router as validation_router

__all__ = [
    "auth_router",
    "projects_router",
    "studies_router",
    "health_router",
    "validation_router",
    "ai_ml_router",
    "scada_router",
    "digital_twin_router",
    "mfa_router",
    "agents_router"
]
