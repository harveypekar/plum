"""Per-message evaluator — scores individual assistant messages from the DB."""

from ..engine import EvalResult, Rubric, judge, load_rubric


def get_scoreable_messages(messages: list[dict]) -> list[dict]:
    """Filter to assistant messages that have pipeline context stored."""
    return [
        m for m in messages
        if m["role"] == "assistant" and m.get("system_prompt") is not None
    ]


def build_context_for_message(msg: dict, history: list[dict]) -> dict:
    """Assemble the context dict for judging a single message."""
    user_message = ""
    for h in reversed(history):
        if h["role"] == "user":
            user_message = h["content"]
            break

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
