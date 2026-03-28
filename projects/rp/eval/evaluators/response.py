"""Response evaluator.

Evaluates individual assistant responses from conversation logs,
using the full pipeline context captured by conv_log.py.
"""

from pathlib import Path

from ..engine import EvalResult, Rubric, judge, load_rubric
from ..log_reader import Conversation, Turn, parse_conversation


def _format_history(turns: list[Turn], up_to: int) -> str:
    """Format recent conversation history leading up to a turn."""
    # Include last 3 turns for context (6 messages)
    start = max(0, up_to - 3)
    lines = []
    for t in turns[start:up_to]:
        if t.user_message:
            lines.append(f"user: {t.user_message}")
        if t.assistant_message:
            lines.append(f"assistant: {t.assistant_message}")
    return "\n\n".join(lines)


def build_context_for_turn(turn: Turn, conv: Conversation) -> dict:
    """Assemble the context dict for judging a single response turn."""
    history = _format_history(conv.turns, turn.turn_index)

    return {
        "system_prompt": turn.system_prompt,
        "scene_state": turn.scene_state_before,
        "conversation_history": history,
        "user_message": turn.user_message,
        "assistant_message": turn.assistant_message,
    }


def get_evaluable_turns(conv: Conversation) -> list[Turn]:
    """Return turns that have both user and assistant messages."""
    return [t for t in conv.turns if t.user_message and t.assistant_message]


async def evaluate_turn(
    aiserver_url: str,
    judge_model: str,
    turn: Turn,
    conv: Conversation,
    rubric: Rubric | None = None,
) -> EvalResult:
    """Evaluate a single response turn."""
    rubric = rubric or load_rubric("response")
    context = build_context_for_turn(turn, conv)

    return await judge(
        aiserver_url, judge_model, rubric, context,
        evaluator="response",
        target_id=f"{conv.conv_id}:{turn.turn_index}",
        target_label=f"conv{conv.conv_id} turn{turn.turn_index}",
    )


async def evaluate_conversation(
    aiserver_url: str,
    judge_model: str,
    conv_id: int,
    rubric: Rubric | None = None,
    limit: int = 0,
    log_path: Path | None = None,
) -> tuple[list[Turn], Conversation, Rubric]:
    """Load a conversation and return evaluable turns.

    Caller drives the eval loop (same pattern as fewshot/card batch).
    """
    rubric = rubric or load_rubric("response")
    conv = parse_conversation(conv_id, log_path)
    if not conv:
        raise ValueError(f"Conversation {conv_id} not found in log")

    turns = get_evaluable_turns(conv)
    if limit and len(turns) > limit:
        turns = turns[:limit]

    return turns, conv, rubric
