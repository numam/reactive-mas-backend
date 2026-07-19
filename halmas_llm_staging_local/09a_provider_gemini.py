"""
09a_provider_gemini.py
========================
Concrete LLMProvider implementation for Google Gemini.

Uses the Gemini REST API directly (no google-generativeai SDK dependency)
so the only external package required is `requests`.

Usage:
    from provider_gemini import GeminiProvider
    provider = GeminiProvider(api_key="...", model_name="gemini-2.0-flash")
    result = provider.call("some prompt text")

Get an API key at: https://aistudio.google.com/app/apikey
"""

import time
import requests

from llm_provider_base import LLMProvider, LLMCallResult

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(LLMProvider):
    provider_name = "gemini"

    def __init__(self, api_key: str, model_name: str = "gemini-3.5-flash",
                 temperature: float = 0.0, max_tokens: int = 1024, timeout_s: float = 30.0):
        super().__init__(api_key=api_key, temperature=temperature, max_tokens=max_tokens)
        self.model_name = model_name
        self.timeout_s = timeout_s

    def call(self, prompt: str) -> LLMCallResult:
        url = f"{GEMINI_API_BASE}/{self.model_name}:generateContent"
        # Send API key both ways: header (current recommended) and query
        # param (legacy). This ensures compatibility across model aliases.
        headers = {
            "content-type": "application/json",
            "X-goog-api-key": self.api_key,
        }
        params = {"key": self.api_key}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }

        t0 = time.time()
        try:
            resp = requests.post(
                url, headers=headers, params=params,
                json=payload, timeout=self.timeout_s,
            )
            latency_ms = (time.time() - t0) * 1000.0
        except requests.exceptions.RequestException as e:
            return LLMCallResult(
                raw_text="", model_name=self.model_name, tokens_in=0,
                tokens_out=0, latency_ms=(time.time() - t0) * 1000.0,
                success=False, error=f"Request exception: {e}",
            )

        # 429 = rate limit — flagged distinctly so call_and_parse() backs off
        if resp.status_code == 429:
            return LLMCallResult(
                raw_text="", model_name=self.model_name, tokens_in=0,
                tokens_out=0, latency_ms=latency_ms, success=False,
                error=f"RATE_LIMIT_429: {resp.text[:200]}",
            )

        if resp.status_code != 200:
            return LLMCallResult(
                raw_text="", model_name=self.model_name, tokens_in=0,
                tokens_out=0, latency_ms=latency_ms, success=False,
                error=f"HTTP {resp.status_code}: {resp.text[:300]}",
            )

        try:
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                reason = data.get("promptFeedback", {}).get("blockReason", "unknown")
                return LLMCallResult(
                    raw_text="", model_name=self.model_name, tokens_in=0,
                    tokens_out=0, latency_ms=latency_ms, success=False,
                    error=f"No candidates returned (blockReason={reason})",
                )

            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)

            usage = data.get("usageMetadata", {})
            tokens_in = usage.get("promptTokenCount", 0)
            tokens_out = usage.get("candidatesTokenCount", 0)

            return LLMCallResult(
                raw_text=text, model_name=self.model_name,
                tokens_in=tokens_in, tokens_out=tokens_out,
                latency_ms=latency_ms, success=True,
            )
        except (KeyError, ValueError, IndexError) as e:
            return LLMCallResult(
                raw_text="", model_name=self.model_name, tokens_in=0,
                tokens_out=0, latency_ms=latency_ms, success=False,
                error=f"Response parsing error: {e}",
            )
