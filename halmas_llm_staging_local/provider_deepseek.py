"""
provider_deepseek.py
========================
Concrete LLMProvider implementation for DeepSeek-R1:7B via Ollama.

Thin subclass of OllamaProvider — identical behaviour, only the default
model name differs. DeepSeek-R1 also uses <think>...</think> blocks which
are already stripped by OllamaProvider._strip_thinking().

Usage:
    from provider_deepseek import DeepSeekProvider
    provider = DeepSeekProvider()
    result = provider.call("some prompt text")

Make sure the model is pulled before use:
    ollama pull deepseek-r1:7b
"""

from provider_ollama import OllamaProvider


class DeepSeekProvider(OllamaProvider):
    provider_name = "deepseek"

    def __init__(self, api_key: str = "", model_name: str = "deepseek-r1:7b",
                 temperature: float = 0.0, max_tokens: int = 512,
                 timeout_s: float = None):
        super().__init__(
            api_key=api_key,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )
