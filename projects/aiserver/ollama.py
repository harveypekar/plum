import httpx
import json
from typing import AsyncGenerator


class OllamaError(Exception):
    """Raised on Ollama connection or API errors."""
    pass


class OllamaClient:
    """Async client for Ollama's /api/generate endpoint."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    async def generate_stream(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream tokens from Ollama. Yields dicts with token/thinking/done keys.

        Each yielded dict:
          {"token": "...", "thinking": bool, "done": False}
          {"token": "", "done": True, "total_tokens": N, "tokens_per_second": F}
        """
        think = False
        ollama_options = {}
        if options:
            think = options.pop("think", False)
            ollama_options = {k: v for k, v in options.items() if v is not None}

        body: dict = {
            "model": model,
            "prompt": prompt,
            "stream": True,
        }
        if system:
            body["system"] = system
        if ollama_options:
            body["options"] = ollama_options
        if think:
            body["think"] = True

        total_tokens = 0
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/generate", json=body
                ) as resp:
                    if resp.status_code != 200:
                        text = await resp.aread()
                        raise OllamaError(f"Ollama returned {resp.status_code}: {text.decode()}")
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)

                        thinking_text = data.get("thinking", "")
                        token_text = data.get("response", "")

                        if thinking_text:
                            total_tokens += 1
                            yield {"token": thinking_text, "thinking": True, "done": False}
                        if token_text:
                            total_tokens += 1
                            yield {"token": token_text, "thinking": False, "done": False}

                        if data.get("done"):
                            eval_count = data.get("eval_count", total_tokens)
                            eval_duration = data.get("eval_duration", 1)
                            tps = eval_count / (eval_duration / 1e9) if eval_duration else 0
                            yield {
                                "token": "",
                                "done": True,
                                "total_tokens": eval_count,
                                "tokens_per_second": round(tps, 1),
                            }
                            return
        except httpx.ConnectError:
            raise OllamaError(f"Cannot connect to Ollama at {self.base_url}")

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict | None = None,
    ) -> str:
        """Send prompt, return complete response (thinking tokens discarded)."""
        tokens = []
        async for chunk in self.generate_stream(model, prompt, system=system, options=options):
            if not chunk.get("thinking") and not chunk.get("done"):
                tokens.append(chunk["token"])
        return "".join(tokens)

    async def is_available(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except httpx.ConnectError:
            return False

    async def list_models(self) -> list[str]:
        """Return list of available model names from Ollama."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    return [m["name"] for m in data.get("models", [])]
        except httpx.ConnectError:
            pass
        return []

    @staticmethod
    def count_tokens(text: str) -> int:
        """Estimate token count (~4 chars per token)."""
        return len(text) // 4
