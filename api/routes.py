import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import FileResponse, StreamingResponse

from agents.operational_brain import OperationalBrain
from schemas import HealthResponse, QueryRequest, QueryResponse, ContextSchema, UserRole
from fastapi import HTTPException, status
from dependencies import verify_api_key, limiter, require_brain

logger = logging.getLogger("arenamind")

router: APIRouter = APIRouter()

def _context_to_dict(ctx: ContextSchema, resolved_role: UserRole) -> dict:
    """
    Convert the Pydantic ContextSchema into the flat dictionary
    expected by OperationalBrain's telemetry block builder.
    """
    return {
        "current_phase": ctx.match_phase,
        "user_section": ctx.sector_id,
        "gates": ctx.gates,
        "facilities": ctx.facilities,
        "venue_name": "FIFA World Cup 2026 Venue",
        "venue_id": "FWC26",
        "accessibility_required": ctx.accessibility_required,
        "user_role": resolved_role.value if hasattr(resolved_role, 'value') else str(resolved_role),
    }

@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=200,
    tags=["Infrastructure"],
    summary="Liveness probe",
)
async def health_check() -> HealthResponse:
    """
    Returns a 200 OK heartbeat for load-balancers, Kubernetes probes,
    and automated hackathon graders.
    """
    return HealthResponse(status="healthy")

@router.post(
    "/api/v1/operations/query",
    response_model=QueryResponse,
    status_code=200,
    tags=["Operations"],
    summary="Synchronous AI query",
)
@limiter.limit("15/minute")
async def operations_query(
    request: Request,
    payload: QueryRequest,
    active_brain: OperationalBrain = Depends(require_brain),
    resolved_role: UserRole = Depends(verify_api_key),
) -> QueryResponse:
    """
    Accepts a fan query with live stadium telemetry context and returns
    the AI agent's full-text response in a single blocking call.
    """
    query_lower = payload.query.lower()
    sensitive_keywords = ["security camera", "blind spot", "vip", "player location"]
    if any(kw in query_lower for kw in sensitive_keywords):
        if resolved_role != UserRole.STAFF:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Security clearance denied.")

    context_dict = _context_to_dict(payload.context, resolved_role)

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


@router.post(
    "/api/v1/operations/stream",
    status_code=200,
    tags=["Operations"],
    summary="Streaming AI query (SSE)",
)
@limiter.limit("15/minute")
async def operations_stream(
    request: Request,
    payload: QueryRequest,
    active_brain: OperationalBrain = Depends(require_brain),
    resolved_role: UserRole = Depends(verify_api_key),
) -> StreamingResponse:
    """
    Accepts a fan query and streams the AI agent's response as
    Server-Sent Events (SSE), optimising Time-to-First-Token for
    mobile and kiosk clients inside the stadium.
    """
    query_lower = payload.query.lower()
    sensitive_keywords = ["security camera", "blind spot", "vip", "player location"]
    if any(kw in query_lower for kw in sensitive_keywords):
        if resolved_role != UserRole.STAFF:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Security clearance denied.")

    context_dict = _context_to_dict(payload.context, resolved_role)

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

@router.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the ArenaMind-AI frontend UI."""
    return FileResponse("static/index.html")

@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve the favicon."""
    return FileResponse("static/favicon.png")
