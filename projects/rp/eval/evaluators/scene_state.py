"""Scene state evaluator.

Evaluates the quality of scene state updates from conversation logs
by comparing previous/updated states against the messages that occurred.
"""

from pathlib import Path

from ..engine import EvalResult, Rubric, judge, load_rubric
from ..log_reader import Conversation, Turn, parse_conversation


def build_context_for_turn(turn: Turn) -> dict:
    """Assemble the context dict for judging a scene state update."""
    return {
        "user_message": turn.user_message,
        "assistant_message": turn.assistant_message,
        "previous_state": turn.scene_state_before or "(no previous state)",
        "updated_state": turn.scene_state_after or "(no updated state)",
    }


def get_evaluable_turns(conv: Conversation) -> list[Turn]:
    """Return turns that have scene state updates."""
    return [
        t for t in conv.turns
        if t.scene_state_after and t.assistant_message
    ]


async def evaluate_turn(
    aiserver_url: str,
    judge_model: str,
    turn: Turn,
    rubric: Rubric | None = None,
) -> EvalResult:
    """Evaluate a single scene state update."""
    rubric = rubric or load_rubric("scene_state")
    context = build_context_for_turn(turn)

    return await judge(
        aiserver_url, judge_model, rubric, context,
        evaluator="scene_state",
        target_id=f"{turn.conv_id}:{turn.turn_index}",
        target_label=f"conv{turn.conv_id} turn{turn.turn_index}",
    )


async def evaluate_conversation(
    aiserver_url: str,
    judge_model: str,
    conv_id: int,
    rubric: Rubric | None = None,
    limit: int = 0,
    log_path: Path | None = None,
) -> tuple[list[Turn], Conversation, Rubric]:
    """Load a conversation and return turns with scene state updates.

    Caller drives the eval loop.
    """
    rubric = rubric or load_rubric("scene_state")
    conv = parse_conversation(conv_id, log_path)
    if not conv:
        raise ValueError(f"Conversation {conv_id} not found in log")

    turns = get_evaluable_turns(conv)
    if limit and len(turns) > limit:
        turns = turns[:limit]

    return turns, conv, rubric
