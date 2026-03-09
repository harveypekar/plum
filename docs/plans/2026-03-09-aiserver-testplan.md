# aiserver Test Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add unit tests for aiserver covering config logic, OllamaClient error handling, streaming protocol, and endpoint behavior — all runnable without a live server or Ollama.

**Tech Stack:** pytest, pytest-asyncio, respx (httpx mocking)

---

### Step 0: Switch to the worktree

```bash
cd "$(git worktree list | grep aiserver-design | awk '{print $1}')"
```

---

### Task 1: Install Test Dependencies

**Files:**
- Modify: `projects/aiserver/requirements.txt`

**Step 1: Add test dependencies**

Append to `requirements.txt`:

```txt
pytest>=9.0.0
pytest-asyncio>=1.0.0
respx>=0.22.0
```

**Step 2: Install**

```bash
cd projects/aiserver
source .venv/bin/activate
pip install -r requirements.txt
```

**Step 3: Commit**

```bash
git add projects/aiserver/requirements.txt
git commit -m "chore(aiserver): add test dependencies"
```

---

### Task 2: Config Unit Tests

**Files:**
- Create: `projects/aiserver/test_config.py`

**Step 1: Write tests for resolve_model and merge_options**

Test cases:
- `resolve_model("q8")` returns `"qwen3:8b"` (alias hit)
- `resolve_model("q06")` returns `"qwen3:0.6b"` (alias hit)
- `resolve_model(None)` returns the resolved default model
- `resolve_model("llama3:8b")` passes through unknown names unchanged
- `merge_options(None)` returns all defaults
- `merge_options(GenerateOptions(temperature=0.3))` overrides only temperature, keeps rest
- `merge_options(GenerateOptions(temperature=0.3, top_k=10))` overrides multiple fields
- Verify `think` field is included in merged output

Use the real `Config` class with the actual `config.json` file — these are pure logic tests.

**Step 2: Run tests**

```bash
cd projects/aiserver
pytest test_config.py -v
```

**Step 3: Commit**

```bash
git add projects/aiserver/test_config.py
git commit -m "test(aiserver): add unit tests for config alias resolution and option merging"
```

---

### Task 3: OllamaClient Unit Tests

**Files:**
- Create: `projects/aiserver/test_ollama.py`

**Step 1: Write tests using respx to mock httpx**

Use `respx` to mock Ollama HTTP responses. Test cases:

**Streaming protocol:**
- Mock a multi-chunk NDJSON response. Verify yielded dicts have correct `token`, `thinking`, `done` keys.
- Mock a response with both thinking and response tokens. Verify thinking chunks have `"thinking": True`.
- Mock a done chunk with `eval_count` and `eval_duration`. Verify `tokens_per_second` calculation (nanosecond conversion: `eval_duration / 1e9`).

**Error handling:**
- Mock a connection error (`respx.mock` + `httpx.ConnectError`). Verify `OllamaError` is raised with the base URL in the message.
- Mock a non-200 response (e.g., 404). Verify `OllamaError` is raised with status code and body.
- Mock a timeout. Verify `OllamaError` is raised (not raw `httpx.TimeoutException`).

**generate() convenience method:**
- Mock a response with thinking + response tokens. Verify only response tokens are returned, thinking discarded.

**options mutation safety:**
- Pass an `options` dict with `"think": True`. Call `generate_stream`. Verify the original dict is not mutated (the `"think"` key should still exist).

**is_available / list_models:**
- Mock `/api/tags` returning 200 with models. Verify `is_available()` returns True and `list_models()` returns model names.
- Mock `/api/tags` connection error. Verify `is_available()` returns False and `list_models()` returns `[]`.

**Step 2: Run tests**

```bash
cd projects/aiserver
pytest test_ollama.py -v
```

**Step 3: Commit**

```bash
git add projects/aiserver/test_ollama.py
git commit -m "test(aiserver): add OllamaClient unit tests with mocked HTTP"
```

---

### Task 4: Endpoint Unit Tests (ASGI)

**Files:**
- Create: `projects/aiserver/test_endpoints.py`

**Step 1: Write tests using httpx ASGITransport**

Use `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))` to test endpoints without a live server. Mock `OllamaClient` methods where needed.

Test cases:

**/defaults:**
- GET `/defaults`. Verify response has `default_model`, `aliases`, `default_options` with correct values from config.

**/health:**
- Mock `ollama.is_available()` returning True and `ollama.list_models()` returning models. Verify `status: "ok"` and `ollama_connected: true`.
- Mock `ollama.is_available()` returning False. Verify `status: "ollama_unavailable"` and `ollama_connected: false`.

**/stats:**
- With empty request log: verify `total_requests: 0`, `avg_tokens_per_second: 0`.
- Prepopulate `request_log` with test entries. Verify counts and TPS calculation.
- Add an entry with `latency: 0` and verify it's excluded from TPS average (no division by zero).

**/generate error path:**
- Mock `ollama.generate_stream` to raise `OllamaError`. Verify the NDJSON stream contains `{"error": "...", "done": true}`.
- Verify `active_streams` returns to 0 after the stream completes.

**Step 2: Run tests**

```bash
cd projects/aiserver
pytest test_endpoints.py -v
```

**Step 3: Commit**

```bash
git add projects/aiserver/test_endpoints.py
git commit -m "test(aiserver): add ASGI endpoint tests without live server"
```

---

### Task 5: Run Full Suite and Commit

**Step 1: Run all tests together**

```bash
cd projects/aiserver
pytest test_config.py test_ollama.py test_endpoints.py -v
```

All tests must pass.

**Step 2: Push and update PR**

```bash
git push
```
