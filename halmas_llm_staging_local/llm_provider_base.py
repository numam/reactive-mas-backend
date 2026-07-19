"""
09_llm_provider_base.py
========================
Abstract interface for LLM providers used by the LLM Manager Agent
(Section 3.2-3.3 of HALMAS-LLM). Every concrete provider (Gemini, Claude,
GPT, ...) implements this same interface, so that 11_llm_hitl_engine.py
and run_llm_simulation.py never need to know which provider is in use.

Adding a new provider later means writing one new file that implements
LLMProvider.call() — nothing else in the codebase changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import json
import time


@dataclass
class LLMCallResult:
    """Raw result of a single LLM API call, before JSON parsing."""
    raw_text: str
    model_name: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class ParsedDecision:
    """Result after parsing the LLM's JSON response against output_schema.json."""
    decision: str            # ACCEPT | MODIFY | OVERRIDE | PARSE_FAILURE
    factor: float
    justification: str
    parse_ok: bool
    raw_response: str = ""


class LLMProvider(ABC):
    """
    Abstract base class for an LLM provider.

    Concrete subclasses must implement call(). Everything else
    (retry logic, JSON parsing, validation) is shared here so that
    provider implementations stay small and provider-specific code
    is limited to "how do I send this prompt and get text back".
    """

    #: Override in subclass with the exact model identifier used,
    #: e.g. "gemini-2.0-flash" or "claude-sonnet-4-6". This string is
    #: logged with every call for reproducibility (Table 5 / Appendix B).
    model_name: str = "override-me"

    #: Override in subclass: provider name for logging, e.g. "gemini".
    provider_name: str = "override-me"

    def __init__(self, api_key: str, temperature: float = 0.0, max_tokens: int = 512):
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    def call(self, prompt: str) -> LLMCallResult:
        """
        Send `prompt` to the underlying API and return the raw result.
        Must NOT raise on API errors — instead set success=False and
        populate `error` with a short description. This keeps retry
        and fallback logic centralised in call_and_parse() below.
        """
        raise NotImplementedError

    def call_and_parse(self, prompt: str, max_retries: int = 1) -> tuple[LLMCallResult, ParsedDecision]:
        """
        Call the provider, parse the JSON response, and retry once on
        either an API failure or a JSON parse failure, per the policy
        in prompts/output_schema.json.
        """
        last_result = None
        for attempt in range(max_retries + 1):
            result = self.call(prompt)
            last_result = result
            if not result.success:
                continue
            parsed = self._parse_json_response(result.raw_text)
            if parsed.parse_ok:
                return result, parsed
        # All attempts failed (API failure or parse failure every time)
        return last_result, ParsedDecision(
            decision="PARSE_FAILURE", factor=1.0,
            justification="LLM call or JSON parse failed after retry; treated as auto-accept.",
            parse_ok=False, raw_response=last_result.raw_text if last_result else ""
        )

    @staticmethod
    def _parse_json_response(raw_text: str) -> ParsedDecision:
        """
        Extract a JSON object from raw_text. Tolerates markdown code
        fences (```json ... ```) and leading/trailing whitespace or
        commentary, which some models add despite instructions not to.
        """
        text = raw_text.strip()
        # Strip markdown code fences if present
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    text = part
                    break

        # Find the outermost { ... } block in case of stray text around it
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return ParsedDecision(decision="PARSE_FAILURE", factor=1.0,
                                   justification="No JSON object found in response.",
                                   parse_ok=False, raw_response=raw_text)
        candidate = text[start:end + 1]

        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError as e:
            return ParsedDecision(decision="PARSE_FAILURE", factor=1.0,
                                   justification=f"JSON decode error: {e}",
                                   parse_ok=False, raw_response=raw_text)

        decision = str(obj.get("decision", "")).upper().strip()
        if decision not in ("ACCEPT", "MODIFY", "OVERRIDE"):
            return ParsedDecision(decision="PARSE_FAILURE", factor=1.0,
                                   justification=f"Invalid decision value: {decision!r}",
                                   parse_ok=False, raw_response=raw_text)

        try:
            factor = float(obj.get("factor", 1.0))
        except (TypeError, ValueError):
            factor = 1.0
        factor = max(0.0, min(1.0, factor))  # clamp into [0,1]

        justification = str(obj.get("justification", "")).strip()

        return ParsedDecision(decision=decision, factor=factor,
                               justification=justification, parse_ok=True,
                               raw_response=raw_text)
