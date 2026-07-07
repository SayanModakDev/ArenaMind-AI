"""
ArenaMind-AI — Operational Brain
=================================
Core intelligence module powering the stadium operations agent.
Wraps the Google Gemini GenerativeModel with enterprise-grade safety
settings, prompt-injection defences, and real-time telemetry injection
for live FIFA World Cup 2026 venue operations.
"""

import os
import re
import json
import hashlib
from typing import Any, Dict, Generator, Optional
import asyncio

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from async_lru import alru_cache

from prompts.templates import STADIUM_SYSTEM_INSTRUCTION
from exceptions import ModelTimeoutError, ConfigurationError, ArenaMindError
from config import settings


class OperationalBrain:
    """
    Secure, production-ready wrapper around the Gemini GenerativeModel.

    Responsibilities:
        - Load and validate the Gemini API key from the environment.
        - Configure enterprise safety filters (harassment, hate speech,
          sexually explicit content, dangerous content).
        - Sanitise every inbound query against known prompt-injection
          patterns before it reaches the model.
        - Inject structured stadium telemetry (phase, congestion, gate,
          accessibility flags) into every prompt.
        - Expose both blocking (`generate_response`) and streaming
          (`generate_stream`) generation interfaces.
    """

    # ── Prompt-Injection Blocklist ──────────────────────────────────────
    # Compiled once at class level for performance. Each pattern targets
    # a well-known injection vector observed in adversarial LLM research.
    _INJECTION_PATTERNS: re.Pattern = re.compile(
        r"|".join(
            [
                r"ignore\s+(all\s+)?previous\s+instructions",
                r"ignore\s+(all\s+)?prior\s+instructions",
                r"ignore\s+(all\s+)?above\s+instructions",
                r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions",
                r"forget\s+(all\s+)?(previous|prior|above)\s+(instructions|rules|context)",
                r"override\s+(system|safety|security)\s+(prompt|instructions|rules|settings)",
                r"you\s+are\s+now\s+(a|an|in)\s+(unrestricted|jailbreak|developer|admin)",
                r"enter\s+(developer|admin|debug|maintenance)\s+mode",
                r"switch\s+to\s+(developer|admin|unrestricted|unfiltered)\s+mode",
                r"act\s+as\s+(a\s+)?(system\s+)?(admin|administrator|root|superuser)",
                r"pretend\s+(you\s+)?(are|have)\s+no\s+(restrictions|rules|limits|filters)",
                r"reveal\s+(your|the)\s+(system\s+)?(prompt|instructions|configuration|rules)",
                r"show\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions)",
                r"print\s+(your|the)\s+(system\s+)?(prompt|instructions)",
                r"output\s+(your|the)\s+(system\s+)?(prompt|instructions)",
                r"repeat\s+(your|the)\s+(system\s+)?(prompt|instructions)\s+verbatim",
                r"what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions|rules)",
                r"\bDAN\b",
                r"do\s+anything\s+now",
                r"jailbreak",
                r"\[\s*SYSTEM\s*\]",
                r"\[\s*INST\s*\]",
                r"<\s*\|?\s*system\s*\|?\s*>",
                r"###\s*(SYSTEM|INSTRUCTION|OVERRIDE)",
            ]
        ),
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        """
        Initialise the OperationalBrain.

        Raises:
            ValueError: If the ``GEMINI_API_KEY`` environment variable is
                not set or is empty.
        """
        # ── 1. Secure API-Key Loading ───────────────────────────────────
        api_key: str = settings.GEMINI_API_KEY

        if not api_key or not api_key.strip():
            raise ConfigurationError(
                "GEMINI_API_KEY is not set in the environment. "
                "Export it before starting the service: "
                "export GEMINI_API_KEY='your-key-here'"
            )

        genai.configure(api_key=api_key.strip())

        # ── 2. Enterprise Safety Settings ───────────────────────────────
        # Block medium-and-above probability content across all harm
        # categories to enforce a family-friendly, stadium-safe output.
        self._safety_settings: Dict[HarmCategory, HarmBlockThreshold] = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }

        # ── 3. Model Initialisation ─────────────────────────────────────
        # gemini-2.5-flash is the latest free-tier Flash model, chosen
        # for maximum efficiency and its low-latency profile — critical
        # for real-time stadium operations where fans expect sub-second
        # guidance on mobile devices in noisy environments.
        self._model: genai.GenerativeModel = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=STADIUM_SYSTEM_INSTRUCTION,
            safety_settings=self._safety_settings,
        )

    # ── Private Helpers ─────────────────────────────────────────────────

    def _sanitize_input(self, text: str) -> str:
        """
        Screen inbound text for prompt-injection attempts.

        Applies a compiled regex blocklist against the raw user input.
        If a match is found the original text is **replaced entirely**
        with a safe refusal string so the model never sees the
        adversarial payload.

        Args:
            text: Raw user query string.

        Returns:
            The original text if clean, or a standardised refusal
            string if an injection pattern was detected.
        """
        if not isinstance(text, str):
            return ""

        cleaned: str = text.strip()

        if not cleaned:
            return ""

        if self._INJECTION_PATTERNS.search(cleaned):
            return (
                "[BLOCKED] This query was flagged by ArenaMind security. "
                "For security and operational matters, please contact "
                "venue operations staff directly or visit the nearest "
                "Information Desk."
            )

        return cleaned

    @staticmethod
    def _build_telemetry_block(context: Dict[str, Any]) -> str:
        """
        Format the real-time stadium telemetry context into a
        structured text block that is prepended to every user query.

        Args:
            context: Dictionary containing live operational data.
                Expected keys (all optional — missing keys are
                reported as "N/A"):
                    - current_phase (str)
                    - venue_name (str)
                    - venue_id (str)
                    - match_id (str)
                    - user_section (str)
                    - user_gate (str)
                    - crowd_density (str)
                    - accessibility_required (bool)
                    - timestamp_utc (str)

        Returns:
            A formatted multi-line string block.
        """

        def _get(key: str, default: str = "N/A") -> str:
            """Safely retrieve a context value as a display string."""
            value = context.get(key)
            if value is None:
                return default
            if isinstance(value, bool):
                return "YES" if value else "NO"
            return str(value).strip() or default

        return (
            "══════════════ LIVE STADIUM TELEMETRY ══════════════\n"
            f"  Match Phase          : {_get('current_phase')}\n"
            f"  Venue                : {_get('venue_name')} ({_get('venue_id')})\n"
            f"  Match ID             : {_get('match_id')}\n"
            f"  Fan Section          : {_get('user_section')}\n"
            f"  Assigned Gate        : {_get('user_gate')}\n"
            f"  Crowd Density        : {_get('crowd_density')}\n"
            f"  Accessibility Required: {_get('accessibility_required')}\n"
            f"  Timestamp (UTC)      : {_get('timestamp_utc')}\n"
            "═══════════════════════════════════════════════════\n"
        )

    def _build_prompt(self, query: str, context_dict: Dict[str, Any]) -> str:
        """
        Assemble the final prompt from sanitised user input and
        live telemetry data.

        Args:
            query: Raw user query (will be sanitised).
            context_dict: Live stadium telemetry dictionary.

        Returns:
            The fully constructed prompt string ready for the model.
        """
        safe_query: str = self._sanitize_input(query)
        telemetry_block: str = self._build_telemetry_block(context_dict)

        return (
            f"{telemetry_block}\n"
            f"Fan Query:\n"
            f"{safe_query}\n"
        )

    def _enforce_accessibility(self, text: str, context: dict) -> str:
        """Deterministic check for ADA route enforcement."""
        if context.get("accessibility_required"):
            text_lower = text.lower()
            if ("stairs" in text_lower or "escalator" in text_lower) and "elevator" not in text_lower and "ramp" not in text_lower:
                return text + "\n\n[SYSTEM OVERRIDE]: Accessible route strictly required. Please use the nearest elevator."
        return text

    # ── Public API ──────────────────────────────────────────────────────

    @alru_cache(maxsize=200)
    async def _cached_gemini_call(self, hashed_key: str, prompt: str) -> str:
        """Internal cached method for the Gemini generation."""
        try:
            response = await asyncio.wait_for(
                self._model.generate_content_async(prompt, stream=False),
                timeout=8.0
            )
        except asyncio.TimeoutError as exc:
            raise ModelTimeoutError(f"LLM generation timed out after 8.0 seconds: {exc}") from exc

        if not response.parts:
            return (
                "I'm sorry, I wasn't able to generate a response for "
                "that query. Please try rephrasing, or contact venue "
                "staff for assistance."
            )
        return response.text

    async def generate_response(
        self,
        query: str,
        context_dict: Dict[str, Any],
    ) -> str:
        """
        Generate a complete (blocking/cached) response from the Gemini model.

        This method awaits the full response and uses async_lru caching 
        to return instantly for identical queries.

        Args:
            query: The fan's natural-language question or request.
            context_dict: Real-time stadium telemetry dictionary.

        Returns:
            The model's full text response as a single string.
        """
        prompt: str = self._build_prompt(query, context_dict)

        hash_input = json.dumps({"query": query, "context": context_dict}, sort_keys=True)
        hashed_key = hashlib.md5(hash_input.encode("utf-8")).hexdigest()

        raw_response = await self._cached_gemini_call(hashed_key, prompt)
        return self._enforce_accessibility(raw_response, context_dict)

    def generate_stream(
        self,
        query: str,
        context_dict: Dict[str, Any],
    ) -> Generator[str, None, None]:
        """
        Generate a streaming response from the Gemini model.

        Yields text chunks as they arrive, optimising
        Time-to-First-Token (TTFT) for responsive mobile and kiosk
        interfaces inside the stadium.

        Args:
            query: The fan's natural-language question or request.
            context_dict: Real-time stadium telemetry dictionary.

        Yields:
            Successive text chunks from the model as they are generated.

        Raises:
            google.generativeai.types.BlockedPromptException:
                If the safety filters block the prompt.
            google.generativeai.types.StopCandidateException:
                If the safety filters block the generated response.
        """
        prompt: str = self._build_prompt(query, context_dict)

        response_stream = self._model.generate_content(
            prompt,
            stream=True,
        )

        full_text = ""
        for chunk in response_stream:
            if chunk.parts:
                yield chunk.text
                full_text += chunk.text

        # Post-validation on the complete stream
        override_text = self._enforce_accessibility(full_text, context_dict)
        if override_text != full_text:
            yield "\n\n[SYSTEM OVERRIDE]: Accessible route strictly required. Please use the nearest elevator."
