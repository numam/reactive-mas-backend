"""
provider_ollama.py
========================
Concrete LLMProvider implementation for Ollama (local inference server).

Calls the Ollama REST API at http://localhost:11434 using the /api/chat
endpoint with format="json" to enforce structured JSON output, so no
external SDK is needed — only `requests`.

Usage:
    from provider_ollama import OllamaProvider
    provider = OllamaProvider(model_name="qwen3:4b")
    result = provider.call("some prompt text")

Make sure Ollama is running locally before use:
    ollama serve
    ollama pull qwen3:4b

Ollama docs: https://github.com/ollama/ollama/blob/main/docs/api.md
"""

import json
import re
import time
import requests

from llm_provider_base import LLMProvider, LLMCallResult, ParsedDecision

OLLAMA_API_BASE = "http://localhost:11434"

# System prompt injected on every call. Specifies the exact schema so that
# qwen3's format=json mode produces the right keys with the right value types.
_SYSTEM_PROMPT = (
    "You are a supply chain manager decision agent. "
    "You MUST respond with a single valid JSON object and absolutely nothing else. "
    "No explanation, no markdown fences, no preamble, no extra text. "
    'The JSON object MUST have exactly these three keys: '
    '"decision" (string — must be exactly one of: ACCEPT, MODIFY, OVERRIDE), '
    '"factor" (number between 0.0 and 1.0), '
    '"justification" (string, 2-3 sentences explaining your reasoning). '
    "Only output the JSON object."
)

# Keywords that map ambiguous decision strings to canonical values.
# qwen3 sometimes writes "Reduce production by 20%" instead of "MODIFY".
_DECISION_KEYWORDS = {
    "accept":   "ACCEPT",
    "approve":  "ACCEPT",
    "agree":    "ACCEPT",
    "modify":   "MODIFY",
    "reduce":   "MODIFY",
    "adjust":   "MODIFY",
    "partial":  "MODIFY",
    "override": "OVERRIDE",
    "reject":   "OVERRIDE",
    "deny":     "OVERRIDE",
    "refuse":   "OVERRIDE",
}


def _normalize_decision(raw: str) -> str:
    """
    Try to map a model's free-text decision string to ACCEPT/MODIFY/OVERRIDE.
    Returns the canonical value, or "" if no match is found.
    """
    v = raw.upper().strip()
    if v in ("ACCEPT", "MODIFY", "OVERRIDE"):
        return v
    v_lower = raw.lower().strip()
    for keyword, canonical in _DECISION_KEYWORDS.items():
        if keyword in v_lower:
            return canonical
    return ""


class OllamaProvider(LLMProvider):
    provider_name = "ollama"

    def __init__(self, api_key: str = "", model_name: str = "qwen3:4b",
                 temperature: float = 0.0, max_tokens: int = 512,
                 timeout_s: float = None):
        # timeout_s=None means wait indefinitely — correct for a slow CPU
        # that needs several minutes per call. A hard timeout would produce
        # PARSE_FAILURE entries in the CSV, which is exactly what we want
        # to avoid.
        super().__init__(api_key=api_key, temperature=temperature, max_tokens=max_tokens)
        self.model_name = model_name
        self.timeout_s = timeout_s

    @staticmethod
    def _strip_thinking(text: str) -> str:
        """Remove <think>...</think> blocks before JSON parsing."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    def call(self, prompt: str) -> LLMCallResult:
        url = f"{OLLAMA_API_BASE}/api/chat"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.model_name,
            "stream": False,
            "think": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
        }

        t0 = time.time()
        try:
            resp = requests.post(
                url, headers=headers, json=payload,
                timeout=self.timeout_s,   # None = wait as long as needed
            )
            latency_ms = (time.time() - t0) * 1000.0
        except requests.exceptions.RequestException as e:
            return LLMCallResult(
                raw_text="", model_name=self.model_name, tokens_in=0,
                tokens_out=0, latency_ms=(time.time() - t0) * 1000.0,
                success=False, error=f"Request exception: {e}",
            )

        if resp.status_code != 200:
            return LLMCallResult(
                raw_text="", model_name=self.model_name, tokens_in=0,
                tokens_out=0, latency_ms=latency_ms, success=False,
                error=f"HTTP {resp.status_code}: {resp.text[:300]}",
            )

        try:
            data = resp.json()
            text = data.get("message", {}).get("content", "")
            text = self._strip_thinking(text)

            tokens_in  = data.get("prompt_eval_count", 0) or 0
            tokens_out = data.get("eval_count", 0) or 0

            if not text:
                return LLMCallResult(
                    raw_text="", model_name=self.model_name,
                    tokens_in=tokens_in, tokens_out=tokens_out,
                    latency_ms=latency_ms, success=False,
                    error="Empty response content from Ollama.",
                )

            return LLMCallResult(
                raw_text=text, model_name=self.model_name,
                tokens_in=tokens_in, tokens_out=tokens_out,
                latency_ms=latency_ms, success=True,
            )
        except (KeyError, ValueError) as e:
            return LLMCallResult(
                raw_text="", model_name=self.model_name, tokens_in=0,
                tokens_out=0, latency_ms=latency_ms, success=False,
                error=f"Response parsing error: {e}",
            )

    def call_and_parse(self, prompt: str,
                       max_retries: int = 3) -> tuple[LLMCallResult, ParsedDecision]:
        """
        Override the base class method with three improvements for local
        Ollama / qwen3 use:

        1. max_retries defaults to 3 (vs 1 in base) so transient glitches
           get multiple chances before writing a failure row to the CSV.
        2. Decision normalization: if the model returns a semantically valid
           but non-canonical string (e.g. "Reduce production by 20%"), map
           it to MODIFY instead of failing.
        3. After all retries are exhausted, fall back to ACCEPT with a clear
           justification rather than PARSE_FAILURE, so the CSV always contains
           a readable decision row.
        """
        last_result = None
        last_raw = ""

        for attempt in range(max_retries + 1):
            result = self.call(prompt)
            last_result = result
            last_raw = result.raw_text

            if not result.success:
                # Network / HTTP error — retry
                continue

            # Try base-class JSON parsing first
            parsed = self._parse_json_response(result.raw_text)
            if parsed.parse_ok:
                return result, parsed

            # Base parser failed — try to rescue the response
            rescued = self._rescue_parse(result.raw_text)
            if rescued is not None:
                return result, rescued

            # Still failed — retry

        # ── All retries exhausted.
        # Return parse_ok=False so llm_hitl_engine.process_signal() records
        # this as "timeout" in the CSV (its logic: `if timed_out or not parsed.parse_ok
        # → decision = "timeout"`). This keeps the CSV decision column honest:
        # a failed parse becomes "timeout", not a fake "accept".
        fallback_justification = (
            f"LLM returned an unparseable response after {max_retries + 1} attempts. "
            f"Raw (truncated): {last_raw[:120]!r}"
        )
        return last_result, ParsedDecision(
            decision="PARSE_FAILURE",
            factor=1.0,
            justification=fallback_justification,
            parse_ok=False,
            raw_response=last_raw,
        )

    @staticmethod
    def _rescue_parse(raw_text: str) -> "ParsedDecision | None":
        """
        Secondary parser for responses that pass the JSON structure check
        but fail schema validation (e.g. wrong decision string, missing keys).

        Returns a ParsedDecision if a rescue is possible, None otherwise.
        """
        text = raw_text.strip()

        # Strip <think> blocks again just in case
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # Strip markdown code fences
        if "```" in text:
            for part in text.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith("{"):
                    text = part
                    break

        # Extract outermost { ... }
        start = text.find("{")
        end   = text.rfind("}")
        if start == -1 or end <= start:
            return None

        try:
            obj = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None

        # Normalize decision
        raw_decision = str(obj.get("decision", ""))
        decision = _normalize_decision(raw_decision)
        if not decision:
            return None     # cannot rescue — unknown decision string

        # factor
        try:
            factor = float(obj.get("factor", 1.0))
        except (TypeError, ValueError):
            factor = 1.0
        factor = max(0.0, min(1.0, factor))

        justification = str(obj.get("justification", "")).strip()
        if not justification:
            justification = f"Decision: {decision} (factor={factor:.2f}; justification field was empty)."

        return ParsedDecision(
            decision=decision,
            factor=factor,
            justification=justification,
            parse_ok=True,
            raw_response=raw_text,
        )
