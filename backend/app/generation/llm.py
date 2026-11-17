"""Clients LLM minimalistes (HTTP direct, sans SDK) : le fournisseur se change par variable d'environnement."""
from functools import lru_cache
from typing import Protocol

import httpx

from app.config import get_settings


class LLM(Protocol):
    name: str

    def generate(self, system: str, prompt: str, max_tokens: int = 800) -> str: ...


class LLMError(RuntimeError):
    pass


class AnthropicLLM:
    def __init__(self, model: str, api_key: str, temperature: float, timeout: float):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY manquant")
        self.name, self.model, self.key, self.t, self.timeout = f"anthropic:{model}", model, api_key, temperature, timeout

    def generate(self, system: str, prompt: str, max_tokens: int = 800) -> str:
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"},
            json={
                "model": self.model,
                "system": system,
                "max_tokens": max_tokens,
                "temperature": self.t,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=self.timeout,
        )
        if r.status_code >= 400:
            raise LLMError(f"Anthropic {r.status_code}: {r.text[:300]}")
        return "".join(b.get("text", "") for b in r.json()["content"])


class OpenAICompatibleLLM:
    """OpenAI ou toute API compatible (Mistral, vLLM, LM Studio...)."""

    def __init__(self, model: str, api_key: str, base_url: str, temperature: float, timeout: float):
        self.name, self.model, self.key, self.url = f"openai:{model}", model, api_key, base_url.rstrip("/")
        self.t, self.timeout = temperature, timeout

    def generate(self, system: str, prompt: str, max_tokens: int = 800) -> str:
        r = httpx.post(
            f"{self.url}/chat/completions",
            headers={"Authorization": f"Bearer {self.key}"},
            json={
                "model": self.model,
                "temperature": self.t,
                "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            },
            timeout=self.timeout,
        )
        if r.status_code >= 400:
            raise LLMError(f"OpenAI-compatible {r.status_code}: {r.text[:300]}")
        return r.json()["choices"][0]["message"]["content"]


class OllamaLLM:
    """Modèle open-weight servi localement : aucune donnée ne quitte la machine."""

    def __init__(self, model: str, url: str, temperature: float, timeout: float, num_ctx: int = 8192):
        self.name, self.model, self.url, self.t, self.timeout = f"ollama:{model}", model, url.rstrip("/"), temperature, timeout
        self.num_ctx = num_ctx

    def generate(self, system: str, prompt: str, max_tokens: int = 800) -> str:
        r = httpx.post(
            f"{self.url}/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "options": {"temperature": self.t, "num_predict": max_tokens, "num_ctx": self.num_ctx},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            },
            timeout=self.timeout,
        )
        if r.status_code >= 400:
            raise LLMError(f"Ollama {r.status_code}: {r.text[:300]}")
        return r.json()["message"]["content"]


@lru_cache
def get_llm() -> LLM | None:
    """None = mode extractif (pas de génération, phrases sources citées telles quelles)."""
    s = get_settings()
    p = s.llm_provider
    if p == "extractive":
        return None
    if not s.llm_model:
        raise LLMError("LLM_MODEL doit être renseigné pour le fournisseur " + p)
    if p == "anthropic":
        return AnthropicLLM(s.llm_model, s.anthropic_api_key, s.llm_temperature, s.llm_timeout_s)
    if p == "openai":
        return OpenAICompatibleLLM(s.llm_model, s.openai_api_key, s.openai_base_url, s.llm_temperature, s.llm_timeout_s)
    if p == "ollama":
        return OllamaLLM(s.llm_model, s.ollama_url, s.llm_temperature, s.llm_timeout_s, s.ollama_num_ctx)
    raise LLMError(f"LLM_PROVIDER inconnu : {p}")
