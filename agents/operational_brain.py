"""
ArenaMind-AI — Operational Brain
=================================
Core intelligence module powering the stadium operations agent.
Wraps the Google Gemini GenerativeModel with enterprise-grade safety
settings, prompt-injection defences, and real-time telemetry injection
for live FIFA World Cup 2026 venue operations.
"""

import re
import json
import hashlib
from typing import Any, Dict, Generator
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from async_lru import alru_cache

from prompts.templates import STADIUM_SYSTEM_INSTRUCTION
from exceptions import ModelTimeoutError, ConfigurationError
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
        self._safety_settings: Dict[Any, Any] = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }

        # ── 3. Model Initialisation ─────────────────────────────────────
        # gemini-3.5-flash is the latest free-tier Flash model, chosen
        # for maximum efficiency and its low-latency profile — critical
        # for real-time stadium operations where fans expect sub-second
        # guidance on mobile devices in noisy environments.
        #
        # The generation_config caps both cost and worst-case latency per 
        # request, complementing the system prompt's soft 150-word guidance 
        # with a hard backend-enforced ceiling.
        self._model: genai.GenerativeModel = genai.GenerativeModel(
            model_name="gemini-3.5-flash",
            system_instruction=STADIUM_SYSTEM_INSTRUCTION,
            safety_settings=self._safety_settings,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=settings.MAX_TOKENS
            ),
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

    def _build_telemetry_context(self, context_data: dict) -> str:
        """
        Format the real-time stadium telemetry context into a
        structured text block that is prepended to every user query.

        Args:
            context_data (dict): Dictionary containing live operational data.
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
            str: A formatted multi-line string block containing the telemetry data.
        """

        def _get(key: str, default: str = "N/A") -> str:
            """Safely retrieve a context value as a display string."""
            value = context_data.get(key)
            if value is None:
                return default
            if isinstance(value, bool):
                return "YES" if value else "NO"
            return str(value).strip() or default

        base = (
            "══════════════ LIVE STADIUM TELEMETRY ══════════════\n"
            f"  Match Phase          : {_get('current_phase')}\n"
            f"  Venue                : {_get('venue_name')} ({_get('venue_id')})\n"
            f"  Match ID             : {_get('match_id')}\n"
            f"  Fan Section          : {_get('user_section')}\n"
            f"  Accessibility Required: {_get('accessibility_required')}\n"
            f"  Timestamp (UTC)      : {_get('timestamp_utc')}\n"
        )
        gates = context_data.get("gates", {})
        if gates:
            for gate, status in gates.items():
                base += f"  Gate {gate} Congestion : {status}\n"
        
        facilities = context_data.get("facilities", {})
        if facilities:
            for fac, status in facilities.items():
                base += f"  Facility {fac} : {status}\n"
                
        base += "═══════════════════════════════════════════════════\n"
        return base

    def _build_prompt(self, query: str, context_dict: Dict[str, Any]) -> str:
        """
        Assemble the final prompt from sanitised user input and
        live telemetry data.

        Args:
            query (str): Raw user query (will be sanitised).
            context_dict (Dict[str, Any]): Live stadium telemetry dictionary.

        Returns:
            str: The fully constructed prompt string ready for the model.
        """
        safe_query: str = self._sanitize_input(query)
        telemetry_block: str = self._build_telemetry_context(context_dict)

        return (
            f"{telemetry_block}\n"
            f"Fan Query:\n"
            f"{safe_query}\n"
        )

    def _enforce_accessibility(self, text: str, context: dict) -> str:
        """Deterministic check for ADA route enforcement."""
        if context.get("accessibility_required"):
            text_lower = text.lower()
            if "stairs" in text_lower or "escalator" in text_lower:
                return "[SYSTEM OVERRIDE]: Accessible route strictly required. Please use the nearest elevator or ramp."
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
        to return instantly for identical queries. The caching mechanism hashes the 
        input query and context dictionary to create a unique key. If the same query 
        and context are encountered again, the cached response is returned, completely 
        bypassing the Gemini API to save costs and reduce latency. Before hitting the 
        cache, the context is dynamically injected via `_build_telemetry_context`.

        Args:
            query (str): The fan's natural-language question or request.
            context_dict (Dict[str, Any]): Real-time stadium telemetry dictionary.

        Returns:
            str: The model's full text response as a single string.
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
        timeout: float = 15.0,
    ) -> Generator[str, None, None]:
        """
        Generate a streaming response from the Gemini model.

        When ``accessibility_required`` is **False** (the common case),
        chunks are yielded token-by-token as they arrive, optimising
        Time-to-First-Token (TTFT) for responsive mobile and kiosk
        interfaces inside the stadium.

        When ``accessibility_required`` is **True**, the stream is
        buffered internally and the complete text is run through
        ``_enforce_accessibility()`` before a single SSE event is
        emitted.  This trades streaming latency for a **guaranteed-safe**
        output — a wheelchair user will never see "take the stairs"
        flash across their screen before an override arrives.

        Args:
            query: The fan's natural-language question or request.
            context_dict: Real-time stadium telemetry dictionary.

        Yields:
            Successive text chunks from the model as they are generated
            (or a single corrected chunk when accessibility is required).

        Raises:
            google.generativeai.types.BlockedPromptException:
                If the safety filters block the prompt.
            google.generativeai.types.StopCandidateException:
                If the safety filters block the generated response.
        """
        prompt: str = self._build_prompt(query, context_dict)
        accessibility_required: bool = bool(
            context_dict.get("accessibility_required")
        )

        response_stream = self._model.generate_content(
            prompt,
            stream=True,
        )

        if accessibility_required:
            # ── Option A: buffer-then-validate ──────────────────────
            # Collect every chunk silently, apply the deterministic
            # accessibility guardrail on the full text, then yield the
            # corrected result as a single event.
            full_text = ""
            start_time = time.monotonic()
            for chunk in response_stream:
                if time.monotonic() - start_time > timeout:
                    logger.error("generate_stream timed out after %.1fs", timeout)
                    yield "[ERROR] Response generation timed out. Please try again or contact venue staff."
                    return
                if chunk.parts:
                    full_text += chunk.text

            safe_text = self._enforce_accessibility(full_text, context_dict)
            yield safe_text
        else:
            # ── Standard token-by-token streaming ──────────────────
            start_time = time.monotonic()
            for chunk in response_stream:
                if time.monotonic() - start_time > timeout:
                    logger.error("generate_stream timed out after %.1fs", timeout)
                    yield "[ERROR] Response generation timed out. Please try again or contact venue staff."
                    return
                if chunk.parts:
                    yield chunk.text

