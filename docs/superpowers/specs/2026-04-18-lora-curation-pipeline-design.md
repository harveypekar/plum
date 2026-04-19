# LoRA Training Data Curation Pipeline

**Date:** 2026-04-18
**Status:** Approved
**Scope:** Per-message quality scoring and filtered export for LoRA fine-tuning

## Problem

The RP system can generate and export conversations for LoRA training, but has no way to filter by quality. Conversations degrade over time — early exchanges are strong, later ones recycle stock phrases and lose character voice. Exporting whole conversations teaches the model the exact cliches we're trying to train out.

The eval system exists but operates at conversation granularity via `log.txt`, not per-message from the DB. Pipeline context (system prompts, scene state) isn't stored on messages, so there's nothing to evaluate against.

## Solution

A three-stage curation pipeline: store pipeline context on messages, score individual messages with heuristic pre-filter + LLM judge, export with per-message score threshold that truncates conversations at the first quality drop.

## 1. DB Schema Changes

Add three nullable TEXT columns to `rp_messages`:

- `system_prompt` — the assembled system prompt used when generating this response
- `scene_state` — scene state before this message was generated
- `post_prompt` — post-history prompt injection if any

Only populated for `role='assistant'` rows. Old messages stay NULL. Migration uses the existing `DO $$ BEGIN ... EXCEPTION WHEN duplicate_column` pattern in `schema.sql`.

## 2. Pipeline Context Storage

### Live conversations (`pipeline.py`)

After generating an assistant response, pass `system_prompt`, `scene_state`, and `post_prompt` from the pipeline `ctx` dict to `db.add_message()`.

### Synthetic conversations (`lora_generate.py`)

Write synthetic conversations to the DB as real conversations (`db.create_conversation()` + `db.add_message()` per turn) with pipeline context on each assistant message. The JSON output file becomes optional (`--also-json` flag).

### `db.add_message()` changes

Add three optional parameters: `system_prompt: str | None = None`, `scene_state: str | None = None`, `post_prompt: str | None = None`. All default to None.

## 3. Hard-Gate Heuristic Filter

New module: `projects/rp/lora_curate.py`

A `filter_message()` function that takes a single assistant message + recent conversation history and returns pass/reject with reasons. Runs before the LLM judge, costs zero GPU time.

### Checks

**Stock phrase density:** Reuse `STOCK_PHRASES` from `lora_generate.py` (extract to shared location). Per-message threshold: 2+ stock phrases = reject. One stock phrase passes through to the judge.

**Repetition detection:** Compare message against previous 3 assistant messages using trigram overlap. If >40% of the message's trigrams appeared in recent messages, reject.

**Length ratio:** If assistant message is >3x the length of the user message it responds to, flag it. Not a hard reject alone, but combined with either check above, it becomes one.

## 4. Per-Message Scoring

New eval CLI command: `python -m projects.rp.eval message`

### Interface

```
python -m projects.rp.eval message --conv-id 87
python -m projects.rp.eval message --all --skip-scored
python -m projects.rp.eval message --all --skip-scored --dry-run
```

### Behavior

- Reads assistant messages directly from `rp_messages` (no `log.txt` dependency)
- Skips messages where `system_prompt` is NULL (old messages without context)
- For each assistant message:
  1. Run hard-gate filter. Rejected messages get score 0.0 saved to `rp_eval_metrics` with `domain='curation'`
  2. Survivors: assemble context from DB (system_prompt, scene_state from the message row; conversation history from prior messages in sequence order)
  3. Judge using existing `response.toml` rubric via `judge()` from `engine.py`
  4. Save score to `rp_eval_metrics` with `target_type='message'`, `target_id='msg:{message_id}'`

### Incremental

`--skip-scored` checks `rp_eval_metrics` for existing scores and skips already-scored messages. Re-running after adding new conversations only scores the new ones.

### Judge model

`qwen3.5:35b` (per project convention).

## 5. Export with Per-Message Threshold

### Changes to `lora_export.py`

New flag: `--min-msg-score FLOAT` (replaces broken `--min-score`).

### Truncation logic

For each conversation:
1. Load messages in sequence order
2. Look up each assistant message's curation score from `rp_eval_metrics` (`target_type='message'`, `target_id='msg:{id}'`)
3. Walk forward: include user+assistant pairs as long as the assistant message scores at or above the threshold
4. First assistant message below threshold **truncates** the conversation — everything after is dropped, even if later messages score well
5. Messages with no score are excluded by default; `--include-unscored` flag overrides

### Why truncate, not cherry-pick

Training examples must be coherent conversations. Skipping turns 6-8 then including 9-12 creates context the model never saw. Truncation preserves narrative integrity.

### Metadata

Output `metadata` gains `original_turns` and `exported_turns` counts per conversation.

## 6. End-to-End Workflow

```
1. Generate data
   - Play conversations via pipeline.py (context stored automatically)
   - Generate synthetic: python -m projects.rp.lora_generate ... (writes to DB)

2. Score
   python -m projects.rp.eval message --all --skip-scored
   -> hard-gate rejects garbage (score 0.0)
   -> survivors judged by qwen3.5:35b
   -> scores in rp_eval_metrics

3. Export
   python -m projects.rp.lora_export --user-card-id 11 --min-msg-score 3.5 -o training.json
   -> conversations truncated at first failing message
   -> ShareGPT JSON for training

4. Iterate
   - Adjust --min-msg-score without re-scoring
   - New conversations: re-run step 2 with --skip-scored
```

## Out of Scope

- LimaRP dataset integration (separate effort)
- QLoRA training pipeline (Unsloth/Axolotl config)
- Backfilling old messages with reconstructed system prompts
- Quality tiers (gold/silver/reject) — can be added later once baseline LoRA results exist
