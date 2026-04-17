import httpx
import json
from typing import AsyncGenerator


class OllamaError(Exception):
    """Raised on Ollama connection or API errors."""
    pass


class OllamaClient:
    """Async client for Ollama's /api/generate and /api/chat endpoints."""

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
            options = dict(options)
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
        except httpx.HTTPError as e:
            raise OllamaError(f"HTTP error communicating with Ollama: {e}") from e

    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
        options: dict | None = None,
        stop: list[str] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream tokens from Ollama /api/chat. Yields dicts with token/thinking/done keys.

        Each yielded dict:
          {"token": "...", "thinking": bool, "done": False}
          {"token": "", "done": True, "total_tokens": N, "tokens_per_second": F}
        """
        think = False
        ollama_options = {}
        if options:
            options = dict(options)
            think = options.pop("think", False)
            ollama_options = {k: v for k, v in options.items() if v is not None}

        body: dict = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if ollama_options:
            body["options"] = ollama_options
        if think:
            body["think"] = True
        if stop:
            body["stop"] = stop

        total_tokens = 0
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=body
                ) as resp:
                    if resp.status_code != 200:
                        text = await resp.aread()
                        raise OllamaError(f"Ollama returned {resp.status_code}: {text.decode()}")
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)

                        thinking_text = data.get("message", {}).get("thinking", "") or data.get("thinking", "")
                        token_text = data.get("message", {}).get("content", "")

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
        except httpx.HTTPError as e:
            raise OllamaError(f"HTTP error communicating with Ollama: {e}") from e

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

    async def count_generate_prompt(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
    ) -> int:
        """Tokenize a prompt via /api/generate and return prompt_eval_count.

        Posts with `num_predict: 0` so Ollama tokenizes the prompt but
        generates no output. Used by budget.fit_raw_prompt for ground-truth
        counting that matches the generate endpoint's template — /api/chat
        would apply chat role markers that /api/generate does not.
        """
        body: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 0},
        }
        if system:
            body["system"] = system
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=body)
                if resp.status_code != 200:
                    raise OllamaError(f"Ollama returned {resp.status_code}: {resp.text}")
                data = resp.json()
                return int(data.get("prompt_eval_count", 0) or 0)
        except httpx.ConnectError:
            raise OllamaError(f"Cannot connect to Ollama at {self.base_url}")
        except httpx.HTTPError as e:
            raise OllamaError(f"HTTP error communicating with Ollama: {e}") from e

    async def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        think: bool = False,
    ) -> dict:
        """Non-streaming chat call. Returns the full Ollama response dict.

        Supports native tool calling via the tools parameter.
        """
        body: dict = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            body["tools"] = tools
        if think:
            body["think"] = True
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=body)
                if resp.status_code != 200:
                    raise OllamaError(f"Ollama returned {resp.status_code}: {resp.text}")
                return resp.json()
        except httpx.ConnectError:
            raise OllamaError(f"Cannot connect to Ollama at {self.base_url}")
        except httpx.HTTPError as e:
            raise OllamaError(f"HTTP error communicating with Ollama: {e}") from e

    async def is_available(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_models(self) -> list[str]:
        """Return list of available model names from Ollama."""
        details = await self.list_models_detail()
        return [m["name"] for m in details]

    async def _check_think_support(self, client: httpx.AsyncClient, model: str) -> bool:
        """Check if a model supports thinking by inspecting its template."""
        try:
            resp = await client.post(f"{self.base_url}/api/show", json={"model": model})
            if resp.status_code == 200:
                template = resp.json().get("template", "")
                return ".Think" in template
        except httpx.HTTPError:
            pass
        return False

    async def list_models_detail(self) -> list[dict]:
        """Return list of models with name and size info from Ollama."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    result = []
                    for m in data.get("models", []):
                        info = {"name": m["name"]}
                        details = m.get("details", {})
                        if details.get("parameter_size"):
                            info["parameter_size"] = details["parameter_size"]
                        if details.get("quantization_level"):
                            info["quantization_level"] = details["quantization_level"]
                        if m.get("size"):
                            info["size_bytes"] = m["size"]
                        info["supports_think"] = await self._check_think_support(client, m["name"])
                        result.append(info)
                    return result
        except httpx.HTTPError:
            pass
        return []

    _OLLAMA_DEFAULT_CTX = 2048

    async def get_num_ctx(self, model: str) -> int:
        """Return effective context length for a model via /api/show.

        Prefers the runtime num_ctx from the parameters field (what Ollama
        actually allocates). Falls back to Ollama's built-in default (2048).

        Does NOT use model_info.<arch>.context_length — that is the
        architectural maximum from the GGUF file (often 1M+), not the
        runtime allocation. Passing it as num_ctx would force Ollama to
        allocate an enormous KV cache.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/show", json={"model": model}
                )
                if resp.status_code != 200:
                    raise OllamaError(
                        f"Ollama /api/show returned {resp.status_code}: {resp.text}"
                    )
                data = resp.json()
        except httpx.ConnectError:
            raise OllamaError(f"Cannot connect to Ollama at {self.base_url}")
        except httpx.HTTPError as e:
            raise OllamaError(f"HTTP error from /api/show: {e}") from e

        params_str = data.get("parameters", "") or ""
        for line in params_str.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "num_ctx":
                try:
                    return int(parts[1])
                except ValueError:
                    pass

        return self._OLLAMA_DEFAULT_CTX

    async def embed(self, model: str, text: str) -> list[float]:
        """Get embedding vector for text via Ollama /api/embed."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": model, "input": text},
                )
                if resp.status_code != 200:
                    raise OllamaError(f"Ollama embed returned {resp.status_code}: {resp.text}")
                data = resp.json()
                return data["embeddings"][0]
        except httpx.ConnectError:
            raise OllamaError(f"Cannot connect to Ollama at {self.base_url}")
        except httpx.HTTPError as e:
            raise OllamaError(f"HTTP error communicating with Ollama: {e}") from e

    @staticmethod
    def count_tokens(text: str) -> int:
        """Estimate token count (~4 chars per token)."""
        return len(text) // 4
