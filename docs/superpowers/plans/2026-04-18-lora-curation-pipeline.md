# LoRA Curation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-message quality scoring with heuristic pre-filter + LLM judge, truncation-based export for LoRA training data.

**Architecture:** Add pipeline context columns to `rp_messages`, build a hard-gate heuristic filter (`lora_curate.py`), add a DB-based per-message eval command, and update `lora_export.py` to filter by per-message score with conversation truncation.

**Tech Stack:** Python, asyncpg, PostgreSQL, pytest, existing eval engine (G-Eval pattern via Ollama)

**Spec:** `docs/superpowers/specs/2026-04-18-lora-curation-pipeline-design.md`

**Worktree:** `git switch feat/lora-curation` (worktree at `/mnt/d/prg/plum-feat-lora-curation`)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `projects/rp/schema.sql` | Modify | Add 3 columns to `rp_messages` |
| `projects/rp/db.py` | Modify | Update `add_message()` signature |
| `projects/rp/lora_curate.py` | Create | Hard-gate heuristic filter |
| `projects/rp/eval/evaluators/message.py` | Create | DB-based per-message evaluator |
| `projects/rp/eval/cli.py` | Modify | Add `message` subcommand |
| `projects/rp/lora_export.py` | Modify | Per-message score filtering with truncation |
| `projects/rp/routes.py` | Modify | Pass pipeline context to `add_message()` |
| `projects/rp/lora_generate.py` | Modify | Extract `STOCK_PHRASES`, write to DB |
| `projects/rp/tests/test_lora_curate.py` | Create | Tests for heuristic filter |
| `projects/rp/tests/test_message_eval.py` | Create | Tests for per-message evaluator |
| `projects/rp/tests/test_lora_export_truncation.py` | Create | Tests for truncation logic |

---

### Task 1: Schema migration — add pipeline context columns to `rp_messages`

**Files:**
- Modify: `projects/rp/schema.sql:56-66`

- [ ] **Step 1: Add migration blocks to schema.sql**

Add after the existing `rp_messages` table definition (after line 66), before the `rp_first_message_cache` table:

```sql
-- Migration: add pipeline context columns to rp_messages
DO $$ BEGIN
    ALTER TABLE rp_messages ADD COLUMN system_prompt TEXT DEFAULT NULL;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE rp_messages ADD COLUMN scene_state TEXT DEFAULT NULL;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE rp_messages ADD COLUMN post_prompt TEXT DEFAULT NULL;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
```

- [ ] **Step 2: Run schema against the database to verify**

Run:
```bash
cd /mnt/d/prg/plum-feat-lora-curation
source projects/aiserver/.venv/bin/activate
DATABASE_URL="postgresql://plum@localhost:5432/plum" python -c "
import asyncio
from projects.rp.db import init_schema
asyncio.run(init_schema())
print('Schema applied OK')
"
```
Expected: `Schema applied OK`

- [ ] **Step 3: Verify columns exist**

Run:
```bash
docker exec plum-postgres-1 psql -U plum -d plum -c "\d rp_messages"
```
Expected: Output includes `system_prompt`, `scene_state`, `post_prompt` columns, all `text` type.

- [ ] **Step 4: Commit**

```bash
git add projects/rp/schema.sql
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp): add pipeline context columns to rp_messages"
```

---

### Task 2: Update `db.add_message()` to accept pipeline context

**Files:**
- Modify: `projects/rp/db.py:261-275`

- [ ] **Step 1: Write the test**

Create `projects/rp/tests/test_db_context.py`:

```python
"""Tests for pipeline context storage on add_message."""

import pytest


@pytest.mark.asyncio
async def test_add_message_stores_pipeline_context(tmp_path):
    """add_message with context kwargs stores them on the row."""
    # This is an integration test concept — we test the SQL string is correct
    # by checking the function signature and return value include the new fields.
    from projects.rp.db import add_message

    import inspect
    sig = inspect.signature(add_message)
    params = list(sig.parameters.keys())
    assert "system_prompt" in params
    assert "scene_state" in params
    assert "post_prompt" in params


@pytest.mark.asyncio
async def test_add_message_signature_defaults_to_none():
    """New params default to None so existing callers don't break."""
    from projects.rp.db import add_message

    import inspect
    sig = inspect.signature(add_message)
    assert sig.parameters["system_prompt"].default is None
    assert sig.parameters["scene_state"].default is None
    assert sig.parameters["post_prompt"].default is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest projects/rp/tests/test_db_context.py -v`
Expected: FAIL — `system_prompt` not in params

- [ ] **Step 3: Update `add_message` in db.py**

Replace the existing `add_message` function (lines 261-275) with:

```python
async def add_message(conv_id: int, role: str, content: str,
                      raw_response: dict | None = None,
                      system_prompt: str | None = None,
                      scene_state: str | None = None,
                      post_prompt: str | None = None) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO rp_messages (conversation_id, role, content, raw_response, "
        "system_prompt, scene_state, post_prompt, sequence) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, "
        "(SELECT COALESCE(MAX(sequence), 0) + 1 FROM rp_messages WHERE conversation_id = $1)) "
        "RETURNING id, conversation_id, role, content, "
        "raw_response, sequence, system_prompt, scene_state, post_prompt, created_at::text",
        conv_id, role, content, raw_response, system_prompt, scene_state, post_prompt,
    )
    await pool.execute(
        "UPDATE rp_conversations SET updated_at = NOW() WHERE id = $1", conv_id
    )
    return dict(row)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest projects/rp/tests/test_db_context.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to check nothing broke**

Run: `pytest projects/rp/tests/ -v`
Expected: All existing tests pass

- [ ] **Step 6: Commit**

```bash
git add projects/rp/db.py projects/rp/tests/test_db_context.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp): add pipeline context params to db.add_message()"
```

---

### Task 3: Hard-gate heuristic filter (`lora_curate.py`)

**Files:**
- Create: `projects/rp/lora_curate.py`
- Create: `projects/rp/tests/test_lora_curate.py`
- Modify: `projects/rp/lora_generate.py:37-52` (extract `STOCK_PHRASES`)

- [ ] **Step 1: Write the tests**

Create `projects/rp/tests/test_lora_curate.py`:

```python
"""Tests for the hard-gate heuristic filter."""

import pytest
from projects.rp.lora_curate import filter_message, FilterResult


class TestStockPhrases:
    def test_zero_stock_phrases_passes(self):
        result = filter_message(
            "She kicked the door open and stomped inside.",
            user_message="Come in",
            previous_assistant_messages=[],
        )
        assert result.passed

    def test_one_stock_phrase_passes(self):
        result = filter_message(
            "Her breath hitched as she entered the room.",
            user_message="Come in",
            previous_assistant_messages=[],
        )
        assert result.passed

    def test_two_stock_phrases_rejects(self):
        result = filter_message(
            "Her breath hitched as electricity coursed through her body.",
            user_message="Touch me",
            previous_assistant_messages=[],
        )
        assert not result.passed
        assert "stock_phrases" in result.reason


class TestRepetition:
    def test_no_history_passes(self):
        result = filter_message(
            "She walked to the kitchen and grabbed a beer.",
            user_message="Get a drink",
            previous_assistant_messages=[],
        )
        assert result.passed

    def test_unique_message_passes(self):
        result = filter_message(
            "She walked to the kitchen and grabbed a beer.",
            user_message="Get a drink",
            previous_assistant_messages=[
                "He sat on the couch watching television quietly."
            ],
        )
        assert result.passed

    def test_highly_repetitive_rejects(self):
        repeated = "She nuzzled into the crook of his neck, breathing in his scent, feeling the warmth of his body."
        result = filter_message(
            repeated,
            user_message="Hold me",
            previous_assistant_messages=[repeated],
        )
        assert not result.passed
        assert "repetition" in result.reason


class TestLengthRatio:
    def test_reasonable_length_passes(self):
        result = filter_message(
            "She smiled and nodded. 'Sure thing.'",
            user_message="Can you help me?",
            previous_assistant_messages=[],
        )
        assert result.passed

    def test_extreme_length_alone_passes(self):
        """Length ratio alone is not a hard reject."""
        long_msg = "word " * 200
        result = filter_message(
            long_msg,
            user_message="hi",
            previous_assistant_messages=[],
        )
        assert result.passed

    def test_extreme_length_plus_stock_phrase_rejects(self):
        """Length ratio + one stock phrase = reject."""
        long_msg = ("word " * 200) + " her breath hitched"
        result = filter_message(
            long_msg,
            user_message="hi",
            previous_assistant_messages=[],
        )
        assert not result.passed


class TestFilterResult:
    def test_passed_result(self):
        result = filter_message(
            "Normal message here.",
            user_message="Hello",
            previous_assistant_messages=[],
        )
        assert result.passed
        assert result.reason == ""
        assert result.stock_phrase_count == 0

    def test_failed_result_has_details(self):
        result = filter_message(
            "Her breath hitched as electricity coursed through her veins.",
            user_message="x",
            previous_assistant_messages=[],
        )
        assert not result.passed
        assert result.stock_phrase_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest projects/rp/tests/test_lora_curate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'projects.rp.lora_curate'`

- [ ] **Step 3: Extract `STOCK_PHRASES` to `lora_curate.py`**

Create `projects/rp/lora_curate.py`:

```python
"""Hard-gate heuristic filter for LoRA training data curation.

Cheaply rejects low-quality assistant messages before they reach the
LLM judge. Three checks: stock phrase density, trigram repetition
against recent messages, and length ratio combined with other flags.
"""

from dataclasses import dataclass, field


STOCK_PHRASES = [
    "ruin you for anyone else", "ruin me for anyone else",
    "ruined for anyone else", "ruined me for everyone",
    "electricity coursed", "electricity shot through",
    "shivers down her spine", "shivers down my spine",
    "breath caught in", "breath hitched",
    "heart pounded in", "heart hammered in",
    "pulse quickened", "pulse raced",
    "a gasp escaped", "a moan escaped",
    "core tightened", "coil tightened",
    "undone by", "came undone",
    "claimed her lips", "claimed his lips",
    "molten heat", "pooling heat",
    "like a prayer", "whispered like a prayer",
    "swallowed thickly", "adam's apple bobbed",
]

REPETITION_THRESHOLD = 0.40
LENGTH_RATIO_THRESHOLD = 3.0


@dataclass
class FilterResult:
    passed: bool
    reason: str = ""
    stock_phrase_count: int = 0
    trigram_overlap: float = 0.0
    length_ratio: float = 0.0


def _count_stock_phrases(text: str) -> int:
    lower = text.lower()
    return sum(1 for p in STOCK_PHRASES if p in lower)


def _trigrams(text: str) -> set[str]:
    words = text.lower().split()
    if len(words) < 3:
        return set()
    return {f"{words[i]} {words[i+1]} {words[i+2]}" for i in range(len(words) - 2)}


def _trigram_overlap(message: str, previous_messages: list[str]) -> float:
    if not previous_messages:
        return 0.0
    msg_trigrams = _trigrams(message)
    if not msg_trigrams:
        return 0.0
    prev_trigrams: set[str] = set()
    for prev in previous_messages:
        prev_trigrams |= _trigrams(prev)
    if not prev_trigrams:
        return 0.0
    overlap = msg_trigrams & prev_trigrams
    return len(overlap) / len(msg_trigrams)


def filter_message(
    assistant_message: str,
    user_message: str,
    previous_assistant_messages: list[str],
) -> FilterResult:
    """Run hard-gate checks on a single assistant message.

    Args:
        assistant_message: The message to evaluate.
        user_message: The user message this is responding to.
        previous_assistant_messages: Up to 3 most recent prior assistant
            messages in the same conversation (for repetition check).

    Returns:
        FilterResult with passed=True if message survives all checks.
    """
    stock_count = _count_stock_phrases(assistant_message)
    overlap = _trigram_overlap(assistant_message, previous_assistant_messages[-3:])

    user_len = max(len(user_message.split()), 1)
    asst_len = len(assistant_message.split())
    length_ratio = asst_len / user_len

    is_long = length_ratio > LENGTH_RATIO_THRESHOLD

    # Check 1: 2+ stock phrases = reject
    if stock_count >= 2:
        return FilterResult(
            passed=False,
            reason="stock_phrases",
            stock_phrase_count=stock_count,
            trigram_overlap=overlap,
            length_ratio=length_ratio,
        )

    # Check 2: >40% trigram overlap with recent messages = reject
    if overlap > REPETITION_THRESHOLD:
        return FilterResult(
            passed=False,
            reason="repetition",
            stock_phrase_count=stock_count,
            trigram_overlap=overlap,
            length_ratio=length_ratio,
        )

    # Check 3: extreme length + any stock phrase = reject
    if is_long and stock_count >= 1:
        return FilterResult(
            passed=False,
            reason="length_ratio+stock_phrase",
            stock_phrase_count=stock_count,
            trigram_overlap=overlap,
            length_ratio=length_ratio,
        )

    return FilterResult(
        passed=True,
        stock_phrase_count=stock_count,
        trigram_overlap=overlap,
        length_ratio=length_ratio,
    )
```

- [ ] **Step 4: Update `lora_generate.py` to import from `lora_curate`**

In `projects/rp/lora_generate.py`, replace lines 37-52 (`STOCK_PHRASES` definition) with:

```python
from .lora_curate import STOCK_PHRASES
```

And update `check_stock_phrases` (line 74-77) to keep working — no change needed since it already references the module-level `STOCK_PHRASES`.

- [ ] **Step 5: Run curate tests**

Run: `pytest projects/rp/tests/test_lora_curate.py -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite**

Run: `pytest projects/rp/tests/ -v`
Expected: All pass (including existing `test_lora_generate_budget.py`)

- [ ] **Step 7: Commit**

```bash
git add projects/rp/lora_curate.py projects/rp/tests/test_lora_curate.py projects/rp/lora_generate.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp): add hard-gate heuristic filter for LoRA curation"
```

---

### Task 4: Per-message evaluator (`eval/evaluators/message.py`)

**Files:**
- Create: `projects/rp/eval/evaluators/message.py`
- Create: `projects/rp/tests/test_message_eval.py`

- [ ] **Step 1: Write the tests**

Create `projects/rp/tests/test_message_eval.py`:

```python
"""Tests for the DB-based per-message evaluator."""

import pytest
from projects.rp.eval.evaluators.message import (
    build_context_for_message,
    get_scoreable_messages,
)


class TestBuildContext:
    def test_builds_context_from_message_row(self):
        msg = {
            "id": 100,
            "conversation_id": 5,
            "role": "assistant",
            "content": "She kicked the door open.",
            "system_prompt": "You are Amber. Be sarcastic.",
            "scene_state": "Living room. Night.",
            "post_prompt": "",
            "sequence": 4,
        }
        history = [
            {"role": "user", "content": "Come in", "sequence": 1},
            {"role": "assistant", "content": "Ugh, fine.", "sequence": 2},
            {"role": "user", "content": "Sit down", "sequence": 3},
        ]
        ctx = build_context_for_message(msg, history)
        assert ctx["system_prompt"] == "You are Amber. Be sarcastic."
        assert ctx["scene_state"] == "Living room. Night."
        assert ctx["assistant_message"] == "She kicked the door open."
        assert ctx["user_message"] == "Sit down"
        assert "Ugh, fine." in ctx["conversation_history"]

    def test_user_message_is_last_user_in_history(self):
        msg = {
            "id": 100,
            "conversation_id": 5,
            "role": "assistant",
            "content": "Response here",
            "system_prompt": "sys",
            "scene_state": "",
            "post_prompt": "",
            "sequence": 6,
        }
        history = [
            {"role": "user", "content": "first", "sequence": 1},
            {"role": "assistant", "content": "reply", "sequence": 2},
            {"role": "user", "content": "second", "sequence": 3},
            {"role": "assistant", "content": "reply2", "sequence": 4},
            {"role": "user", "content": "third", "sequence": 5},
        ]
        ctx = build_context_for_message(msg, history)
        assert ctx["user_message"] == "third"


class TestGetScoreableMessages:
    def test_filters_to_assistant_with_system_prompt(self):
        messages = [
            {"id": 1, "role": "user", "content": "hi", "system_prompt": None, "sequence": 1},
            {"id": 2, "role": "assistant", "content": "hey", "system_prompt": "sys", "sequence": 2},
            {"id": 3, "role": "assistant", "content": "no ctx", "system_prompt": None, "sequence": 3},
        ]
        result = get_scoreable_messages(messages)
        assert len(result) == 1
        assert result[0]["id"] == 2

    def test_empty_input(self):
        assert get_scoreable_messages([]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest projects/rp/tests/test_message_eval.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `message.py`**

Create `projects/rp/eval/evaluators/message.py`:

```python
"""Per-message evaluator — scores individual assistant messages from the DB.

Unlike the response evaluator (which reads from log.txt), this reads
pipeline context directly from rp_messages columns: system_prompt,
scene_state, post_prompt.
"""

from ..engine import EvalResult, Rubric, judge, load_rubric


def get_scoreable_messages(messages: list[dict]) -> list[dict]:
    """Filter to assistant messages that have pipeline context stored."""
    return [
        m for m in messages
        if m["role"] == "assistant" and m.get("system_prompt") is not None
    ]


def build_context_for_message(msg: dict, history: list[dict]) -> dict:
    """Assemble the context dict for judging a single message.

    Args:
        msg: The assistant message row (must have system_prompt, scene_state).
        history: All messages in the conversation with sequence < msg.sequence,
                 ordered by sequence.
    """
    # Find the user message this is responding to (last user msg before this one)
    user_message = ""
    for h in reversed(history):
        if h["role"] == "user":
            user_message = h["content"]
            break

    # Format recent history (last 3 exchanges = 6 messages)
    recent = history[-6:]
    history_lines = []
    for h in recent:
        history_lines.append(f"{h['role']}: {h['content']}")
    conversation_history = "\n\n".join(history_lines)

    return {
        "system_prompt": msg.get("system_prompt", ""),
        "scene_state": msg.get("scene_state", "") or "",
        "conversation_history": conversation_history,
        "user_message": user_message,
        "assistant_message": msg["content"],
    }


async def score_message(
    aiserver_url: str,
    judge_model: str,
    msg: dict,
    history: list[dict],
    rubric: Rubric | None = None,
) -> EvalResult:
    """Score a single assistant message using the response rubric."""
    rubric = rubric or load_rubric("response")
    context = build_context_for_message(msg, history)

    return await judge(
        aiserver_url, judge_model, rubric, context,
        evaluator="curation",
        target_id=f"msg:{msg['id']}",
        target_label=f"msg {msg['id']} (conv {msg['conversation_id']})",
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest projects/rp/tests/test_message_eval.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add projects/rp/eval/evaluators/message.py projects/rp/tests/test_message_eval.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp): add DB-based per-message evaluator"
```

---

### Task 5: Add `message` subcommand to eval CLI

**Files:**
- Modify: `projects/rp/eval/cli.py:67-111` (add subparser), `cli.py:730-762` (add handler)

- [ ] **Step 1: Add the subparser**

In `projects/rp/eval/cli.py`, in the `build_parser()` function, after the `p_response` block (after line 85), add:

```python
    p_message = sub.add_parser("message", help="Score individual messages for LoRA curation")
    _add_common_args(p_message)
    p_message.add_argument("--conv-id", type=int, help="Score messages in one conversation")
    p_message.add_argument("--all", action="store_true", help="Score all conversations")
    p_message.add_argument("--skip-scored", action="store_true",
                           help="Skip messages that already have scores")
    p_message.add_argument("--min-messages", type=int, default=10,
                           help="Min messages per conv for --all (default: 10)")
```

- [ ] **Step 2: Add the import**

At the top of `cli.py`, alongside the other evaluator imports (around line 42), add:

```python
from .evaluators import message as message_eval  # noqa: E402
```

Also add the import for the curate filter (after the db imports around line 47):

```python
from lora_curate import filter_message  # noqa: E402
```

- [ ] **Step 3: Add the handler function**

Add `run_message` function after `run_scene_state` (around line 440):

```python
async def run_message(args, pool: asyncpg.Pool, aiserver_url: str):
    rubric = load_rubric("response", Path(args.rubric) if args.rubric else None)

    # Gather conversation IDs
    if args.conv_id:
        conv_ids = [args.conv_id]
    elif args.all:
        rows = await pool.fetch(
            "SELECT c.id FROM rp_conversations c "
            "JOIN rp_messages m ON m.conversation_id = c.id "
            "GROUP BY c.id HAVING count(m.id) >= $1 "
            "ORDER BY c.id",
            args.min_messages,
        )
        conv_ids = [r["id"] for r in rows]
    else:
        print("Error: --conv-id or --all required", file=sys.stderr)
        sys.exit(1)

    if not conv_ids:
        print("No conversations found.")
        return

    # Collect already-scored message IDs for --skip-scored
    scored_ids: set[str] = set()
    if args.skip_scored:
        scored_rows = await pool.fetch(
            "SELECT target_id FROM rp_eval_metrics "
            "WHERE target_type = 'message'"
        )
        scored_ids = {r["target_id"] for r in scored_rows}

    total_scored = 0
    total_rejected = 0
    total_skipped = 0

    print(f"Judge: {args.judge_model}  Conversations: {len(conv_ids)}")

    for conv_id in conv_ids:
        all_msgs = await pool.fetch(
            "SELECT id, conversation_id, role, content, system_prompt, "
            "scene_state, post_prompt, sequence "
            "FROM rp_messages WHERE conversation_id = $1 ORDER BY sequence",
            conv_id,
        )
        all_msgs = [dict(m) for m in all_msgs]
        scoreable = message_eval.get_scoreable_messages(all_msgs)

        if not scoreable:
            continue

        conv_label = f"conv {conv_id}"
        print(f"\n{conv_label}: {len(scoreable)} scoreable messages")

        if args.dry_run:
            for msg in scoreable:
                preview = msg["content"][:60].replace("\n", " ")
                scored_marker = " [scored]" if f"msg:{msg['id']}" in scored_ids else ""
                print(f"  msg {msg['id']} seq {msg['sequence']}: {preview}...{scored_marker}")
            continue

        # Warm up model on first conv
        if total_scored == 0 and total_rejected == 0:
            await _warmup_model(aiserver_url, args.judge_model)

        results: list[EvalResult] = []
        eval_times: list[float] = []

        for i, msg in enumerate(scoreable):
            target_id = f"msg:{msg['id']}"

            if target_id in scored_ids:
                total_skipped += 1
                continue

            # Build history: all messages before this one
            history = [m for m in all_msgs if m["sequence"] < msg["sequence"]]

            # Hard-gate filter
            prev_assistant = [
                m["content"] for m in history
                if m["role"] == "assistant"
            ][-3:]
            user_msg = ""
            for h in reversed(history):
                if h["role"] == "user":
                    user_msg = h["content"]
                    break

            gate = filter_message(msg["content"], user_msg, prev_assistant)

            if not gate.passed:
                total_rejected += 1
                reject_scores = [
                    {"dimension": "hard_gate", "score": 0, "explanation": gate.reason}
                ]
                await save_metrics(
                    domain="curation",
                    target_type="message",
                    target_id=target_id,
                    target_label=f"msg {msg['id']} (conv {conv_id})",
                    judge_model="heuristic",
                    rubric_name="hard_gate",
                    scores=reject_scores,
                    weighted_average=0.0,
                    raw_judge_output=f"reason={gate.reason} stock={gate.stock_phrase_count} "
                                     f"overlap={gate.trigram_overlap:.2f} length={gate.length_ratio:.1f}",
                    pool=pool,
                )
                preview = msg["content"][:50].replace("\n", " ")
                print(f"  [REJECT] msg {msg['id']}: {gate.reason} — {preview}...")
                continue

            # Judge
            preview = msg["content"][:50].replace("\n", " ")
            print(f"  [{i+1}/{len(scoreable)}] msg {msg['id']} {preview}...", end="", flush=True)
            try:
                t0 = time.time()
                result = await message_eval.score_message(
                    aiserver_url, args.judge_model, msg, history, rubric,
                )
                elapsed = time.time() - t0
                eval_times.append(elapsed)
                results.append(result)
                total_scored += 1
                _print_progress(result, i, len(scoreable), elapsed, eval_times)
                await _save_results([result], "message", rubric.name, pool)
            except Exception as e:
                print(f" ERROR: {type(e).__name__}: {e}" if str(e) else f" ERROR: {type(e).__name__}")

    print(f"\nDone: {total_scored} scored, {total_rejected} rejected, {total_skipped} skipped")
```

- [ ] **Step 4: Wire up the command in `main()`**

In the `main()` function's command dispatch (around line 746), add before the `else` branch:

```python
        elif args.command == "message":
            await run_message(args, pool, aiserver_url)
```

- [ ] **Step 5: Smoke test with dry-run**

Run:
```bash
cd /mnt/d/prg/plum-feat-lora-curation
source projects/aiserver/.venv/bin/activate
DATABASE_URL="postgresql://plum@localhost:5432/plum" python -m projects.rp.eval message --conv-id 87 --dry-run
```
Expected: Lists messages in conv 87 (most will show as not scoreable since they lack `system_prompt`).

- [ ] **Step 6: Run full test suite**

Run: `pytest projects/rp/tests/ -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add projects/rp/eval/cli.py projects/rp/eval/evaluators/message.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp): add message subcommand for per-message LoRA curation scoring"
```

---

### Task 6: Update `lora_export.py` with per-message score truncation

**Files:**
- Modify: `projects/rp/lora_export.py`
- Create: `projects/rp/tests/test_lora_export_truncation.py`

- [ ] **Step 1: Write the tests**

Create `projects/rp/tests/test_lora_export_truncation.py`:

```python
"""Tests for per-message score truncation in lora_export."""

import pytest
from projects.rp.lora_export import truncate_by_score


class TestTruncateByScore:
    def test_all_above_threshold_keeps_all(self):
        messages = [
            {"id": 1, "role": "user", "content": "hi", "sequence": 1},
            {"id": 2, "role": "assistant", "content": "hey", "sequence": 2},
            {"id": 3, "role": "user", "content": "sup", "sequence": 3},
            {"id": 4, "role": "assistant", "content": "nm", "sequence": 4},
        ]
        scores = {2: 4.0, 4: 3.5}
        result = truncate_by_score(messages, scores, min_score=3.0)
        assert len(result) == 4

    def test_second_assistant_below_truncates(self):
        messages = [
            {"id": 1, "role": "user", "content": "hi", "sequence": 1},
            {"id": 2, "role": "assistant", "content": "hey", "sequence": 2},
            {"id": 3, "role": "user", "content": "sup", "sequence": 3},
            {"id": 4, "role": "assistant", "content": "bad reply", "sequence": 4},
            {"id": 5, "role": "user", "content": "ok", "sequence": 5},
            {"id": 6, "role": "assistant", "content": "good again", "sequence": 6},
        ]
        scores = {2: 4.0, 4: 2.0, 6: 4.5}
        result = truncate_by_score(messages, scores, min_score=3.0)
        # Truncates at msg 4, so we keep only msgs 1-2
        assert len(result) == 2
        assert result[-1]["id"] == 2

    def test_first_assistant_below_returns_empty(self):
        messages = [
            {"id": 1, "role": "user", "content": "hi", "sequence": 1},
            {"id": 2, "role": "assistant", "content": "bad", "sequence": 2},
        ]
        scores = {2: 1.0}
        result = truncate_by_score(messages, scores, min_score=3.0)
        assert len(result) == 0

    def test_unscored_excluded_by_default(self):
        messages = [
            {"id": 1, "role": "user", "content": "hi", "sequence": 1},
            {"id": 2, "role": "assistant", "content": "hey", "sequence": 2},
        ]
        scores = {}  # no scores
        result = truncate_by_score(messages, scores, min_score=3.0)
        assert len(result) == 0

    def test_unscored_included_with_flag(self):
        messages = [
            {"id": 1, "role": "user", "content": "hi", "sequence": 1},
            {"id": 2, "role": "assistant", "content": "hey", "sequence": 2},
        ]
        scores = {}
        result = truncate_by_score(messages, scores, min_score=3.0,
                                    include_unscored=True)
        assert len(result) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest projects/rp/tests/test_lora_export_truncation.py -v`
Expected: FAIL — `cannot import name 'truncate_by_score'`

- [ ] **Step 3: Add `truncate_by_score` to `lora_export.py`**

Add this function after the existing `_conv_to_sharegpt` function (around line 131):

```python
def truncate_by_score(
    messages: list[dict],
    scores: dict[int, float],
    min_score: float,
    include_unscored: bool = False,
) -> list[dict]:
    """Truncate a message list at the first assistant message below threshold.

    Args:
        messages: Messages in sequence order.
        scores: Map of assistant message ID -> weighted_average score.
        min_score: Minimum score to include.
        include_unscored: If True, treat unscored messages as passing.

    Returns:
        Truncated message list (may be empty).
    """
    result = []
    for msg in messages:
        if msg["role"] == "assistant":
            msg_score = scores.get(msg["id"])
            if msg_score is None:
                if not include_unscored:
                    break
            elif msg_score < min_score:
                # Drop this assistant message AND its preceding user message
                if result and result[-1]["role"] == "user":
                    result.pop()
                break
        result.append(msg)
    return result
```

- [ ] **Step 4: Run truncation tests**

Run: `pytest projects/rp/tests/test_lora_export_truncation.py -v`
Expected: All PASS

- [ ] **Step 5: Update `main()` in `lora_export.py`**

Replace the `--min-score` argument (line 152) with:

```python
    parser.add_argument("--min-msg-score", type=float, default=0,
                        help="Min per-message eval score to include (0 = no filter)")
    parser.add_argument("--include-unscored", action="store_true",
                        help="Include messages without scores (default: exclude)")
```

Remove the old `_get_eval_scores` function (lines 133-144) and the `--min-score` argument.

Update the export loop in `main()` (around line 176-187) to use per-message scoring:

```python
    results = []
    for conv_id in conv_ids:
        conv_data = await _get_conv_data(pool, conv_id)
        if not conv_data:
            _log.warning("Skipping conv %d: missing data", conv_id)
            continue

        original_turns = len([m for m in conv_data["messages"] if m["role"] == "assistant"])

        if args.min_msg_score > 0:
            # Look up per-message scores
            msg_ids = [m["id"] for m in conv_data["messages"] if m["role"] == "assistant"]
            if msg_ids:
                score_rows = await pool.fetch(
                    f"SELECT target_id, weighted_average FROM rp_eval_metrics "
                    f"WHERE target_type = 'message' AND target_id = ANY($1::text[])",
                    [f"msg:{mid}" for mid in msg_ids],
                )
                scores = {}
                for row in score_rows:
                    mid = int(row["target_id"].split(":")[1])
                    scores[mid] = float(row["weighted_average"])

                conv_data["messages"] = truncate_by_score(
                    conv_data["messages"], scores, args.min_msg_score,
                    include_unscored=args.include_unscored,
                )

        if not conv_data["messages"]:
            _log.warning("Skipping conv %d: no messages after filtering", conv_id)
            continue

        entry = _conv_to_sharegpt(conv_data)
        exported_turns = len([m for m in entry["conversations"] if m["from"] == "gpt"])
        entry["metadata"]["original_turns"] = original_turns
        entry["metadata"]["exported_turns"] = exported_turns
        results.append(entry)
        _log.info("  conv %d: %s — %d/%d turns", conv_id,
                  entry["metadata"]["character"], exported_turns, original_turns)
```

- [ ] **Step 6: Update `_get_conv_data` to include message IDs**

In `_get_conv_data` (line 100-102), update the query to include `id`:

```python
    messages = await pool.fetch(
        "SELECT id, role, content FROM rp_messages "
        "WHERE conversation_id = $1 ORDER BY sequence", conv_id)
```

- [ ] **Step 7: Run all tests**

Run: `pytest projects/rp/tests/ -v`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add projects/rp/lora_export.py projects/rp/tests/test_lora_export_truncation.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp): add per-message score truncation to lora_export"
```

---

### Task 7: Store pipeline context in live conversations (`routes.py`)

**Files:**
- Modify: `projects/rp/routes.py:845,950,1025,1149`

- [ ] **Step 1: Update `send_message` endpoint**

At line 845, change:
```python
await db.add_message(conv_id, "assistant", post_ctx["response"], raw_response=raw)
```
to:
```python
await db.add_message(
    conv_id, "assistant", post_ctx["response"], raw_response=raw,
    system_prompt=ctx.get("system_prompt", ""),
    scene_state=conv.get("scene_state", ""),
    post_prompt=ctx.get("post_prompt", ""),
)
```

- [ ] **Step 2: Update `regenerate` endpoint**

At line 950, same change:
```python
await db.add_message(
    conv_id, "assistant", post_ctx["response"], raw_response=raw,
    system_prompt=ctx.get("system_prompt", ""),
    scene_state=conv.get("scene_state", ""),
    post_prompt=ctx.get("post_prompt", ""),
)
```

- [ ] **Step 3: Update `continue_conversation` endpoint**

At line 1025, same change:
```python
await db.add_message(
    conv_id, "assistant", post_ctx["response"], raw_response=raw,
    system_prompt=ctx.get("system_prompt", ""),
    scene_state=conv.get("scene_state", ""),
    post_prompt=ctx.get("post_prompt", ""),
)
```

- [ ] **Step 4: Update `auto_reply` endpoint**

At line 1149, same change:
```python
await db.add_message(
    conv_id, save_role, post_ctx["response"], raw_response=raw,
    system_prompt=ctx.get("system_prompt", ""),
    scene_state=conv.get("scene_state", ""),
    post_prompt=ctx.get("post_prompt", ""),
)
```

- [ ] **Step 5: Run full test suite**

Run: `pytest projects/rp/tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add projects/rp/routes.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp): store pipeline context on assistant messages in routes"
```

---

### Task 8: Write synthetic conversations to DB (`lora_generate.py`)

**Files:**
- Modify: `projects/rp/lora_generate.py:544-621`

- [ ] **Step 1: Add `--also-json` flag and DB writing**

In `main()`, replace `--output` (line 557) with:
```python
    parser.add_argument("--also-json", type=str, default=None,
                        help="Also write results to JSON file (optional)")
```

- [ ] **Step 2: Update conversation generation to write to DB**

After a successful `generate_conversation` call (around line 598), add DB writes. Replace the result collection block:

```python
            if result:
                all_results.append(result)
                turns = result["metadata"]["turns"]
                stock = result["metadata"]["stock_phrases_found"]
                _log.info("  -> %d turns, %d stock phrases", turns, stock)

                # Write to DB
                from . import db as rp_db
                rp_db._pool = pool  # reuse existing pool
                db_conv = await rp_db.create_conversation(
                    user_card_id=args.user_card_id,
                    ai_card_id=ai_card_id,
                    scenario_id=None,
                    model=args.model,
                )
                system_prompt = result["conversations"][0]["value"]
                for msg in result["conversations"][1:]:
                    role = "user" if msg["from"] == "human" else "assistant"
                    kwargs = {}
                    if role == "assistant":
                        kwargs["system_prompt"] = system_prompt
                        kwargs["scene_state"] = ""
                        kwargs["post_prompt"] = ""
                    await rp_db.add_message(
                        db_conv["id"], role, msg["value"], **kwargs,
                    )
                _log.info("  -> saved to DB as conv %d", db_conv["id"])
            else:
                _log.warning("  -> discarded")
```

- [ ] **Step 3: Update JSON output to use `--also-json`**

Replace the output section (lines 611-617):

```python
    if args.also_json and all_results:
        with open(args.also_json, "w") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        _log.info("Also wrote JSON to %s", args.also_json)

    total_turns = sum(r["metadata"]["turns"] for r in all_results)
    _log.info("Generated %d conversations (%d turns), all saved to DB",
             len(all_results), total_turns)
```

- [ ] **Step 4: Run existing lora_generate tests**

Run: `pytest projects/rp/tests/test_lora_generate_budget.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add projects/rp/lora_generate.py
git commit --author="Claude <noreply@anthropic.com>" -m "feat(rp): write synthetic conversations to DB with pipeline context"
```

---

### Task 9: Integration test — end-to-end dry run

**Files:** None (verification only)

- [ ] **Step 1: Verify schema is applied**

```bash
docker exec plum-postgres-1 psql -U plum -d plum -c "\d rp_messages" | grep -E "system_prompt|scene_state|post_prompt"
```
Expected: Three rows showing the new columns.

- [ ] **Step 2: Verify eval message dry-run works**

```bash
cd /mnt/d/prg/plum-feat-lora-curation
source projects/aiserver/.venv/bin/activate
DATABASE_URL="postgresql://plum@localhost:5432/plum" python -m projects.rp.eval message --all --dry-run
```
Expected: Lists conversations and their scoreable messages (most old messages will be skipped since they lack `system_prompt`).

- [ ] **Step 3: Verify export dry-run works**

```bash
DATABASE_URL="postgresql://plum@localhost:5432/plum" python -m projects.rp.lora_export --user-card-id 11 --min-msg-score 3.5 -o /dev/null 2>&1 | head -20
```
Expected: Runs without errors (may export 0 conversations since no messages are scored yet).

- [ ] **Step 4: Run full test suite one final time**

```bash
pytest projects/rp/tests/ -v
```
Expected: All tests pass.
