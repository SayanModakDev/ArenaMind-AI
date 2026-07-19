from enum import Enum
from pydantic import BaseModel, Field

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
