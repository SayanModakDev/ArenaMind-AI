"""
ArenaMind-AI — Shared Dependencies
====================================
Provides authentication, rate-limiting, and brain-access
dependencies used by route handlers. Lives outside main.py
to break the circular import between main ↔ api.routes.
"""

from schemas import UserRole
from fastapi import HTTPException, Security, Request, status
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

from agents.operational_brain import OperationalBrain
from config import settings

# ── Authentication ──────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-Stadium-Auth", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> UserRole:
    """Validate the X-Stadium-Auth header against the configured tokens."""
    if api_key:
        if api_key == settings.FAN_AUTH_TOKEN:
            return UserRole.FAN
        elif api_key == settings.VOLUNTEER_AUTH_TOKEN:
            return UserRole.VOLUNTEER
        elif api_key == settings.STAFF_AUTH_TOKEN:
            return UserRole.STAFF
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing X-Stadium-Auth token",
    )


# ── Rate Limiting ───────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Brain Access ────────────────────────────────────────────────────────
def require_brain(request: Request) -> OperationalBrain:
    """
    FastAPI dependency that retrieves the OperationalBrain singleton
    from ``app.state.brain``. Raises 503 if the brain failed to
    initialise (e.g. missing GEMINI_API_KEY).
    """
    brain = getattr(request.app.state, "brain", None)
    if brain is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "AI engine is unavailable. Ensure GEMINI_API_KEY is "
                "configured in the environment and restart the server."
            ),
        )
    return brain
