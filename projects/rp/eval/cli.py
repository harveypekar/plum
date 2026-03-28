"""CLI entry point for the RP evaluation system.

Usage:
    python -m projects.rp.eval fewshot --card-id 9 --judge-model qwen3:32b
    python -m projects.rp.eval fewshot --example-id 22 --judge-model qwen3:32b
    python -m projects.rp.eval fewshot --card-id 9 --limit 5
    python -m projects.rp.eval fewshot --card-id 9 --json
    python -m projects.rp.eval fewshot --card-id 9 --dry-run

    python -m projects.rp.eval card --card-id 9
    python -m projects.rp.eval card --all

    python -m projects.rp.eval response --conv-id 57
    python -m projects.rp.eval response --conv-id 57 --limit 3

    python -m projects.rp.eval scene-state --conv-id 57

    python -m projects.rp.eval scenario --scenario-id 8
    python -m projects.rp.eval scenario --all
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import asyncpg

# Reuse aiserver's URL resolution for wsl-gateway fallback
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "aiserver"))
from config import resolve_url

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from .engine import EvalResult, judge, load_rubric  # noqa: E402
from .evaluators import card as card_eval  # noqa: E402
from .evaluators import fewshot as fewshot_eval  # noqa: E402
from .evaluators import response as response_eval  # noqa: E402
from .evaluators import scenario as scenario_eval  # noqa: E402
from .evaluators import scene_state as scene_state_eval  # noqa: E402
from .report import aggregate, format_report, format_single, to_json  # noqa: E402

# Import db functions for saving/loading metrics
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import save_metrics, get_metrics  # noqa: E402


def _add_common_args(sub: argparse.ArgumentParser):
    sub.add_argument(
        "--judge-model", default="qwen3:32b",
        help="Ollama model for judging (default: qwen3:32b)",
    )
    sub.add_argument(
        "--ollama-url",
        default=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
    )
    sub.add_argument("--db-url", default=None)
    sub.add_argument("--rubric", default=None, help="Custom rubric TOML path")
    sub.add_argument("--json", action="store_true", help="Output JSON")
    sub.add_argument("--dry-run", action="store_true")
    sub.add_argument("--save", action="store_true", help="Save results to database")
    sub.add_argument("--limit", type=int, default=0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RP Evaluation System")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fewshot = sub.add_parser("fewshot", help="Evaluate fewshot examples")
    _add_common_args(p_fewshot)
    p_fewshot.add_argument("--card-id", type=int, help="Evaluate all for this card")
    p_fewshot.add_argument("--example-id", type=int, help="Evaluate a single example")

    p_card = sub.add_parser("card", help="Evaluate character card quality")
    _add_common_args(p_card)
    p_card.add_argument("--card-id", type=int, help="Evaluate a single card")
    p_card.add_argument("--all", action="store_true", help="Evaluate all cards")

    p_response = sub.add_parser("response", help="Evaluate responses from conv log")
    _add_common_args(p_response)
    p_response.add_argument("--conv-id", type=int, required=True, help="Conversation ID")
    p_response.add_argument("--log-path", default=None, help="Custom log.txt path")

    p_scene = sub.add_parser("scene-state", help="Evaluate scene state updates from conv log")
    _add_common_args(p_scene)
    p_scene.add_argument("--conv-id", type=int, required=True, help="Conversation ID")
    p_scene.add_argument("--log-path", default=None, help="Custom log.txt path")

    p_scenario = sub.add_parser("scenario", help="Evaluate scenario quality")
    _add_common_args(p_scenario)
    p_scenario.add_argument("--scenario-id", type=int, help="Evaluate a single scenario")
    p_scenario.add_argument("--all", action="store_true", help="Evaluate all scenarios")

    p_show = sub.add_parser("show", help="Show stored metrics from database")
    p_show.add_argument("--db-url", default=None)
    p_show.add_argument("--json", action="store_true", help="Output JSON")
    p_show.add_argument("--type", dest="target_type", required=True,
                        choices=["card", "fewshot", "response", "scene_state", "scenario"],
                        help="Target type to show metrics for")
    p_show.add_argument("--id", dest="target_id", default=None, help="Specific target ID")
    p_show.add_argument("--limit", type=int, default=20)

    p_report = sub.add_parser("report", help="Generate markdown conversation report")
    _add_common_args(p_report)
    p_report.add_argument("--conv-id", type=int, required=True, help="Conversation ID")
    p_report.add_argument("--log-path", default=None, help="Custom log.txt path")
    p_report.add_argument("--output", default=None, help="Output file path (default: stdout)")

    return parser


async def _warmup_model(ollama_url: str, model: str):
    """Send a throwaway request to load the model into memory."""
    print("Loading judge model...", end="", flush=True)
    t_load = time.time()
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{ollama_url}/api/chat",
                json={"model": model, "messages": [
                    {"role": "user", "content": "hi"}
                ], "stream": False},
                timeout=600.0,
            )
    except Exception:
        pass
    print(f" {time.time() - t_load:.1f}s\n")


def _print_progress(result: EvalResult, index: int, total: int,
                    elapsed: float, eval_times: list[float]):
    """Print compact progress line for a single eval result."""
    score_parts = []
    for s in result.scores:
        mark = str(s.score) if s.score >= 0 else "?"
        score_parts.append(f"{s.dimension[:5]}:{mark}")
    avg_time = sum(eval_times) / len(eval_times)
    remaining = total - (index + 1)
    eta = avg_time * remaining / 60
    print(
        f" {' '.join(score_parts)} avg={result.weighted_average:.1f} "
        f"({elapsed:.1f}s, ETA {eta:.0f}m)"
    )


def _print_results(results: list[EvalResult], rubric, label: str, as_json: bool):
    """Print aggregate report or JSON for a list of results."""
    if not results:
        print("No results.")
        return
    report = aggregate(results, rubric, label)
    if as_json:
        print(json.dumps(to_json(report, results), indent=2))
    else:
        print(format_report(report))
        ranked = sorted(results, key=lambda r: r.weighted_average)
        print("  Detailed explanations (bottom items):\n")
        for r in ranked[:5]:
            print(f"    #{r.target_id} ({r.weighted_average:.1f}):")
            for s in r.scores:
                if s.explanation:
                    print(f"      {s.dimension}: {s.explanation}")
            print()


async def _save_results(results: list[EvalResult], target_type: str,
                        rubric_name: str, pool: asyncpg.Pool):
    """Persist eval results to the database."""
    count = 0
    for r in results:
        scores_data = [
            {"dimension": s.dimension, "score": s.score, "explanation": s.explanation}
            for s in r.scores
        ]
        await save_metrics(
            domain=r.evaluator,
            target_type=target_type,
            target_id=r.target_id,
            target_label=r.target_label,
            judge_model=r.model,
            rubric_name=rubric_name,
            scores=scores_data,
            weighted_average=r.weighted_average,
            raw_judge_output=r.raw_judge_output,
            pool=pool,
        )
        count += 1
    print(f"  Saved {count} results to database.")


async def run_fewshot(args, pool: asyncpg.Pool, ollama_url: str):
    rubric = load_rubric("fewshot", Path(args.rubric) if args.rubric else None)

    # Single example mode
    if args.example_id:
        if args.dry_run:
            print(f"Would evaluate fewshot example {args.example_id}")
            return
        print(f"Evaluating fewshot example {args.example_id}...")
        result = await fewshot_eval.evaluate_single(
            pool, ollama_url, args.judge_model, args.example_id, rubric,
        )
        if args.json:
            print(json.dumps(to_json(
                aggregate([result], rubric, result.target_label), [result]
            ), indent=2))
        else:
            print(format_single(result, rubric))
        if args.save:
            await _save_results([result], "fewshot", rubric.name, pool)
        return

    # Batch mode
    if not args.card_id:
        print("Error: --card-id or --example-id required", file=sys.stderr)
        sys.exit(1)

    rows, card_fields, rubric = await fewshot_eval.evaluate_batch(
        pool, ollama_url, args.judge_model, args.card_id,
        limit=args.limit, rubric=rubric,
    )
    char_name = card_fields["name"]

    if not rows:
        print(f"No active fewshot examples for card {args.card_id} ({char_name})")
        return

    if args.dry_run:
        print(f"Would evaluate {len(rows)} fewshot examples for {char_name}\n")
        for i, row in enumerate(rows):
            preview = row["user_message"][:80].replace("\n", " ")
            model = row["model"] or "handcrafted"
            print(f"  [{i+1}] id={row['id']} model={model}")
            print(f"      User: {preview}...")
        return

    print(f"Judge: {args.judge_model}  Card: {char_name}  Examples: {len(rows)}")
    await _warmup_model(ollama_url, args.judge_model)

    results: list[EvalResult] = []
    eval_times: list[float] = []

    for i, row in enumerate(rows):
        preview = row["user_message"][:60].replace("\n", " ")
        print(f"[{i+1}/{len(rows)}] #{row['id']} {preview}...", end="", flush=True)
        try:
            context = fewshot_eval.build_context_for_row(row, card_fields)
            t0 = time.time()
            result = await judge(
                ollama_url, args.judge_model, rubric, context,
                evaluator="fewshot",
                target_id=str(row["id"]),
                target_label=f"{char_name} #{row['id']}",
            )
            elapsed = time.time() - t0
            eval_times.append(elapsed)
            results.append(result)
            _print_progress(result, i, len(rows), elapsed, eval_times)
        except Exception as e:
            print(f" ERROR: {type(e).__name__}: {e}" if str(e) else f" ERROR: {type(e).__name__}")

    _print_results(results, rubric, f"{char_name} fewshot examples", args.json)
    if args.save and results:
        await _save_results(results, "fewshot", rubric.name, pool)


async def run_card(args, pool: asyncpg.Pool, ollama_url: str):
    rubric = load_rubric("card", Path(args.rubric) if args.rubric else None)

    # Single card mode
    if args.card_id and not args.all:
        if args.dry_run:
            row = await pool.fetchrow(
                "SELECT name FROM rp_character_cards WHERE id = $1", args.card_id,
            )
            print(f"Would evaluate card {args.card_id} ({row['name'] if row else '?'})")
            return
        await _warmup_model(ollama_url, args.judge_model)
        result = await card_eval.evaluate_single(
            pool, ollama_url, args.judge_model, args.card_id, rubric,
        )
        if args.json:
            print(json.dumps(to_json(
                aggregate([result], rubric, result.target_label), [result]
            ), indent=2))
        else:
            print(format_single(result, rubric))
        if args.save:
            await _save_results([result], "card", rubric.name, pool)
        return

    # All cards mode
    if not args.all:
        print("Error: --card-id or --all required", file=sys.stderr)
        sys.exit(1)

    rows, rubric = await card_eval.evaluate_all(pool, ollama_url, args.judge_model, rubric)

    if args.limit and len(rows) > args.limit:
        rows = rows[:args.limit]

    if args.dry_run:
        print(f"Would evaluate {len(rows)} cards\n")
        for row in rows:
            print(f"  id={row['id']} {row['name']}")
        return

    print(f"Judge: {args.judge_model}  Cards: {len(rows)}")
    await _warmup_model(ollama_url, args.judge_model)

    results: list[EvalResult] = []
    eval_times: list[float] = []

    for i, row in enumerate(rows):
        print(f"[{i+1}/{len(rows)}] {row['name']}...", end="", flush=True)
        try:
            context = card_eval.build_context_for_row(row)
            t0 = time.time()
            result = await judge(
                ollama_url, args.judge_model, rubric, context,
                evaluator="card",
                target_id=str(row["id"]),
                target_label=row["name"],
            )
            elapsed = time.time() - t0
            eval_times.append(elapsed)
            results.append(result)
            _print_progress(result, i, len(rows), elapsed, eval_times)
        except Exception as e:
            print(f" ERROR: {type(e).__name__}: {e}" if str(e) else f" ERROR: {type(e).__name__}")

    _print_results(results, rubric, "All character cards", args.json)
    if args.save and results:
        await _save_results(results, "card", rubric.name, pool)


async def run_response(args, pool: asyncpg.Pool, ollama_url: str):
    rubric = load_rubric("response", Path(args.rubric) if args.rubric else None)
    log_path = Path(args.log_path) if args.log_path else None

    turns, conv, rubric = await response_eval.evaluate_conversation(
        ollama_url, args.judge_model, args.conv_id,
        rubric=rubric, limit=args.limit, log_path=log_path,
    )

    if not turns:
        print(f"No evaluable turns in conversation {args.conv_id}")
        return

    if args.dry_run:
        print(f"Would evaluate {len(turns)} turns in conv {args.conv_id} (model: {conv.model})\n")
        for t in turns:
            user_preview = t.user_message[:80].replace("\n", " ")
            print(f"  [turn {t.turn_index}] seq {t.seq_start}-{t.seq_end}")
            print(f"      User: {user_preview}...")
        return

    print(f"Judge: {args.judge_model}  Conv: {args.conv_id}  Turns: {len(turns)}  Model: {conv.model}")
    await _warmup_model(ollama_url, args.judge_model)

    results: list[EvalResult] = []
    eval_times: list[float] = []

    for i, turn in enumerate(turns):
        user_preview = turn.user_message[:60].replace("\n", " ")
        print(f"[{i+1}/{len(turns)}] turn{turn.turn_index} {user_preview}...", end="", flush=True)
        try:
            context = response_eval.build_context_for_turn(turn, conv)
            t0 = time.time()
            result = await judge(
                ollama_url, args.judge_model, rubric, context,
                evaluator="response",
                target_id=f"{conv.conv_id}:{turn.turn_index}",
                target_label=f"conv{conv.conv_id} turn{turn.turn_index}",
            )
            elapsed = time.time() - t0
            eval_times.append(elapsed)
            results.append(result)
            _print_progress(result, i, len(turns), elapsed, eval_times)
        except Exception as e:
            print(f" ERROR: {type(e).__name__}: {e}" if str(e) else f" ERROR: {type(e).__name__}")

    _print_results(results, rubric, f"Conv {args.conv_id} responses", args.json)
    if args.save and results:
        await _save_results(results, "response", rubric.name, pool)


async def run_scene_state(args, pool: asyncpg.Pool, ollama_url: str):
    rubric = load_rubric("scene_state", Path(args.rubric) if args.rubric else None)
    log_path = Path(args.log_path) if args.log_path else None

    turns, conv, rubric = await scene_state_eval.evaluate_conversation(
        ollama_url, args.judge_model, args.conv_id,
        rubric=rubric, limit=args.limit, log_path=log_path,
    )

    if not turns:
        print(f"No scene state updates in conversation {args.conv_id}")
        return

    if args.dry_run:
        print(f"Would evaluate {len(turns)} scene state updates in conv {args.conv_id}\n")
        for t in turns:
            before_len = len(t.scene_state_before)
            after_len = len(t.scene_state_after)
            print(f"  [turn {t.turn_index}] state: {before_len}c -> {after_len}c")
        return

    print(f"Judge: {args.judge_model}  Conv: {args.conv_id}  Updates: {len(turns)}")
    await _warmup_model(ollama_url, args.judge_model)

    results: list[EvalResult] = []
    eval_times: list[float] = []

    for i, turn in enumerate(turns):
        user_preview = turn.user_message[:60].replace("\n", " ")
        print(f"[{i+1}/{len(turns)}] turn{turn.turn_index} {user_preview}...", end="", flush=True)
        try:
            context = scene_state_eval.build_context_for_turn(turn)
            t0 = time.time()
            result = await judge(
                ollama_url, args.judge_model, rubric, context,
                evaluator="scene_state",
                target_id=f"{conv.conv_id}:{turn.turn_index}",
                target_label=f"conv{conv.conv_id} turn{turn.turn_index}",
            )
            elapsed = time.time() - t0
            eval_times.append(elapsed)
            results.append(result)
            _print_progress(result, i, len(turns), elapsed, eval_times)
        except Exception as e:
            print(f" ERROR: {type(e).__name__}: {e}" if str(e) else f" ERROR: {type(e).__name__}")

    _print_results(results, rubric, f"Conv {args.conv_id} scene states", args.json)
    if args.save and results:
        await _save_results(results, "scene_state", rubric.name, pool)


async def run_scenario(args, pool: asyncpg.Pool, ollama_url: str):
    rubric = load_rubric("scenario", Path(args.rubric) if args.rubric else None)

    # Single scenario mode
    if args.scenario_id and not args.all:
        if args.dry_run:
            row = await pool.fetchrow(
                "SELECT name FROM rp_scenarios WHERE id = $1", args.scenario_id,
            )
            print(f"Would evaluate scenario {args.scenario_id} ({row['name'] if row else '?'})")
            return
        await _warmup_model(ollama_url, args.judge_model)
        result = await scenario_eval.evaluate_single(
            pool, ollama_url, args.judge_model, args.scenario_id, rubric,
        )
        if args.json:
            print(json.dumps(to_json(
                aggregate([result], rubric, result.target_label), [result]
            ), indent=2))
        else:
            print(format_single(result, rubric))
        if args.save:
            await _save_results([result], "scenario", rubric.name, pool)
        return

    # All scenarios mode
    if not args.all:
        print("Error: --scenario-id or --all required", file=sys.stderr)
        sys.exit(1)

    rows, rubric = await scenario_eval.evaluate_all(
        pool, ollama_url, args.judge_model, rubric,
    )

    if args.limit and len(rows) > args.limit:
        rows = rows[:args.limit]

    if not rows:
        print("No scenarios found.")
        return

    if args.dry_run:
        print(f"Would evaluate {len(rows)} scenarios\n")
        for row in rows:
            print(f"  id={row['id']} {row['name']}")
        return

    print(f"Judge: {args.judge_model}  Scenarios: {len(rows)}")
    await _warmup_model(ollama_url, args.judge_model)

    results: list[EvalResult] = []
    eval_times: list[float] = []

    for i, row in enumerate(rows):
        print(f"[{i+1}/{len(rows)}] {row['name']}...", end="", flush=True)
        try:
            context = scenario_eval.build_context_for_row(row)
            t0 = time.time()
            result = await judge(
                ollama_url, args.judge_model, rubric, context,
                evaluator="scenario",
                target_id=str(row["id"]),
                target_label=row["name"],
            )
            elapsed = time.time() - t0
            eval_times.append(elapsed)
            results.append(result)
            _print_progress(result, i, len(rows), elapsed, eval_times)
        except Exception as e:
            print(f" ERROR: {type(e).__name__}: {e}" if str(e) else f" ERROR: {type(e).__name__}")

    _print_results(results, rubric, "All scenarios", args.json)
    if args.save and results:
        await _save_results(results, "scenario", rubric.name, pool)


async def run_show(args, pool: asyncpg.Pool):
    """Show stored metrics from the database."""
    rows = await get_metrics(
        target_type=args.target_type,
        target_id=args.target_id,
        limit=args.limit,
        pool=pool,
    )
    if not rows:
        print(f"No stored metrics for type={args.target_type}" +
              (f" id={args.target_id}" if args.target_id else ""))
        return

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return

    # Group by target_id, show latest per target
    seen = {}
    for r in rows:
        key = r["target_id"]
        if key not in seen:
            seen[key] = r

    for tid, r in seen.items():
        scores = r["scores"] if isinstance(r["scores"], list) else json.loads(r["scores"])
        score_parts = []
        for s in scores:
            mark = str(s["score"]) if s["score"] >= 0 else "?"
            score_parts.append(f"{s['dimension'][:5]}:{mark}")
        print(f"  [{r['target_label']}] avg={r['weighted_average']:.1f}  {' '.join(score_parts)}")
        print(f"    judge={r['judge_model']}  {r['created_at']}")
        for s in scores:
            if s.get("explanation"):
                print(f"    {s['dimension']}: {s['explanation']}")
        print()


async def run_report(args, pool: asyncpg.Pool, ollama_url: str):
    from .log_reader import parse_conversation
    from .evaluators import response as response_eval
    from .evaluators import scene_state as scene_state_eval
    from .markdown import render_report

    log_path = Path(args.log_path) if args.log_path else None
    response_rubric = load_rubric("response", Path(args.rubric) if args.rubric else None)
    scene_state_rubric = load_rubric("scene_state")

    # Step 1: Fetch conversation metadata from DB
    conv_row = await pool.fetchrow("""
        SELECT c.model, c.created_at,
               ai.name AS ai_card_name, u.name AS user_card_name
        FROM rp_conversations c
        JOIN rp_character_cards ai ON ai.id = c.ai_card_id
        JOIN rp_character_cards u ON u.id = c.user_card_id
        WHERE c.id = $1
    """, args.conv_id)
    if not conv_row:
        print(f"Conversation {args.conv_id} not found in database", file=sys.stderr)
        sys.exit(1)

    ai_card_name = conv_row["ai_card_name"]
    user_card_name = conv_row["user_card_name"]
    conv_date = conv_row["created_at"].strftime("%Y-%m-%d")

    # Step 2: Parse turns from log
    conv = parse_conversation(args.conv_id, log_path)
    if not conv:
        print(f"Conversation {args.conv_id} not found in log", file=sys.stderr)
        sys.exit(1)

    resp_turns = response_eval.get_evaluable_turns(conv)
    ss_turns = scene_state_eval.get_evaluable_turns(conv)

    if args.limit:
        resp_turns = resp_turns[:args.limit]
        ss_turns = ss_turns[:args.limit]

    if args.dry_run:
        print(f"Would generate report for conv {args.conv_id}")
        print(f"  AI: {ai_card_name}  User: {user_card_name}  Model: {conv.model}")
        print(f"  Response turns: {len(resp_turns)}  Scene state turns: {len(ss_turns)}")
        return

    total_evals = len(resp_turns) + len(ss_turns)
    print(f"Judge: {args.judge_model}  Conv: {args.conv_id}  Evals: {total_evals}")
    print(f"  {ai_card_name} × {user_card_name}  Model: {conv.model}")
    await _warmup_model(ollama_url, args.judge_model)

    # Step 3: Run response evals
    response_results: dict[int, EvalResult | str] = {}
    eval_times: list[float] = []
    all_response_results: list[EvalResult] = []

    for i, turn in enumerate(resp_turns):
        preview = turn.user_message[:60].replace("\n", " ")
        print(f"[resp {i+1}/{len(resp_turns)}] turn{turn.turn_index} {preview}...", end="", flush=True)
        try:
            context = response_eval.build_context_for_turn(turn, conv)
            t0 = time.time()
            result = await judge(
                ollama_url, args.judge_model, response_rubric, context,
                evaluator="response",
                target_id=f"{conv.conv_id}:{turn.turn_index}",
                target_label=f"conv{conv.conv_id} turn{turn.turn_index}",
            )
            elapsed = time.time() - t0
            eval_times.append(elapsed)
            response_results[turn.turn_index] = result
            all_response_results.append(result)
            _print_progress(result, i, len(resp_turns), elapsed, eval_times)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            print(f" ERROR: {msg}")
            response_results[turn.turn_index] = msg

    # Step 4: Run scene state evals
    scene_state_results: dict[int, EvalResult | str] = {}
    all_ss_results: list[EvalResult] = []
    eval_times.clear()

    for i, turn in enumerate(ss_turns):
        preview = turn.user_message[:60].replace("\n", " ")
        print(f"[scene {i+1}/{len(ss_turns)}] turn{turn.turn_index} {preview}...", end="", flush=True)
        try:
            context = scene_state_eval.build_context_for_turn(turn)
            t0 = time.time()
            result = await judge(
                ollama_url, args.judge_model, scene_state_rubric, context,
                evaluator="scene_state",
                target_id=f"{conv.conv_id}:{turn.turn_index}",
                target_label=f"conv{conv.conv_id} turn{turn.turn_index}",
            )
            elapsed = time.time() - t0
            eval_times.append(elapsed)
            scene_state_results[turn.turn_index] = result
            all_ss_results.append(result)
            _print_progress(result, i, len(ss_turns), elapsed, eval_times)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            print(f" ERROR: {msg}")
            scene_state_results[turn.turn_index] = msg

    # Save if requested
    if args.save:
        if all_response_results:
            await _save_results(all_response_results, "response", response_rubric.name, pool)
        if all_ss_results:
            await _save_results(all_ss_results, "scene_state", scene_state_rubric.name, pool)

    # Render markdown
    md = render_report(
        conv, response_results, scene_state_results,
        response_rubric, scene_state_rubric,
        args.judge_model, ai_card_name, user_card_name, conv_date,
    )

    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"\nReport written to {args.output}")
    else:
        print(f"\n{'=' * 60}\n")
        print(md)


async def main():
    parser = build_parser()
    args = parser.parse_args()

    db_url = getattr(args, "db_url", None) or os.environ.get(
        "DATABASE_URL", "postgresql://plum@localhost:5432/plum"
    )

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
    try:
        if args.command == "show":
            await run_show(args, pool)
            return

        ollama_url = resolve_url(args.ollama_url)

        if args.command == "fewshot":
            await run_fewshot(args, pool, ollama_url)
        elif args.command == "card":
            await run_card(args, pool, ollama_url)
        elif args.command == "response":
            await run_response(args, pool, ollama_url)
        elif args.command == "scene-state":
            await run_scene_state(args, pool, ollama_url)
        elif args.command == "scenario":
            await run_scenario(args, pool, ollama_url)
        elif args.command == "report":
            await run_report(args, pool, ollama_url)
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            sys.exit(1)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
