# RP Chat: /api/chat Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate RP chat from Ollama's `/api/generate` to `/api/chat` with structured messages and post-history instructions, fixing name duplication, multi-turn generation, and missing stop boundaries.

**Architecture:** Add `chat_stream()` to OllamaClient, rework pipeline to produce system + post prompts + message array (no flat history), update routes to assemble structured chat messages with stop sequences.

**Tech Stack:** Python, FastAPI, httpx, Ollama `/api/chat`, pytest

---

### Task 1: Add `chat_stream()` to OllamaClient

**Files:**
- Modify: `projects/aiserver/ollama.py:88` (insert after `generate_stream`)
- Create: `projects/aiserver/tests/test_ollama_chat.py`

**Step 1: Write the failing test**

Create `projects/aiserver/tests/__init__.py` (empty) and test file:

```python
# projects/aiserver/tests/test_ollama_chat.py
import pytest
import json
import httpx
from unittest.mock import AsyncMock
from projects.aiserver.ollama import OllamaClient


class FakeStreamResponse:
    """Simulates httpx streaming response with NDJSON lines."""
    def __init__(self, lines, status_code=200):
        self.status_code = status_code
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return b"error"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class FakeClient:
    def __init__(self, response):
        self._response = response
        self.last_request = None

    def stream(self, method, url, json=None):
        self._response._request_json = json
        self.last_request = json
        return self._response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_chat_stream_sends_messages(monkeypatch):
    """chat_stream sends messages array to /api/chat."""
    lines = [
        json.dumps({"message": {"content": "Hello"}, "done": False}),
        json.dumps({"message": {"content": " world"}, "done": False}),
        json.dumps({"done": True, "eval_count": 10, "eval_duration": 1_000_000_000}),
    ]
    fake_resp = FakeStreamResponse(lines)
    fake_client = FakeClient(fake_resp)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: fake_client)

    client = OllamaClient()
    messages = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hi"},
    ]

    chunks = []
    async for chunk in client.chat_stream(model="test", messages=messages):
        chunks.append(chunk)

    # Verify request body
    assert fake_client.last_request["model"] == "test"
    assert fake_client.last_request["messages"] == messages
    assert fake_client.last_request["stream"] is True
    assert "prompt" not in fake_client.last_request  # not generate API

    # Verify yielded chunks
    assert chunks[0] == {"token": "Hello", "thinking": False, "done": False}
    assert chunks[1] == {"token": " world", "thinking": False, "done": False}
    assert chunks[2]["done"] is True
    assert chunks[2]["total_tokens"] == 10


@pytest.mark.asyncio
async def test_chat_stream_with_thinking(monkeypatch):
    """chat_stream handles thinking tokens from /api/chat."""
    lines = [
        json.dumps({"message": {"content": ""}, "thinking": "Let me think", "done": False}),
        json.dumps({"message": {"content": "Answer"}, "done": False}),
        json.dumps({"done": True, "eval_count": 5, "eval_duration": 1_000_000_000}),
    ]
    fake_resp = FakeStreamResponse(lines)
    fake_client = FakeClient(fake_resp)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: fake_client)

    client = OllamaClient()
    messages = [{"role": "user", "content": "Hi"}]

    chunks = []
    async for chunk in client.chat_stream(model="test", messages=messages, options={"think": True}):
        chunks.append(chunk)

    assert fake_client.last_request.get("think") is True
    assert chunks[0] == {"token": "Let me think", "thinking": True, "done": False}
    assert chunks[1] == {"token": "Answer", "thinking": False, "done": False}


@pytest.mark.asyncio
async def test_chat_stream_passes_options_and_stop(monkeypatch):
    """chat_stream forwards Ollama options and stop sequences."""
    lines = [
        json.dumps({"done": True, "eval_count": 0, "eval_duration": 1}),
    ]
    fake_resp = FakeStreamResponse(lines)
    fake_client = FakeClient(fake_resp)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: fake_client)

    client = OllamaClient()
    messages = [{"role": "user", "content": "Hi"}]
    options = {"temperature": 0.8, "repeat_penalty": 1.1}

    chunks = []
    async for chunk in client.chat_stream(
        model="test", messages=messages, options=options, stop=["Valentina:"]
    ):
        chunks.append(chunk)

    assert fake_client.last_request["options"] == {"temperature": 0.8, "repeat_penalty": 1.1}
    assert fake_client.last_request["stop"] == ["Valentina:"]
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/d/prg/plum-worktrees/rp-chat-api-migration && python -m pytest projects/aiserver/tests/test_ollama_chat.py -v`
Expected: FAIL — `OllamaClient` has no `chat_stream` method

**Step 3: Write the implementation**

Add after `generate_stream` method (line 88) in `projects/aiserver/ollama.py`:

```python
    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
        options: dict | None = None,
        stop: list[str] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream tokens from Ollama /api/chat. Yields same format as generate_stream.

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

                        thinking_text = data.get("thinking", "")
                        msg = data.get("message", {})
                        token_text = msg.get("content", "")

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
```

**Step 4: Run test to verify it passes**

Run: `cd /mnt/d/prg/plum-worktrees/rp-chat-api-migration && python -m pytest projects/aiserver/tests/test_ollama_chat.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
cd /mnt/d/prg/plum-worktrees/rp-chat-api-migration
git add projects/aiserver/ollama.py projects/aiserver/tests/
git commit -m "feat(aiserver): add chat_stream() method for /api/chat endpoint"
```

---

### Task 2: Rework pipeline — split template into system + post sections

**Files:**
- Modify: `projects/rp/pipeline.py:54-102` (replace `assemble_prompt`, `DEFAULT_PROMPT_TEMPLATE`, remove `_format_history`, `_split_template`)
- Create: `projects/rp/tests/__init__.py`
- Create: `projects/rp/tests/test_pipeline.py`

**Step 1: Write the failing tests**

```python
# projects/rp/tests/test_pipeline.py
import pytest
from projects.rp.pipeline import assemble_prompt, expand_variables, render_template


def _make_ctx(template="", scenario_desc="", ai_desc="", ai_personality="", ai_name="Char", user_name="User", messages=None):
    return {
        "user_card": {"card_data": {"data": {"name": user_name}}},
        "ai_card": {"card_data": {"data": {
            "name": ai_name,
            "description": ai_desc,
            "personality": ai_personality,
            "mes_example": "",
        }}},
        "scenario": {"description": scenario_desc},
        "messages": messages or [],
        "system_prompt": "",
        "prompt_template": template,
    }


def test_assemble_splits_system_and_post():
    """Template with ## system and ## post produces both prompts."""
    template = "## system\nYou are {{char}}.\n\n## post\nStay in character."
    ctx = _make_ctx(template=template, ai_name="Jessica")
    result = assemble_prompt(ctx)
    assert result["system_prompt"] == "You are Jessica."
    assert result["post_prompt"] == "Stay in character."


def test_assemble_no_post_section():
    """Template without ## post produces empty post_prompt."""
    template = "## system\nYou are {{char}}."
    ctx = _make_ctx(template=template, ai_name="Jessica")
    result = assemble_prompt(ctx)
    assert result["system_prompt"] == "You are Jessica."
    assert result["post_prompt"] == ""


def test_assemble_messages_untouched():
    """Messages pass through as structured list, not formatted as text."""
    template = "## system\nHello\n\n## post\nBye"
    msgs = [{"role": "assistant", "content": "Hi"}, {"role": "user", "content": "Hey"}]
    ctx = _make_ctx(template=template, messages=msgs)
    result = assemble_prompt(ctx)
    assert result["messages"] == msgs  # unchanged, no Name: prefix


def test_assemble_no_mes_history_variable():
    """{{mes_history}} is no longer a valid variable — not rendered."""
    template = "## system\n{{mes_history}}"
    msgs = [{"role": "user", "content": "test"}]
    ctx = _make_ctx(template=template, messages=msgs)
    result = assemble_prompt(ctx)
    # mes_history not in values, so it stays as literal or gets stripped
    assert "test" not in result["system_prompt"]


def test_expand_variables_includes_post_prompt():
    """expand_variables replaces ${char} in post_prompt too."""
    ctx = {
        "user_card": {"card_data": {"data": {"name": "Val"}}},
        "ai_card": {"card_data": {"data": {"name": "Jess"}}},
        "scenario": {"description": "park scene"},
        "system_prompt": "You are ${char}.",
        "post_prompt": "Write ${char}'s reply. Don't narrate ${user}.",
    }
    result = expand_variables(ctx)
    assert result["post_prompt"] == "Write Jess's reply. Don't narrate Val."


def test_default_template_has_system_and_post():
    """Default template (no file) produces both system and post sections."""
    ctx = _make_ctx(template="", ai_name="Jessica", ai_desc="A painter", scenario_desc="In a park")
    result = assemble_prompt(ctx)
    assert "Jessica" in result["system_prompt"] or "painter" in result["system_prompt"]
    assert result["post_prompt"]  # not empty
```

**Step 2: Run tests to verify they fail**

Run: `cd /mnt/d/prg/plum-worktrees/rp-chat-api-migration && python -m pytest projects/rp/tests/test_pipeline.py -v`
Expected: FAIL — no `post_prompt` key, `assemble_prompt` doesn't split sections

**Step 3: Rewrite pipeline**

Replace `DEFAULT_PROMPT_TEMPLATE`, `_format_history`, `_split_template`, and `assemble_prompt` in `projects/rp/pipeline.py`:

```python
DEFAULT_PROMPT_TEMPLATE = """## system
{{#scenario}}Scenario: {{scenario}}

{{/scenario}}{{#description}}Character: {{description}}

{{/description}}{{#personality}}Personality: {{personality}}

{{/personality}}{{#mes_example}}Example dialogue:
{{mes_example}}{{/mes_example}}

## post
Write only {{char}}'s next response. Stay in character. Do not narrate {{user}}'s actions."""


def _split_template(template: str) -> tuple[str, str]:
    """Split template into (system, post) sections by ## headers."""
    import re
    sections = re.split(r'^## +(system|post)\s*$', template, flags=re.MULTILINE)
    system_part = ""
    post_part = ""
    i = 0
    while i < len(sections):
        if sections[i].strip() == "system" and i + 1 < len(sections):
            system_part = sections[i + 1]
            i += 2
        elif sections[i].strip() == "post" and i + 1 < len(sections):
            post_part = sections[i + 1]
            i += 2
        else:
            if not system_part and not post_part:
                system_part = sections[i]
            i += 1
    return system_part, post_part


def assemble_prompt(ctx: dict) -> dict:
    """Build system_prompt and post_prompt from template. Messages pass through as-is."""
    ai_card = ctx.get("ai_card", {})
    scenario = ctx.get("scenario", {})
    user_card = ctx.get("user_card", {})
    ai_data = ai_card.get("card_data", {}).get("data", ai_card.get("card_data", {}))
    user_data = user_card.get("card_data", {}).get("data", user_card.get("card_data", {}))

    template = ctx.get("prompt_template", "") or DEFAULT_PROMPT_TEMPLATE

    values = {
        "scenario": scenario.get("description", ""),
        "description": ai_data.get("description", ""),
        "personality": ai_data.get("personality", ""),
        "mes_example": ai_data.get("mes_example", ""),
        "char": ai_data.get("name", "Character"),
        "user": user_data.get("name", "User"),
    }

    system_part, post_part = _split_template(template)
    ctx["system_prompt"] = render_template(system_part, values)
    ctx["post_prompt"] = render_template(post_part, values) if post_part else ""
    return ctx
```

Also update `expand_variables` to handle `post_prompt`:

```python
def expand_variables(ctx: dict) -> dict:
    """Replace ${user}, ${char}, ${scenario} in all text fields."""
    user_card = ctx.get("user_card", {})
    ai_card = ctx.get("ai_card", {})
    scenario = ctx.get("scenario", {})

    user_data = user_card.get("card_data", {}).get("data", user_card.get("card_data", {}))
    ai_data = ai_card.get("card_data", {}).get("data", ai_card.get("card_data", {}))

    replacements = {
        "${user}": user_data.get("name", "User"),
        "${char}": ai_data.get("name", "Character"),
        "${scenario}": scenario.get("description", ""),
    }

    def replace(text: str) -> str:
        for var, val in replacements.items():
            text = text.replace(var, val)
        return text

    ctx["system_prompt"] = replace(ctx.get("system_prompt", ""))
    if ctx.get("post_prompt"):
        ctx["post_prompt"] = replace(ctx["post_prompt"])
    return ctx
```

**Step 4: Run tests to verify they pass**

Run: `cd /mnt/d/prg/plum-worktrees/rp-chat-api-migration && python -m pytest projects/rp/tests/test_pipeline.py -v`
Expected: 6 PASSED

**Step 5: Commit**

```bash
cd /mnt/d/prg/plum-worktrees/rp-chat-api-migration
git add projects/rp/pipeline.py projects/rp/tests/
git commit -m "feat(rp): rework pipeline to produce system + post prompts with structured messages"
```

---

### Task 3: Update routes to use `chat_stream()`

**Files:**
- Modify: `projects/rp/routes.py:195-309` (rework `send_message`, `regenerate`, `_build_pipeline_ctx`)

**Step 1: Rewrite `_build_pipeline_ctx` and `send_message`**

Replace `_build_pipeline_ctx` (line 173-193) — remove `user_prompt` logic:

```python
    async def _build_pipeline_ctx(conv, messages):
        """Load cards, scenario, template file and run pipeline pre-hooks."""
        user_card = await db.get_card(conv["user_card_id"])
        ai_card = await db.get_card(conv["ai_card_id"])
        scenario = await db.get_scenario(conv["scenario_id"]) if conv["scenario_id"] else {}
        scenario = scenario or {}

        prompt_template = ""
        if _template_path.exists():
            prompt_template = _template_path.read_text()

        ctx = {
            "user_card": user_card,
            "ai_card": ai_card,
            "scenario": scenario,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "system_prompt": "",
            "post_prompt": "",
            "prompt_template": prompt_template,
        }
        return await _pipeline.run_pre(ctx)

    def _build_chat_messages(ctx):
        """Assemble the messages array for chat_stream()."""
        chat_messages = [{"role": "system", "content": ctx["system_prompt"]}]
        chat_messages.extend(ctx["messages"])
        if ctx.get("post_prompt"):
            chat_messages.append({"role": "system", "content": ctx["post_prompt"]})
        return chat_messages

    def _get_user_name(ctx):
        """Extract user character name for stop sequences."""
        user_data = ctx.get("user_card", {}).get("card_data", {}).get("data", ctx.get("user_card", {}).get("card_data", {}))
        return user_data.get("name", "User")
```

Replace `send_message` (line 195-246):

```python
    @app.post("/rp/conversations/{conv_id}/message")
    async def send_message(conv_id: int, req: SendMessageRequest):
        conv = await db.get_conversation(conv_id)
        if not conv:
            raise HTTPException(404, "Conversation not found")

        await db.add_message(conv_id, "user", req.content)

        messages = await db.get_messages(conv_id)
        ctx = await _build_pipeline_ctx(conv, messages)

        model = _resolve_model(conv["model"])
        scenario = ctx.get("scenario") or {}
        settings = scenario.get("settings", {})
        ollama_options = {k: v for k, v in settings.items() if k not in ("context_strategy", "max_context_tokens", "model")}

        chat_messages = _build_chat_messages(ctx)
        user_name = _get_user_name(ctx)

        async def stream():
            yield json.dumps({
                "debug_prompt": ctx["system_prompt"],
                "debug_user_prompt": ctx.get("post_prompt", ""),
                "debug_messages": ctx["messages"],
            }) + "\n"

            tokens = []
            raw = {}
            try:
                async for chunk in _ollama.chat_stream(
                    model=model, messages=chat_messages,
                    options=ollama_options, stop=[f"{user_name}:"],
                ):
                    yield json.dumps(chunk) + "\n"
                    if chunk.get("done"):
                        raw = chunk
                    elif not chunk.get("thinking"):
                        tokens.append(chunk["token"])
            except Exception as e:
                yield json.dumps({"error": str(e), "done": True}) + "\n"
                return

            try:
                response_text = "".join(tokens)
                post_ctx = {"response": response_text}
                post_ctx = await _pipeline.run_post(post_ctx)
                await db.add_message(conv_id, "assistant", post_ctx["response"], raw_response=raw)
            except Exception as e:
                yield json.dumps({"error": f"Failed to save response: {e}", "done": True}) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")
```

Replace `regenerate` (line 261-309):

```python
    @app.post("/rp/conversations/{conv_id}/regenerate")
    async def regenerate(conv_id: int):
        messages = await db.get_messages(conv_id)
        if not messages:
            raise HTTPException(400, "No messages to regenerate")
        last = messages[-1]
        if last["role"] != "assistant":
            raise HTTPException(400, "Last message is not from assistant")
        await db.delete_message(last["id"])

        conv = await db.get_conversation(conv_id)
        messages = await db.get_messages(conv_id)
        ctx = await _build_pipeline_ctx(conv, messages)

        model = _resolve_model(conv["model"])
        scenario = ctx.get("scenario") or {}
        settings = scenario.get("settings", {})
        ollama_options = {k: v for k, v in settings.items() if k not in ("context_strategy", "max_context_tokens", "model")}

        chat_messages = _build_chat_messages(ctx)
        user_name = _get_user_name(ctx)

        async def stream():
            yield json.dumps({
                "debug_prompt": ctx["system_prompt"],
                "debug_user_prompt": ctx.get("post_prompt", ""),
                "debug_messages": ctx["messages"],
            }) + "\n"

            tokens = []
            raw = {}
            try:
                async for chunk in _ollama.chat_stream(
                    model=model, messages=chat_messages,
                    options=ollama_options, stop=[f"{user_name}:"],
                ):
                    yield json.dumps(chunk) + "\n"
                    if chunk.get("done"):
                        raw = chunk
                    elif not chunk.get("thinking"):
                        tokens.append(chunk["token"])
            except Exception as e:
                yield json.dumps({"error": str(e), "done": True}) + "\n"
                return
            try:
                response_text = "".join(tokens)
                post_ctx = {"response": response_text}
                post_ctx = await _pipeline.run_post(post_ctx)
                await db.add_message(conv_id, "assistant", post_ctx["response"], raw_response=raw)
            except Exception as e:
                yield json.dumps({"error": f"Failed to save response: {e}", "done": True}) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")
```

**Step 2: Verify server starts**

Run: `cd /mnt/d/prg/plum-worktrees/rp-chat-api-migration/projects/aiserver && DATABASE_URL='postgresql://plum:Simatai0!@localhost/plum' timeout 5 python main.py 2>&1 || true`
Expected: Server starts without import errors (may timeout, that's fine)

**Step 3: Commit**

```bash
cd /mnt/d/prg/plum-worktrees/rp-chat-api-migration
git add projects/rp/routes.py
git commit -m "feat(rp): switch routes from generate_stream to chat_stream with structured messages"
```

---

### Task 4: Update prompt.md template

**Files:**
- Modify: `projects/rp/prompt.md`

**Step 1: Replace template content**

```markdown
## system

You are writing an immersive, engaging roleplay with {{user}} where you are {{char}}.

{{#scenario}}Scenario: {{scenario}}

{{/scenario}}{{#description}}Character: {{description}}

{{/description}}{{#personality}}Personality: {{personality}}

{{/personality}}{{#mes_example}}
Example dialogue, do not repeat:
{{mes_example}}
{{/mes_example}}

The genres are: romance, slice of life
Tones are: introspective, cute, feminine
The writing style is: third person, vivid sensory detail and inner monologue
Frequently reference physical character descriptions.
Use graphic, verbose and vivid detail for actions.
Respond authentically based on character believability
Continue the story, prefer "yes, and" and "no, but"

## post

Write only {{char}}'s next response in this collaborative story.
Keep writing in character. Stay in the current scene.
Do not narrate {{user}}'s actions or dialogue.
Write 2-3 paragraphs per response.
Leave space for {{user}} to respond.
```

**Step 2: Commit**

```bash
cd /mnt/d/prg/plum-worktrees/rp-chat-api-migration
git add projects/rp/prompt.md
git commit -m "feat(rp): migrate prompt template to system + post sections for /api/chat"
```

---

### Task 5: Manual smoke test

**Step 1: Start the server**

```bash
cd /mnt/d/prg/plum-worktrees/rp-chat-api-migration/projects/aiserver
source .venv/bin/activate
DATABASE_URL='postgresql://plum:Simatai0!@localhost/plum' python main.py
```

**Step 2: Open UI and test**

Open `http://localhost:8080/rp/`. Create a new conversation or use existing one. Send a message and verify:

- [ ] No name duplication in AI response (no "Jessica Klein: Jessica Klein:")
- [ ] AI responds with one turn only (doesn't generate user's lines)
- [ ] Streaming works (tokens appear progressively)
- [ ] Under the Hood > System Prompt shows the system section
- [ ] Under the Hood > User Prompt shows the post-history instruction
- [ ] Regenerate button works
- [ ] Thinking toggle works (if model supports it)

**Step 3: Commit any fixes found during smoke test**

---

### Task 6: Update DESIGN.md

**Files:**
- Modify: `projects/rp/DESIGN.md`

**Step 1: Update relevant sections**

- Change "Streaming Protocol" to note `/api/chat` instead of `/api/generate`
- Update "Prompt Template" section: document `## system` + `## post` (replace `## prompt`)
- Remove references to `{{mes_history}}` variable
- Add `## post` to "Template Sections"
- Update "How It Works" flow diagram
- Add stop sequences to pipeline docs

**Step 2: Commit**

```bash
cd /mnt/d/prg/plum-worktrees/rp-chat-api-migration
git add projects/rp/DESIGN.md
git commit -m "docs(rp): update DESIGN.md for /api/chat migration"
```
