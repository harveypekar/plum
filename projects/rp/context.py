class ContextStrategy:
    """Base class for context window management strategies."""

    def fit(self, messages: list[dict], max_tokens: int,
            token_counter=None) -> list[dict]:
        raise NotImplementedError


class SlidingWindow(ContextStrategy):
    """Drop oldest messages first. Always keeps first message (greeting)."""

    def fit(self, messages: list[dict], max_tokens: int,
            token_counter=None) -> list[dict]:
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


STRATEGIES = {
    "sliding_window": SlidingWindow,
}


def get_strategy(name: str = "sliding_window") -> ContextStrategy:
    cls = STRATEGIES.get(name, SlidingWindow)
    return cls()
