"""
ArenaMind-AI — FastAPI Application Entry Point
================================================
Exposes the operational intelligence engine as a high-performance async
HTTP API for the FIFA World Cup 2026 stadium operations platform.
"""

import logging
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status, Request, Security
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

from agents.operational_brain import OperationalBrain
from config import settings

# ── Environment & Logging ───────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("arenamind")

# ── FastAPI Application ─────────────────────────────────────────────────
app = FastAPI(
    title="ArenaMind-AI",
    description=(
        "Operational Intelligence Engine for the FIFA World Cup 2026. "
        "Provides real-time, AI-powered stadium operations guidance "
        "including wayfinding, accessibility routing, crowd-flow "
        "optimisation, and multilingual fan assistance."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_and_audit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"AUDIT | Method: {request.method} | URL: {request.url.path} | IP: {client_ip}")
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

api_key_header = APIKeyHeader(name="X-Stadium-Auth")

def verify_api_key(api_key: str = Security(api_key_header)):
    """Simple deterministic hardcoded token validation."""
    if api_key != settings.STADIUM_AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Stadium-Auth token",
        )
    return api_key

# ── Static Files ────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# ── Brain Instantiation (fail-safe) ────────────────────────────────────
# Wrapped in a try/except so the server can still boot in CI/CD
# environments where GEMINI_API_KEY may not be configured. Endpoints
# that require the brain will return a clear 503 when it is unavailable.
brain: Optional[OperationalBrain] = None

try:
    brain = OperationalBrain()
    logger.info("OperationalBrain initialised successfully.")
except Exception as exc:
    logger.warning(
        "OperationalBrain failed to initialise — AI endpoints will "
        "return 503 until resolved. Error: %s",
        exc,
    )

# ── Routers ─────────────────────────────────────────────────────────────
from api.routes import router  # noqa: E402
app.include_router(router)

# ═════════════════════════════════════════════════════════════════════════
#  MAIN EXECUTION
# ═════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info",
    )
