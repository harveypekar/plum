"""Hard-gate heuristic filter for LoRA training data curation."""

from dataclasses import dataclass


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
    stock_count = _count_stock_phrases(assistant_message)
    overlap = _trigram_overlap(assistant_message, previous_assistant_messages[-3:])

    user_len = max(len(user_message.split()), 1)
    asst_len = len(assistant_message.split())
    length_ratio = asst_len / user_len

    is_long = length_ratio > LENGTH_RATIO_THRESHOLD

    if stock_count >= 2:
        return FilterResult(
            passed=False,
            reason="stock_phrases",
            stock_phrase_count=stock_count,
            trigram_overlap=overlap,
            length_ratio=length_ratio,
        )

    if overlap > REPETITION_THRESHOLD:
        return FilterResult(
            passed=False,
            reason="repetition",
            stock_phrase_count=stock_count,
            trigram_overlap=overlap,
            length_ratio=length_ratio,
        )

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
