"""
provider_llama.py
========================
Concrete LLMProvider implementation for Llama 3.1:8B via Ollama.

Llama 3.1 differences vs qwen3/deepseek that this provider handles:

1. No <think> blocks — llama3.1 does not use chain-of-thought tags.
2. format="json" is supported and reliable on llama3.1, so we keep it.
3. Llama 3.1 responds faster than qwen3 on CPU (~15-25s vs ~40s).
4. Llama 3.1 is more likely to produce a valid decision string directly
   (ACCEPT/MODIFY/OVERRIDE) without needing normalization, but the
   _rescue_parse fallback from OllamaProvider handles edge cases anyway.

Usage:
    from provider_llama import LlamaProvider
    provider = LlamaProvider()
    result = provider.call("some prompt text")

Make sure the model is pulled before use:
    ollama pull llama3.1:8b
"""

from provider_ollama import OllamaProvider


class LlamaProvider(OllamaProvider):
    provider_name = "llama"

    def __init__(self, api_key: str = "", model_name: str = "llama3.1:8b",
                 temperature: float = 0.0, max_tokens: int = 512,
                 timeout_s: float = None):
        super().__init__(
            api_key=api_key,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )

    @staticmethod
    def _strip_thinking(text: str) -> str:
        # Llama 3.1 does not emit <think> blocks — override to skip the
        # regex entirely for a minor speedup, and return the text as-is.
        return text.strip()
