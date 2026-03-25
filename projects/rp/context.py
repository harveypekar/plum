class ContextStrategy:
    """Base class for context window management strategies."""

    def fit(self, messages: list[dict], max_tokens: int,
            token_counter=None, ctx: dict | None = None) -> list[dict]:
        raise NotImplementedError


class SlidingWindow(ContextStrategy):
    """Drop oldest messages first. Always keeps first message (greeting)."""

    def fit(self, messages: list[dict], max_tokens: int,
            token_counter=None, ctx: dict | None = None) -> list[dict]:
        if not messages:
            return []

        count = token_counter or (lambda t: len(t) // 4)

        # Always keep first message (character greeting)
        first = messages[0]
        rest = messages[1:]

        total = count(first["content"])
        kept = []

        # Add from newest to oldest
        for msg in reversed(rest):
            msg_tokens = count(msg["content"])
            if total + msg_tokens > max_tokens:
                break
            kept.insert(0, msg)
            total += msg_tokens

        return [first] + kept


class SummaryBuffer(ContextStrategy):
    """Rolling summary of older messages + recent messages verbatim.

    When a summary is available (via ctx["_summary"]), it is injected as a
    system message after the greeting. Messages already covered by the summary
    are excluded. The summary gets a soft 25% budget cap; unused budget flows
    to the recent message window.

    Falls back to SlidingWindow behavior when no summary exists.
    """

    def fit(self, messages: list[dict], max_tokens: int,
            token_counter=None, ctx: dict | None = None) -> list[dict]:
        if not messages:
            return []

        count = token_counter or (lambda t: len(t) // 4)
        ctx = ctx or {}

        # Always keep first message (character greeting)
        first = messages[0]
        rest = messages[1:]
        budget = max_tokens - count(first["content"])

        # Check for available summary
        summary = ctx.get("_summary")
        summary_through = ctx.get("_summary_through_sequence", 0)
        summary_msg = None

        if summary:
            summary_tokens = count(summary)
            cap = int(max_tokens * 0.25)
            if summary_tokens <= cap:
                summary_msg = {
                    "role": "system",
                    "content": f"[Story so far]\n{summary}",
                }
                budget -= summary_tokens
                # Exclude messages already covered by the summary
                rest = [m for m in rest
                        if m.get("_sequence", 0) > summary_through]

        # Fill recent messages newest-first (same as SlidingWindow)
        kept = []
        for msg in reversed(rest):
            msg_tokens = count(msg["content"])
            if budget - msg_tokens < 0:
                break
            kept.insert(0, msg)
            budget -= msg_tokens

        result = []
        if summary_msg:
            result.append(summary_msg)
        result.append(first)
        result.extend(kept)
        return result


STRATEGIES = {
    "sliding_window": SlidingWindow,
    "summary_buffer": SummaryBuffer,
}


def get_strategy(name: str = "sliding_window") -> ContextStrategy:
    cls = STRATEGIES.get(name, SlidingWindow)
    return cls()
