"""Fast offline token counting using tiktoken.

Used as the estimator for budget shrink loops. Ground-truth counting
still happens via Ollama (see budget.py), but this is ~10x more accurate
than the old len(text)//4 heuristic for deciding when to shrink.
"""

import tiktoken

_enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_enc.encode(text, disallowed_special=()))
