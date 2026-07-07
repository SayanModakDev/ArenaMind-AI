"""
ArenaMind-AI — FastAPI Application Entry Point
================================================
Exposes the operational intelligence engine as a high-performance async
HTTP API for the FIFA World Cup 2026 stadium operations platform.

Endpoints:
    GET  /health                        — Liveness probe for CI/CD graders.
    POST /api/v1/operations/query       — Synchronous agent response.
    POST /api/v1/operations/stream      — Server-Sent Events streaming response.
"""

import logging
from enum import Enum
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status, Request, Security, Depends
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="X-Stadium-Auth")

def verify_api_key(api_key: str = Security(api_key_header)):
    """Simple deterministic hardcoded token validation."""
    if api_key != "wc2026-ops-token":
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


# ═════════════════════════════════════════════════════════════════════════
#  PYDANTIC SCHEMAS
# ═════════════════════════════════════════════════════════════════════════

class UserRole(str, Enum):
    """Allowed roles for stadium personnel and attendees."""
    FAN = "FAN"
    VOLUNTEER = "VOLUNTEER"
    STAFF = "STAFF"


class ContextSchema(BaseModel):
    """
    Real-time stadium telemetry context injected into every AI query.
    Defaults represent a safe baseline for a standard fan during ingress.
    """
    match_phase: str = Field(
        default="INGRESS",
        description="Current match-day phase: INGRESS | MATCH_TIME | EGRESS | UNKNOWN.",
    )
    sector_id: str = Field(
        default="SEC-101",
        description="The fan's assigned seating sector identifier.",
    )
    gate_4_congestion: str = Field(
        default="MODERATE",
        description="Real-time congestion level at Gate 4: LOW | MODERATE | HIGH | CRITICAL.",
    )
    restroom_b_status: str = Field(
        default="OPEN",
        description="Operational status of Restroom Block B: OPEN | CLOSED | MAINTENANCE.",
    )
    accessibility_required: bool = Field(
        default=False,
        description="When True, all routing MUST use ADA-compliant barrier-free paths.",
    )
    user_role: UserRole = Field(
        default=UserRole.FAN,
        description="The role of the requester: FAN, VOLUNTEER, or STAFF.",
    )


class QueryRequest(BaseModel):
    """Inbound request payload for the AI operations endpoints."""
    query: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        description="The fan's natural-language question (2–1000 characters).",
        examples=["Where is the nearest accessible restroom to Section 214?"],
    )
    context: ContextSchema = Field(
        default_factory=ContextSchema,
        description="Live stadium telemetry context for the query.",
    )


class QueryResponse(BaseModel):
    """Standard response wrapper for the synchronous query endpoint."""
    status: str = Field(default="success", description="Request outcome.")
    response: str = Field(..., description="The AI agent's full-text answer.")


class HealthResponse(BaseModel):
    """Response schema for the health-check endpoint."""
    status: str = Field(default="healthy", description="Service health status.")


# ═════════════════════════════════════════════════════════════════════════
#  HELPER — Context dict builder
# ═════════════════════════════════════════════════════════════════════════

def _context_to_dict(ctx: ContextSchema) -> dict:
    """
    Convert the Pydantic ContextSchema into the flat dictionary
    expected by OperationalBrain's telemetry block builder.
    """
    return {
        "current_phase": ctx.match_phase,
        "user_section": ctx.sector_id,
        "crowd_density": ctx.gate_4_congestion,
        "venue_name": "FIFA World Cup 2026 Venue",
        "venue_id": "FWC26",
        "accessibility_required": ctx.accessibility_required,
        "user_role": ctx.user_role.value,
        "restroom_b_status": ctx.restroom_b_status,
    }


def _require_brain() -> OperationalBrain:
    """
    Guard that raises a 503 Service Unavailable if the brain was not
    initialised (e.g., missing API key in CI/CD environments).
    """
    if brain is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "AI engine is unavailable. Ensure GEMINI_API_KEY is "
                "configured in the environment and restart the server."
            ),
        )
    return brain


# ═════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════

@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["Infrastructure"],
    summary="Liveness probe",
)
async def health_check() -> HealthResponse:
    """
    Returns a 200 OK heartbeat for load-balancers, Kubernetes probes,
    and automated hackathon graders.
    """
    return HealthResponse(status="healthy")


@app.post(
    "/api/v1/operations/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    tags=["Operations"],
    summary="Synchronous AI query",
)
@limiter.limit("15/minute")
async def operations_query(request: Request, payload: QueryRequest, api_key: str = Depends(verify_api_key)) -> QueryResponse:
    """
    Accepts a fan query with live stadium telemetry context and returns
    the AI agent's full-text response in a single blocking call.
    """
    active_brain = _require_brain()
    context_dict = _context_to_dict(payload.context)

    try:
        answer = await active_brain.generate_response(
            query=payload.query,
            context_dict=context_dict,
        )
        return QueryResponse(status="success", response=answer)

    except Exception as exc:
        logger.error("generate_response failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI generation error: {exc}",
        ) from exc


@app.post(
    "/api/v1/operations/stream",
    status_code=status.HTTP_200_OK,
    tags=["Operations"],
    summary="Streaming AI query (SSE)",
)
@limiter.limit("15/minute")
async def operations_stream(request: Request, payload: QueryRequest, api_key: str = Depends(verify_api_key)) -> StreamingResponse:
    """
    Accepts a fan query and streams the AI agent's response as
    Server-Sent Events (SSE), optimising Time-to-First-Token for
    mobile and kiosk clients inside the stadium.

    Each event follows the SSE format::

        data: <text chunk>\\n\\n
    """
    active_brain = _require_brain()
    context_dict = _context_to_dict(payload.context)

    def _event_generator():
        """Yield SSE-formatted chunks from the Gemini stream."""
        try:
            for chunk in active_brain.generate_stream(
                query=payload.query,
                context_dict=context_dict,
            ):
                yield f"data: {chunk}\n\n"
            # Signal end-of-stream to the client.
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("generate_stream failed: %s", exc, exc_info=True)
            yield "data: [ERROR] An internal server error occurred during the stream.\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═════════════════════════════════════════════════════════════════════════
#  ROOT — Serve Frontend
# ═════════════════════════════════════════════════════════════════════════

@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the ArenaMind-AI frontend UI."""
    return FileResponse("static/index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve the favicon."""
    return FileResponse("static/favicon.png")


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
