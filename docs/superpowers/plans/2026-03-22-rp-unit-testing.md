# RP Unit Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add comprehensive unit tests for all pure-logic modules in the RP project to catch regressions.

**Architecture:** Three phases — foundation modules (cards, context, db hashes), pipeline expansion, and parsing/scene-state extraction. All tests are pure logic; no database or network mocking. Scene state prompt-building is extracted from `routes.py` into a testable module.

**Tech Stack:** pytest, Pillow (for card PNG round-trip tests)

---

## File Structure

- Create: `projects/rp/tests/test_cards.py` — PNG parse/export round-trip, extract_name
- Create: `projects/rp/tests/test_context.py` — SlidingWindow.fit, get_strategy
- Create: `projects/rp/tests/test_db_hashes.py` — hash stability, combo hashes
- Modify: `projects/rp/tests/test_pipeline.py` — expand with render_template edges, clean_response, scene state injection, conditional sections, DEFAULT_PROMPT_TEMPLATE, _split_template
- Create: `projects/rp/tests/test_mcp_parsing.py` — TOOL_CALL_RE, parse_tool_calls
- Create: `projects/rp/scene_state.py` — extracted `build_scene_state_prompt` + `clean_scene_state_response`
- Create: `projects/rp/tests/test_scene_state.py` — prompt building, response cleaning

---

## Phase 1: Foundation Modules

### Task 1: Card PNG Round-Trip Tests

**Files:**
- Test: `projects/rp/tests/test_cards.py`
- Source: `projects/rp/cards.py`

- [ ] **Step 1: Write the tests**

```python
import pytest
from projects.rp.cards import parse_card_png, export_card_png, extract_name


def _make_card_data(name="TestChar", description="A test character"):
    return {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": name,
            "description": description,
            "personality": "brave",
            "mes_example": "",
            "first_mes": "Hello!",
            "system_prompt": "",
        },
    }


class TestParseExportRoundTrip:
    def test_round_trip_preserves_card_data(self):
        original = _make_card_data()
        png = export_card_png(original)
        parsed, avatar_bytes = parse_card_png(png)
        assert parsed["data"]["name"] == "TestChar"
        assert parsed["data"]["description"] == "A test character"
        assert parsed["spec"] == "chara_card_v2"

    def test_round_trip_with_unicode(self):
        original = _make_card_data(name="Ëlaria", description="She wields a flaming sörd")
        png = export_card_png(original)
        parsed, _ = parse_card_png(png)
        assert parsed["data"]["name"] == "Ëlaria"
        assert "sörd" in parsed["data"]["description"]

    def test_round_trip_with_avatar(self):
        original = _make_card_data()
        # Create a small valid PNG to use as avatar
        placeholder_png = export_card_png({"data": {"name": "x"}})
        png = export_card_png(original, avatar_png=placeholder_png)
        parsed, returned_png = parse_card_png(png)
        assert parsed["data"]["name"] == "TestChar"
        assert len(returned_png) > 0

    def test_parse_raises_on_plain_png(self):
        from PIL import Image
        import io
        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        with pytest.raises(ValueError, match="no 'chara' tEXt chunk"):
            parse_card_png(buf.getvalue())

    def test_export_no_avatar_creates_placeholder(self):
        original = _make_card_data()
        png = export_card_png(original)
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(png))
        assert img.size == (400, 600)


class TestExtractName:
    def test_v2_format(self):
        assert extract_name({"data": {"name": "Jessica"}}) == "Jessica"

    def test_flat_format(self):
        assert extract_name({"name": "Sol"}) == "Sol"

    def test_v2_missing_name_falls_to_top_level(self):
        assert extract_name({"data": {}, "name": "Fallback"}) == "Fallback"

    def test_completely_empty(self):
        assert extract_name({}) == "Unknown"

    def test_v2_no_name_no_fallback(self):
        assert extract_name({"data": {}}) == "Unknown"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /mnt/d/prg/plum && python -m pytest projects/rp/tests/test_cards.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add projects/rp/tests/test_cards.py
git commit -m "test(rp): add card PNG round-trip and extract_name tests"
```

---

### Task 2: Context Strategy Tests

**Files:**
- Test: `projects/rp/tests/test_context.py`
- Source: `projects/rp/context.py`

- [ ] **Step 1: Write the tests**

```python
import pytest
from projects.rp.context import SlidingWindow, get_strategy


def _msg(role, content):
    return {"role": role, "content": content}


class TestSlidingWindow:
    def test_empty_messages(self):
        sw = SlidingWindow()
        assert sw.fit([], 1000) == []

    def test_all_fit(self):
        msgs = [_msg("assistant", "Hello"), _msg("user", "Hi"), _msg("assistant", "How?")]
        result = SlidingWindow().fit(msgs, 10000)
        assert result == msgs

    def test_keeps_first_message_always(self):
        greeting = _msg("assistant", "A" * 100)
        old = _msg("user", "B" * 100)
        recent = _msg("assistant", "C" * 50)
        # Budget: greeting (25 tokens) + recent (12 tokens) = 37, old would push to 62
        result = SlidingWindow().fit([greeting, old, recent], 40)
        assert result[0] == greeting
        assert recent in result
        assert old not in result

    def test_drops_oldest_not_newest(self):
        msgs = [
            _msg("assistant", "greeting"),
            _msg("user", "msg1"),
            _msg("user", "msg2"),
            _msg("user", "msg3"),
            _msg("assistant", "msg4"),
        ]
        # Very tight budget: should keep greeting + most recent
        result = SlidingWindow().fit(msgs, 10)
        assert result[0] == msgs[0]  # greeting kept
        assert result[-1] == msgs[-1]  # newest kept

    def test_custom_token_counter(self):
        msgs = [_msg("assistant", "hi"), _msg("user", "hello world")]
        # Counter that counts words
        result = SlidingWindow().fit(msgs, 3, token_counter=lambda t: len(t.split()))
        assert len(result) == 2  # 1 word + 2 words = 3, fits

    def test_custom_counter_tight(self):
        msgs = [_msg("assistant", "hi"), _msg("user", "hello world")]
        # Budget of 1 word — only greeting fits
        result = SlidingWindow().fit(msgs, 1, token_counter=lambda t: len(t.split()))
        assert len(result) == 1
        assert result[0] == msgs[0]

    def test_single_message(self):
        msgs = [_msg("assistant", "Hello!")]
        result = SlidingWindow().fit(msgs, 1000)
        assert result == msgs

    def test_single_message_over_budget(self):
        """Greeting is always kept even if it alone exceeds budget."""
        msgs = [_msg("assistant", "A" * 10000)]
        result = SlidingWindow().fit(msgs, 1)
        assert result == msgs

    def test_oversized_message_blocks_all_older(self):
        """A large message causes break (not continue), dropping older messages too."""
        msgs = [
            _msg("assistant", "greet"),
            _msg("user", "old short"),
            _msg("user", "X" * 10000),
            _msg("assistant", "recent short"),
        ]
        result = SlidingWindow().fit(msgs, 20)
        assert result[0] == msgs[0]       # greeting always kept
        assert msgs[-1] in result          # newest kept (fits)
        assert msgs[1] not in result       # blocked by oversized msg before it


class TestGetStrategy:
    def test_returns_sliding_window(self):
        s = get_strategy("sliding_window")
        assert isinstance(s, SlidingWindow)

    def test_unknown_falls_back_to_sliding_window(self):
        s = get_strategy("nonexistent_strategy")
        assert isinstance(s, SlidingWindow)

    def test_default_is_sliding_window(self):
        s = get_strategy()
        assert isinstance(s, SlidingWindow)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /mnt/d/prg/plum && python -m pytest projects/rp/tests/test_context.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add projects/rp/tests/test_context.py
git commit -m "test(rp): add context strategy unit tests"
```

---

### Task 3: DB Hash Function Tests

**Files:**
- Test: `projects/rp/tests/test_db_hashes.py`
- Source: `projects/rp/db.py` (only the pure hash functions)

- [ ] **Step 1: Write the tests**

```python
from projects.rp.db import (
    _hash_data,
    compute_card_hash,
    compute_scenario_hash,
    compute_combo_hash,
)


class TestHashData:
    def test_deterministic(self):
        assert _hash_data({"a": 1}) == _hash_data({"a": 1})

    def test_key_order_irrelevant(self):
        assert _hash_data({"a": 1, "b": 2}) == _hash_data({"b": 2, "a": 1})

    def test_different_data_different_hash(self):
        assert _hash_data({"a": 1}) != _hash_data({"a": 2})

    def test_returns_16_char_hex(self):
        h = _hash_data("test")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


class TestComputeCardHash:
    def _card(self, **overrides):
        data = {
            "description": "tall",
            "personality": "kind",
            "system_prompt": "",
            "first_mes": "Hi",
            "mes_example": "",
        }
        data.update(overrides)
        return {"card_data": {"data": data}}

    def test_same_card_same_hash(self):
        c = self._card()
        assert compute_card_hash(c) == compute_card_hash(c)

    def test_ignores_name(self):
        c1 = self._card()
        c1["card_data"]["data"]["name"] = "Alice"
        c2 = self._card()
        c2["card_data"]["data"]["name"] = "Bob"
        assert compute_card_hash(c1) == compute_card_hash(c2)

    def test_description_change_changes_hash(self):
        c1 = self._card(description="tall")
        c2 = self._card(description="short")
        assert compute_card_hash(c1) != compute_card_hash(c2)

    def test_personality_change_changes_hash(self):
        c1 = self._card(personality="kind")
        c2 = self._card(personality="rude")
        assert compute_card_hash(c1) != compute_card_hash(c2)

    def test_flat_card_format(self):
        """Cards without nested 'data' key still hash."""
        card = {"card_data": {"description": "flat", "personality": "x",
                              "system_prompt": "", "first_mes": "", "mes_example": ""}}
        h = compute_card_hash(card)
        assert len(h) == 16


class TestComputeScenarioHash:
    def test_none_scenario(self):
        h = compute_scenario_hash(None)
        assert len(h) == 16

    def test_same_scenario_same_hash(self):
        s = {"description": "park", "first_message": "You arrive."}
        assert compute_scenario_hash(s) == compute_scenario_hash(s)

    def test_description_change(self):
        s1 = {"description": "park", "first_message": "Hi"}
        s2 = {"description": "beach", "first_message": "Hi"}
        assert compute_scenario_hash(s1) != compute_scenario_hash(s2)

    def test_empty_scenario(self):
        h = compute_scenario_hash({})
        assert len(h) == 16


class TestComputeComboHash:
    def test_deterministic(self):
        h = compute_combo_hash("abc", "def", "model1")
        assert h == compute_combo_hash("abc", "def", "model1")

    def test_model_change_changes_hash(self):
        h1 = compute_combo_hash("abc", "def", "model1")
        h2 = compute_combo_hash("abc", "def", "model2")
        assert h1 != h2

    def test_card_hash_change(self):
        h1 = compute_combo_hash("abc", "def", "m")
        h2 = compute_combo_hash("xyz", "def", "m")
        assert h1 != h2
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /mnt/d/prg/plum && python -m pytest projects/rp/tests/test_db_hashes.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add projects/rp/tests/test_db_hashes.py
git commit -m "test(rp): add hash function stability tests"
```

---

## Phase 2: Pipeline Expansion

### Task 4: Expand Pipeline Tests

**Files:**
- Modify: `projects/rp/tests/test_pipeline.py`
- Source: `projects/rp/pipeline.py`

- [ ] **Step 1: Add render_template edge case tests**

Append to `projects/rp/tests/test_pipeline.py`:

```python
from projects.rp.pipeline import (
    _split_template, clean_response, Pipeline, DEFAULT_PROMPT_TEMPLATE,
    apply_context_strategy,
)


class TestRenderTemplate:
    def test_simple_substitution(self):
        assert render_template("Hello {{name}}", {"name": "World"}) == "Hello World"

    def test_conditional_section_truthy(self):
        result = render_template("{{#name}}Hi {{name}}{{/name}}", {"name": "Val"})
        assert result == "Hi Val"

    def test_conditional_section_falsy(self):
        result = render_template("{{#name}}Hi {{name}}{{/name}}", {"name": ""})
        assert result == ""

    def test_conditional_section_missing(self):
        result = render_template("{{#name}}Hi {{name}}{{/name}}", {})
        assert result == ""

    def test_multiple_sections(self):
        tmpl = "{{#a}}A:{{a}}{{/a}} {{#b}}B:{{b}}{{/b}}"
        result = render_template(tmpl, {"a": "1", "b": ""})
        assert "A:1" in result
        assert "B:" not in result

    def test_nested_var_in_section(self):
        tmpl = "{{#desc}}Character: {{desc}}\n{{/desc}}{{#user}}Player: {{user}}{{/user}}"
        result = render_template(tmpl, {"desc": "tall", "user": "Val"})
        assert "Character: tall" in result
        assert "Player: Val" in result

    def test_unreferenced_var_left_alone(self):
        result = render_template("{{unknown}} stays", {})
        assert "{{unknown}}" in result

    def test_empty_template(self):
        assert render_template("", {"name": "x"}) == ""

    def test_multiline_section(self):
        tmpl = "{{#bio}}Bio:\n{{bio}}\nEnd{{/bio}}"
        result = render_template(tmpl, {"bio": "A brave warrior"})
        assert "Bio:\nA brave warrior\nEnd" in result
```

- [ ] **Step 2: Add _split_template tests**

```python
class TestSplitTemplate:
    def test_system_and_post(self):
        sys, post = _split_template("## system\nSys content\n\n## post\nPost content")
        assert "Sys content" in sys
        assert "Post content" in post

    def test_system_only(self):
        sys, post = _split_template("## system\nOnly system")
        assert "Only system" in sys
        assert post == ""

    def test_post_only(self):
        sys, post = _split_template("## post\nOnly post")
        assert sys == ""
        assert "Only post" in post

    def test_no_markers(self):
        sys, post = _split_template("Just plain text")
        assert "Just plain text" in sys
        assert post == ""

    def test_extra_whitespace_in_markers(self):
        sys, post = _split_template("##  system\nSys\n\n##  post\nPost")
        assert "Sys" in sys
        assert "Post" in post
```

- [ ] **Step 3: Add expand_variables tests including scene state injection**

```python
class TestExpandVariables:
    def _ctx(self, system="", post="", scene_state="",
             user_name="User", ai_name="Char", scenario_desc=""):
        return {
            "user_card": {"card_data": {"data": {"name": user_name}}},
            "ai_card": {"card_data": {"data": {"name": ai_name}}},
            "scenario": {"description": scenario_desc},
            "system_prompt": system,
            "post_prompt": post,
            "scene_state": scene_state,
        }

    def test_replaces_user_and_char(self):
        ctx = self._ctx(system="Hi ${user} and ${char}", user_name="Val", ai_name="Jess")
        result = expand_variables(ctx)
        assert result["system_prompt"] == "Hi Val and Jess"

    def test_replaces_scenario(self):
        ctx = self._ctx(system="Scene: ${scenario}", scenario_desc="a park")
        result = expand_variables(ctx)
        assert result["system_prompt"] == "Scene: a park"

    def test_scene_state_injected_into_post(self):
        ctx = self._ctx(post="Stay in character.", scene_state="Location: park\nMood: tense")
        result = expand_variables(ctx)
        assert "Current Scene State" in result["post_prompt"]
        assert "Location: park" in result["post_prompt"]

    def test_empty_scene_state_not_injected(self):
        ctx = self._ctx(post="Stay in character.", scene_state="")
        result = expand_variables(ctx)
        assert "Scene State" not in result["post_prompt"]

    def test_whitespace_only_scene_state_not_injected(self):
        ctx = self._ctx(post="Stay in character.", scene_state="   \n  ")
        result = expand_variables(ctx)
        assert "Scene State" not in result["post_prompt"]

    def test_empty_post_prompt_still_gets_scene_state(self):
        ctx = self._ctx(system="${char} says hi", post="", ai_name="Jess",
                        scene_state="Location: X")
        result = expand_variables(ctx)
        assert result["system_prompt"] == "Jess says hi"
        assert "Location: X" in result["post_prompt"]
```

- [ ] **Step 4: Add clean_response tests**

```python
class TestCleanResponse:
    def test_strips_whitespace(self):
        ctx = {"response": "  hello  ", "ai_name": ""}
        assert clean_response(ctx)["response"] == "hello"

    def test_strips_ai_name_prefix(self):
        ctx = {"response": "Jessica: She smiled.", "ai_name": "Jessica"}
        assert clean_response(ctx)["response"] == "She smiled."

    def test_strips_full_name_prefix(self):
        ctx = {"response": "Jessica Klein: She smiled.", "ai_name": "Jessica Klein"}
        assert clean_response(ctx)["response"] == "She smiled."

    def test_no_strip_when_name_is_substring(self):
        ctx = {"response": "Jessica smiled.", "ai_name": "Jessica"}
        # "Jessica smiled." starts with "Jessica" but next char is " " not ": "
        assert clean_response(ctx)["response"] == "Jessica smiled."

    def test_no_ai_name(self):
        ctx = {"response": "Hello", "ai_name": ""}
        assert clean_response(ctx)["response"] == "Hello"

    def test_empty_response(self):
        ctx = {"response": "", "ai_name": "Test"}
        assert clean_response(ctx)["response"] == ""
```

- [ ] **Step 5: Add DEFAULT_PROMPT_TEMPLATE integration test**

```python
class TestDefaultTemplate:
    def test_default_template_renders_with_full_card(self):
        ctx = _make_ctx(
            template="",
            ai_name="Jessica",
            ai_desc="A painter from Berlin",
            ai_personality="Thoughtful and reserved",
            scenario_desc="Meeting at a gallery",
            user_name="Val",
        )
        ctx["user_card"]["card_data"]["data"]["description"] = "An art collector"
        result = assemble_prompt(ctx)
        assert "Jessica" in result["system_prompt"]
        assert "painter" in result["system_prompt"]
        assert "gallery" in result["system_prompt"]
        assert result["post_prompt"]  # post section is non-empty

    def test_default_template_omits_empty_sections(self):
        ctx = _make_ctx(template="", ai_name="Sol", ai_desc="", scenario_desc="")
        result = assemble_prompt(ctx)
        assert "Scenario:" not in result["system_prompt"]
```

- [ ] **Step 6: Add Pipeline class test**

```python
import asyncio

class TestPipelineClass:
    def test_pre_hooks_run_in_order(self):
        p = Pipeline()
        log = []
        p.add_pre(lambda ctx: (log.append("a"), ctx)[1])
        p.add_pre(lambda ctx: (log.append("b"), ctx)[1])
        asyncio.run(p.run_pre({}))
        assert log == ["a", "b"]

    def test_post_hooks_run_in_order(self):
        p = Pipeline()
        log = []
        p.add_post(lambda ctx: (log.append("x"), ctx)[1])
        p.add_post(lambda ctx: (log.append("y"), ctx)[1])
        asyncio.run(p.run_post({}))
        assert log == ["x", "y"]

    def test_async_hook(self):
        p = Pipeline()

        async def async_hook(ctx):
            ctx["async_ran"] = True
            return ctx

        p.add_pre(async_hook)
        result = asyncio.run(p.run_pre({}))
        assert result["async_ran"] is True
```

- [ ] **Step 7: Run all pipeline tests**

Run: `cd /mnt/d/prg/plum && python -m pytest projects/rp/tests/test_pipeline.py -v`
Expected: All tests PASS (original 6 + new tests)

- [ ] **Step 8: Commit**

```bash
git add projects/rp/tests/test_pipeline.py
git commit -m "test(rp): expand pipeline tests with template, clean_response, scene state"
```

---

## Phase 3: Parsing & Scene State

### Task 5: MCP Tool Call Parsing Tests

**Files:**
- Test: `projects/rp/tests/test_mcp_parsing.py`
- Source: `projects/rp/mcp_client.py`

- [ ] **Step 1: Write the tests**

```python
import re
from projects.rp.mcp_client import TOOL_CALL_RE, MCPToolRouter


class TestToolCallRegex:
    def test_simple_match(self):
        m = TOOL_CALL_RE.search('[TOOL: search("hello")]')
        assert m
        assert m.group(1) == "search"
        assert m.group(2) == '"hello"'

    def test_single_quotes(self):
        m = TOOL_CALL_RE.search("[TOOL: search('hello')]")
        assert m
        assert m.group(1) == "search"

    def test_no_quotes(self):
        m = TOOL_CALL_RE.search("[TOOL: lookup(42)]")
        assert m
        assert m.group(2) == "42"

    def test_tool_in_text(self):
        text = "Let me check that. [TOOL: search(\"weather\")] Here's what I found."
        m = TOOL_CALL_RE.search(text)
        assert m
        assert m.group(1) == "search"

    def test_multiple_tools(self):
        text = '[TOOL: search("a")] and [TOOL: lookup("b")]'
        matches = list(TOOL_CALL_RE.finditer(text))
        assert len(matches) == 2
        assert matches[0].group(1) == "search"
        assert matches[1].group(1) == "lookup"

    def test_no_match(self):
        assert TOOL_CALL_RE.search("no tools here") is None

    def test_empty_arg(self):
        m = TOOL_CALL_RE.search('[TOOL: search()]')
        assert m
        assert m.group(2) == ""

    def test_space_after_colon(self):
        m = TOOL_CALL_RE.search('[TOOL:  search("x")]')
        assert m


class TestParseToolCalls:
    def setup_method(self):
        self.router = MCPToolRouter()
        # Register a fake tool schema
        self.router._tools["search"] = ("test_server", {
            "name": "search",
            "description": "Search for things",
            "parameters": {"properties": {"query": {"type": "string"}}},
        })

    def test_parses_known_tool(self):
        results = self.router.parse_tool_calls('[TOOL: search("hello world")]')
        assert len(results) == 1
        name, args, full = results[0]
        assert name == "search"
        assert args == {"query": "hello world"}

    def test_parses_unknown_tool_defaults_to_query(self):
        results = self.router.parse_tool_calls('[TOOL: unknown("test")]')
        assert len(results) == 1
        assert results[0][1] == {"query": "test"}

    def test_strips_quotes_from_arg(self):
        results = self.router.parse_tool_calls('[TOOL: search("quoted")]')
        assert results[0][1]["query"] == "quoted"

    def test_returns_full_match_string(self):
        text = '[TOOL: search("x")]'
        results = self.router.parse_tool_calls(text)
        assert results[0][2] == text

    def test_no_tools_returns_empty(self):
        assert self.router.parse_tool_calls("plain text") == []

    def test_uses_first_param_from_schema(self):
        self.router._tools["custom"] = ("srv", {
            "name": "custom",
            "description": "Custom tool",
            "parameters": {"properties": {"url": {"type": "string"}, "depth": {"type": "int"}}},
        })
        results = self.router.parse_tool_calls('[TOOL: custom("example.com")]')
        assert results[0][1] == {"url": "example.com"}


class TestToolDescriptions:
    def test_no_tools_returns_empty(self):
        r = MCPToolRouter()
        assert r.get_tool_descriptions() == ""

    def test_has_tools_returns_formatted(self):
        r = MCPToolRouter()
        r._tools["search"] = ("srv", {"name": "search", "description": "Find stuff", "parameters": {}})
        desc = r.get_tool_descriptions()
        assert "search" in desc
        assert "Find stuff" in desc
        assert "[TOOL:" in desc
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /mnt/d/prg/plum && python -m pytest projects/rp/tests/test_mcp_parsing.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add projects/rp/tests/test_mcp_parsing.py
git commit -m "test(rp): add MCP tool call parsing tests"
```

---

### Task 6: Extract Scene State Functions

**Files:**
- Create: `projects/rp/scene_state.py`
- Modify: `projects/rp/routes.py:575-650` (call extracted functions)

- [ ] **Step 1: Create scene_state.py with extracted pure functions**

```python
"""Scene state prompt building and response cleaning — extracted for testability."""


def build_scene_state_prompt(messages: list[dict], previous_state: str = "",
                              ai_name: str = "Character", user_name: str = "User",
                              ai_personality: str = "",
                              scenario_context: str = "") -> str:
    """Build the prompt sent to the LLM to generate/update scene state."""
    history = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    prev_section = ""
    if previous_state.strip():
        prev_section = (
            "PREVIOUS SCENE STATE (carry forward anything not contradicted by new messages):\n"
            f"{previous_state.strip()}\n\n"
        )
    personality_hint = ""
    if ai_personality:
        short = ai_personality[:200].rsplit(" ", 1)[0]
        personality_hint = f"{ai_name}'s personality: {short}\n\n"
    scenario_section = ""
    if scenario_context.strip():
        scenario_section = f"Scenario context: {scenario_context.strip()}\n\n"
    initial = not previous_state.strip() and len(messages) <= 1
    if initial:
        instruction = (
            "This is the opening of a new scene. Establish the INITIAL scene state "
            "based on the scenario context and first message below.\n\n"
        )
    else:
        instruction = (
            "Below are the most recent messages. UPDATE the scene state based on what changed.\n"
            "Keep everything from the previous state that still holds true. "
            "Only change what the new messages contradict or add.\n\n"
        )
    return (
        f"{prev_section}"
        f"{personality_hint}"
        f"{scenario_section}"
        f"{instruction}"
        f"Characters: {ai_name} (AI) and {user_name} (user).\n\n"
        "Format — one short line per category:\n"
        "Location: (where are they right now)\n"
        f"Clothing: (what {ai_name} and {user_name} are currently wearing RIGHT NOW — track removals: if a character undressed, they are naked, not still wearing the old clothes. Write 'naked' or 'nude' when appropriate)\n"
        "Restraints: (describe the specific tie/pattern AND what it practically limits — e.g. 'wrists behind back — no free hand use' — or 'none')\n"
        "Position: (posture, who is where, physical contact)\n"
        "Props: (objects currently in play)\n"
        "Mood: (emotional atmosphere right now)\n"
        "ONLY state facts explicitly shown or described in the messages. Do NOT invent or assume details not present.\n"
        "If clothing is not mentioned, write 'not described' — do NOT guess.\n"
        "No narration, no story, no explanation. Just the current facts.\n\n"
        f"Recent messages:\n{history}"
    )


def clean_scene_state_response(raw: str) -> str:
    """Clean up LLM scene state output: strip think tags, remove empty/none lines."""
    clean = raw.strip()
    if "<think>" in clean:
        clean = clean.split("</think>")[-1].strip()
    lines = []
    for line in clean.splitlines():
        if ":" in line:
            value = line.split(":", 1)[1].strip().lower()
            if value and value != "none" and value != "n/a":
                lines.append(line)
        elif line.strip():
            lines.append(line)
    return "\n".join(lines)
```

- [ ] **Step 2: Update routes.py to import from scene_state.py**

In `routes.py`, inside the `setup()` function (line 38), replace the `_build_scene_state_prompt` body with a delegation to the extracted module, and similarly for the cleaning logic in `_generate_scene_state`. The functions in `routes.py` become thin wrappers:

In `_build_scene_state_prompt` (line 575-625): replace the body with:
```python
    def _build_scene_state_prompt(messages, previous_state="",
                                   ai_name="Character", user_name="User",
                                   ai_personality="", scenario_context=""):
        from .scene_state import build_scene_state_prompt
        return build_scene_state_prompt(messages, previous_state, ai_name, user_name,
                                         ai_personality, scenario_context)
```

In `_generate_scene_state` (line 627-650): replace the line-filtering logic with:
```python
        from .scene_state import clean_scene_state_response
        # ... keep the ollama.generate call ...
        return clean_scene_state_response(result)
```

- [ ] **Step 3: Run existing tests to verify no regression**

Run: `cd /mnt/d/prg/plum && python -m pytest projects/rp/tests/ -v`
Expected: All existing tests still PASS

- [ ] **Step 4: Commit**

```bash
git add projects/rp/scene_state.py projects/rp/routes.py
git commit -m "refactor(rp): extract scene state functions for testability"
```

---

### Task 7: Scene State Tests

**Files:**
- Test: `projects/rp/tests/test_scene_state.py`
- Source: `projects/rp/scene_state.py`

- [ ] **Step 1: Write the tests**

```python
from projects.rp.scene_state import build_scene_state_prompt, clean_scene_state_response


def _msgs(*pairs):
    """Shorthand: _msgs(("user", "hi"), ("assistant", "hello"))"""
    return [{"role": r, "content": c} for r, c in pairs]


class TestBuildSceneStatePrompt:
    def test_initial_scene_uses_establish_instruction(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("assistant", "She stepped into the room.")),
            previous_state="",
        )
        assert "INITIAL scene state" in prompt
        assert "UPDATE" not in prompt

    def test_update_scene_uses_update_instruction(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "I wave"), ("assistant", "She waves back")),
            previous_state="Location: park",
        )
        assert "UPDATE" in prompt
        assert "INITIAL" not in prompt

    def test_previous_state_included(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            previous_state="Location: kitchen\nMood: calm",
        )
        assert "PREVIOUS SCENE STATE" in prompt
        assert "Location: kitchen" in prompt

    def test_no_previous_state_no_section(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            previous_state="",
        )
        assert "PREVIOUS SCENE STATE" not in prompt

    def test_personality_hint_truncated(self):
        long_personality = "X" * 300
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            ai_personality=long_personality,
            ai_name="Sol",
        )
        assert "Sol's personality:" in prompt
        # Should be truncated to ~200 chars at word boundary
        assert len(prompt.split("Sol's personality:")[1].split("\n")[0]) <= 210

    def test_no_personality_no_hint(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "test")),
            ai_personality="",
        )
        assert "personality:" not in prompt.lower().split("format")[0]

    def test_scenario_context_included(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "hi")),
            scenario_context="A coffee shop in autumn",
        )
        assert "Scenario context: A coffee shop in autumn" in prompt

    def test_character_names_in_prompt(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "hi")),
            ai_name="Jessica",
            user_name="Val",
        )
        assert "Jessica (AI)" in prompt
        assert "Val (user)" in prompt
        assert "Jessica" in prompt  # in Clothing line

    def test_messages_appear_in_history(self):
        prompt = build_scene_state_prompt(
            messages=_msgs(("user", "I sit down"), ("assistant", "She looks over")),
        )
        assert "user: I sit down" in prompt
        assert "assistant: She looks over" in prompt

    def test_format_categories_present(self):
        prompt = build_scene_state_prompt(messages=_msgs(("user", "test")))
        for cat in ["Location:", "Clothing:", "Restraints:", "Position:", "Props:", "Mood:"]:
            assert cat in prompt

    def test_anti_hallucination_instructions(self):
        prompt = build_scene_state_prompt(messages=_msgs(("user", "test")))
        assert "Do NOT invent" in prompt
        assert "not described" in prompt


class TestCleanSceneStateResponse:
    def test_strips_whitespace(self):
        assert clean_scene_state_response("  Location: park  ") == "Location: park"

    def test_removes_think_tags(self):
        raw = "<think>reasoning here</think>Location: park"
        assert clean_scene_state_response(raw) == "Location: park"

    def test_removes_none_lines(self):
        raw = "Location: park\nRestraints: none\nMood: calm"
        result = clean_scene_state_response(raw)
        assert "Location: park" in result
        assert "Mood: calm" in result
        assert "Restraints" not in result

    def test_removes_na_lines(self):
        raw = "Location: park\nProps: n/a"
        result = clean_scene_state_response(raw)
        assert "Props" not in result

    def test_removes_empty_value_lines(self):
        raw = "Location: park\nRestraints: \nMood: calm"
        result = clean_scene_state_response(raw)
        assert "Restraints" not in result

    def test_keeps_non_category_lines(self):
        raw = "Location: park\nSome extra context"
        result = clean_scene_state_response(raw)
        assert "Some extra context" in result

    def test_empty_input(self):
        assert clean_scene_state_response("") == ""

    def test_only_think_tags(self):
        assert clean_scene_state_response("<think>blah</think>") == ""

    def test_preserves_restraint_with_detail(self):
        raw = "Restraints: wrists behind back — no free hand use"
        result = clean_scene_state_response(raw)
        assert "wrists behind back" in result
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /mnt/d/prg/plum && python -m pytest projects/rp/tests/test_scene_state.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add projects/rp/tests/test_scene_state.py
git commit -m "test(rp): add scene state prompt building and cleaning tests"
```

---

### Task 8: Run Full Suite & Final Commit

- [ ] **Step 1: Run the complete test suite**

Run: `cd /mnt/d/prg/plum && python -m pytest projects/rp/tests/ -v --tb=short`
Expected: All tests PASS across all 7 test files

- [ ] **Step 2: Verify test count**

Run: `cd /mnt/d/prg/plum && python -m pytest projects/rp/tests/ --co -q | tail -1`
Expected: ~60+ tests collected

- [ ] **Step 3: Final commit if any stragglers**

```bash
git add projects/rp/tests/
git commit -m "test(rp): complete unit test suite for all pure-logic modules"
```
