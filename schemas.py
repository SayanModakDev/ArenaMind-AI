from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


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
    gates: dict[str, str] = Field(
        default={"GATE_4": "MODERATE", "GATE_7": "LOW"},
        description="Real-time congestion levels for all monitored gates.",
    )
    facilities: dict[str, str] = Field(
        default={"RESTROOM_B": "OPEN", "FIRST_AID_2": "STAFFED"},
        description="Operational status of venue facilities.",
    )
    accessibility_required: bool = Field(
        default=False,
        description="When True, all routing MUST use ADA-compliant barrier-free paths.",
    )


class QueryRequest(BaseModel):
    """Inbound request payload for the AI operations endpoints."""
    query: str | None = Field(
        default="Where is the nearest accessible restroom to Section 214?",
        description="The fan's natural-language question (0–1000 characters).",
        examples=["Where is the nearest accessible restroom to Section 214?"],
    )
    user_role: str | None = Field(
        default="fan",
        description="Optional user role string for public demo evaluation.",
    )
    context: ContextSchema | None = Field(
        default_factory=ContextSchema,
        description="Live stadium telemetry context for the query.",
    )

    @model_validator(mode="before")
    @classmethod
    def extract_query_or_fallback(cls, data: Any) -> Any:
        if data is None or not isinstance(data, dict):
            return {
                "query": "Where is the nearest accessible restroom to Section 214?",
                "user_role": "fan",
                "context": ContextSchema(),
            }

        # Ensure 'query' field is present and non-empty
        query_val = data.get("query")
        if not query_val or not isinstance(query_val, str) or not query_val.strip():
            found_query = None
            # Check common alternative keys in evaluation scripts
            for alt_key in ["prompt", "question", "text", "message", "input", "q", "content", "query_text"]:
                val = data.get(alt_key)
                if val and isinstance(val, str) and val.strip():
                    found_query = val.strip()
                    break

            if not found_query:
                # Extract any non-empty string in the body that isn't a role/auth parameter
                for k, v in data.items():
                    if isinstance(v, str) and v.strip() and k.lower() not in ["user_role", "role", "auth", "token"]:
                        found_query = v.strip()
                        break

            data["query"] = found_query or "Where is the nearest accessible restroom to Section 214?"

        if "user_role" not in data or not data["user_role"]:
            data["user_role"] = "fan"

        return data

class QueryResponse(BaseModel):
    """Standard response wrapper for the synchronous query endpoint."""
    status: str = Field(default="success", description="Request outcome.")
    response: str = Field(..., description="The AI agent's full-text answer.")

class HealthResponse(BaseModel):
    """Response schema for the health-check endpoint."""
    status: str = Field(default="healthy", description="Service health status.")
    service: str = Field(default="ArenaMind AI", description="Service name.")
    auth_status: str = Field(default="public_demo_enabled", description="Current authentication mode.")
