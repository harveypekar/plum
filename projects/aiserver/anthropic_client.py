"""Anthropic API client matching the OllamaClient interface for drop-in routing."""

import os
import logging
from typing import AsyncGenerator

import anthropic

from ollama import OllamaError

_log = logging.getLogger("aiserver.anthropic")

ANTHROPIC_MODELS = frozenset({
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
})

DEFAULT_MAX_TOKENS = 1024


def is_anthropic_model(model: str) -> bool:
    return model in ANTHROPIC_MODELS


def _map_options(options: dict | None) -> dict:
    """Map Ollama-style options to Anthropic API params."""
    if not options:
        return {"max_tokens": DEFAULT_MAX_TOKENS}
    params: dict = {}
    params["max_tokens"] = options.get("num_predict", DEFAULT_MAX_TOKENS)
    if "temperature" in options:
        params["temperature"] = options["temperature"]
    if "top_p" in options:
        params["top_p"] = options["top_p"]
    if "top_k" in options:
        params["top_k"] = options["top_k"]
    if stop := options.get("stop"):
        params["stop_sequences"] = stop if isinstance(stop, list) else [stop]
    return params


def _split_system_and_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    """Extract system message from message list, return (system, remaining)."""
    system_parts = []
    chat_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_parts.append(msg["content"])
        else:
            chat_messages.append({"role": msg["role"], "content": msg["content"]})
    return "\n\n".join(system_parts), chat_messages


class AnthropicClient:
    """Async Anthropic client with the same interface as OllamaClient."""

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise OllamaError("ANTHROPIC_API_KEY not set")
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
        options: dict | None = None,
        stop: list[str] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream tokens from Anthropic. Yields same format as OllamaClient.chat_stream."""
        system, chat_messages = _split_system_and_messages(messages)
        params = _map_options(options)
        if stop:
            params["stop_sequences"] = stop

        max_tokens = params.pop("max_tokens", DEFAULT_MAX_TOKENS)
        total_tokens = 0

        try:
            async with self._client.messages.stream(
                model=model,
                messages=chat_messages,
                system=system or anthropic.NOT_GIVEN,
                max_tokens=max_tokens,
                **params,
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            total_tokens += 1
                            yield {"token": event.delta.text, "thinking": False, "done": False}
                        elif event.delta.type == "thinking_delta":
                            total_tokens += 1
                            yield {"token": event.delta.thinking, "thinking": True, "done": False}

                final = await stream.get_final_message()
                input_tokens = final.usage.input_tokens
                output_tokens = final.usage.output_tokens
                yield {
                    "token": "",
                    "done": True,
                    "total_tokens": output_tokens,
                    "tokens_per_second": 0,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                }
        except anthropic.APIError as e:
            raise OllamaError(f"Anthropic API error: {e}") from e

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict | None = None,
    ) -> str:
        """Non-streaming generation. Maps prompt to a single user message."""
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})
        tokens = []
        async for chunk in self.chat_stream(model=model, messages=messages, options=options):
            if not chunk.get("thinking") and not chunk.get("done"):
                tokens.append(chunk["token"])
        return "".join(tokens)

    async def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        think: bool | None = None,
        options: dict | None = None,
    ) -> dict:
        """Non-streaming chat. Returns dict compatible with OllamaClient.chat."""
        system, chat_messages = _split_system_and_messages(messages)
        params = _map_options(options)
        max_tokens = params.pop("max_tokens", DEFAULT_MAX_TOKENS)

        try:
            response = await self._client.messages.create(
                model=model,
                messages=chat_messages,
                system=system or anthropic.NOT_GIVEN,
                max_tokens=max_tokens,
                **params,
            )
            content = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return {
                "message": {"role": "assistant", "content": content},
                "done": True,
                "total_duration": 0,
                "eval_count": response.usage.output_tokens,
                "prompt_eval_count": response.usage.input_tokens,
            }
        except anthropic.APIError as e:
            raise OllamaError(f"Anthropic API error: {e}") from e
