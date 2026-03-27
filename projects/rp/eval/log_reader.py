"""Parse conv_log.py NDJSON output into structured turns for evaluation.

Each conversation turn is: user message → (research?) → (fewshot?) → prompt → assistant response → (scene_state?)

The log reader correlates these events by sequence number and groups them
into Turn objects that the response and scene_state evaluators can consume.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[1] / "log.txt"


@dataclass
class Turn:
    """A single conversation turn with all associated pipeline events."""
    seq_start: int
    seq_end: int
    conv_id: int
    turn_index: int

    # Core message pair
    user_message: str = ""
    assistant_message: str = ""

    # Pipeline context
    endpoint: str = ""
    model: str = ""
    system_prompt: str = ""
    post_prompt: str = ""
    prompt_messages: list[dict] = field(default_factory=list)
    ollama_options: dict = field(default_factory=dict)

    # Injected context
    fewshot_count: int = 0
    fewshot_examples: list[dict] = field(default_factory=list)
    research_query: str = ""
    research_result: str = ""

    # Scene state (the update that happened *after* this turn)
    scene_state_before: str = ""
    scene_state_after: str = ""

    # Stats from Ollama response
    raw_stats: dict = field(default_factory=dict)


@dataclass
class Conversation:
    """A full conversation parsed from the log."""
    conv_id: int
    turns: list[Turn] = field(default_factory=list)
    model: str = ""

    @property
    def turn_count(self) -> int:
        return len(self.turns)


def parse_log(path: Path | None = None) -> dict[int, Conversation]:
    """Parse log.txt and return conversations keyed by conv_id."""
    log_path = path or LOG_PATH
    if not log_path.exists():
        return {}

    events: list[dict] = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    # Group by conv_id
    by_conv: dict[int, list[dict]] = {}
    for e in events:
        cid = e["conv_id"]
        by_conv.setdefault(cid, []).append(e)

    conversations = {}
    for conv_id, conv_events in by_conv.items():
        conv_events.sort(key=lambda e: e["seq"])
        conversations[conv_id] = _build_conversation(conv_id, conv_events)

    return conversations


def parse_conversation(conv_id: int, path: Path | None = None) -> Conversation | None:
    """Parse a single conversation from the log."""
    all_convs = parse_log(path)
    return all_convs.get(conv_id)


def _build_conversation(conv_id: int, events: list[dict]) -> Conversation:
    """Correlate events into turns for a single conversation.

    Turn boundary: each user-role response starts a new turn.
    Events between two user responses belong to the earlier turn.
    """
    conv = Conversation(conv_id=conv_id)
    current_turn: Turn | None = None
    turn_index = 0

    for e in events:
        etype = e["event"]

        if etype == "response" and e.get("role") == "user":
            # New turn starts
            if current_turn:
                conv.turns.append(current_turn)
            turn_index = len(conv.turns)
            current_turn = Turn(
                seq_start=e["seq"],
                seq_end=e["seq"],
                conv_id=conv_id,
                turn_index=turn_index,
                user_message=e.get("content", ""),
            )
            continue

        if current_turn is None:
            # Events before first user message (e.g., initial scene_state)
            if etype == "scene_state":
                # This is the conversation's initial state — attach to first turn later
                # Store as a pending initial state
                conv._initial_state = e.get("updated", "")
            continue

        # Update seq_end for this turn
        current_turn.seq_end = e["seq"]

        if etype == "research":
            current_turn.research_query = e.get("query", "")
            current_turn.research_result = e.get("result", "")

        elif etype == "fewshot":
            current_turn.fewshot_count = e.get("count", 0)
            current_turn.fewshot_examples = e.get("examples", [])

        elif etype == "prompt":
            current_turn.endpoint = e.get("endpoint", "")
            current_turn.model = e.get("model", "")
            current_turn.system_prompt = e.get("system_prompt", "")
            current_turn.post_prompt = e.get("post_prompt", "")
            current_turn.prompt_messages = e.get("messages", [])
            current_turn.ollama_options = e.get("ollama_options", {})
            if not conv.model:
                conv.model = current_turn.model

        elif etype == "response" and e.get("role") == "assistant":
            current_turn.assistant_message = e.get("content", "")
            current_turn.raw_stats = e.get("raw_stats", {})

        elif etype == "scene_state":
            current_turn.scene_state_before = e.get("previous", "")
            current_turn.scene_state_after = e.get("updated", "")

    # Don't forget the last turn
    if current_turn:
        conv.turns.append(current_turn)

    # Backfill initial scene state into first turn if it didn't get one
    initial = getattr(conv, "_initial_state", "")
    if initial and conv.turns and not conv.turns[0].scene_state_before:
        conv.turns[0].scene_state_before = initial
    # Clean up temp attribute
    if hasattr(conv, "_initial_state"):
        del conv._initial_state

    return conv
