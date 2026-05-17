"""Routing layer that dispatches to Ollama or Anthropic based on model name."""

import logging
from typing import AsyncGenerator

from ollama import OllamaClient
from anthropic_client import AnthropicClient, is_anthropic_model, ANTHROPIC_MODELS

_log = logging.getLogger("aiserver.multi")


class MultiClient:
    """Drop-in replacement for OllamaClient that routes Anthropic models to their API."""

    def __init__(self, ollama: OllamaClient):
        self._ollama = ollama
        self._anthropic: AnthropicClient | None = None

    def _get_anthropic(self) -> AnthropicClient:
        if self._anthropic is None:
            self._anthropic = AnthropicClient()
            _log.info("Anthropic client initialized")
        return self._anthropic

    def _backend(self, model: str):
        if is_anthropic_model(model):
            return self._get_anthropic()
        return self._ollama

    @property
    def base_url(self) -> str:
        return self._ollama.base_url

    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
        options: dict | None = None,
        stop: list[str] | None = None,
    ) -> AsyncGenerator[dict, None]:
        backend = self._backend(model)
        async for chunk in backend.chat_stream(model=model, messages=messages,
                                               options=options, stop=stop):
            yield chunk

    async def generate_stream(self, model: str, prompt: str, **kwargs) -> AsyncGenerator[dict, None]:
        if is_anthropic_model(model):
            backend = self._get_anthropic()
            messages = [{"role": "user", "content": prompt}]
            system = kwargs.get("system")
            if system:
                messages.insert(0, {"role": "system", "content": system})
            options = kwargs.get("options")
            async for chunk in backend.chat_stream(model=model, messages=messages, options=options):
                yield chunk
        else:
            async for chunk in self._ollama.generate_stream(model, prompt, **kwargs):
                yield chunk

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict | None = None,
    ) -> str:
        return await self._backend(model).generate(model=model, prompt=prompt,
                                                   system=system, options=options)

    async def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        think: bool | None = None,
        options: dict | None = None,
    ) -> dict:
        if is_anthropic_model(model) and options and options.get("num_predict", 0) <= 1:
            total_chars = sum(len(m.get("content", "")) for m in messages)
            return {"prompt_eval_count": total_chars // 4, "message": {"content": ""}, "done": True}
        return await self._backend(model).chat(model=model, messages=messages,
                                               tools=tools, think=think, options=options)

    async def count_generate_prompt(self, model: str, prompt: str,
                                    system: str | None = None) -> int:
        if is_anthropic_model(model):
            return len(prompt) // 4
        return await self._ollama.count_generate_prompt(model, prompt, system=system)

    async def list_models(self) -> list[str]:
        models = await self._ollama.list_models()
        models.extend(ANTHROPIC_MODELS)
        return models

    async def list_models_detail(self) -> list[dict]:
        return await self._ollama.list_models_detail()

    async def is_available(self) -> bool:
        return await self._ollama.is_available()

    async def get_num_ctx(self, model: str) -> int:
        if is_anthropic_model(model):
            return 200000
        return await self._ollama.get_num_ctx(model)
