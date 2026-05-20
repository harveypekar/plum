"""Lorebook (World Info) — keyword-triggered prompt injection.

Entries stored in rp_lorebook_entries, matched against recent messages,
injected into system_prompt based on position field.
"""

import logging
from . import db
from .tokenizer import count_tokens

_log = logging.getLogger("rp.lorebook")


def _keywords_match(text: str, keys: list[str]) -> bool:
    haystack = text.lower()
    return any(k and k.lower() in haystack for k in keys)


def match_entries(entries: list[dict], messages: list[dict],
                  scan_depth: int = 10) -> list[dict]:
    """Return entries whose keywords appear in recent messages.

    Constant entries always match. Selective entries require both primary
    AND secondary key hits. Results sorted by insertion_order.
    """
    window = messages[-scan_depth:] if scan_depth > 0 else messages
    combined = "\n".join(m.get("content", "") for m in window)

    matched = []
    for entry in entries:
        if not entry.get("enabled", True):
            continue
        if not entry.get("content", "").strip():
            continue

        if entry.get("constant", False):
            matched.append(entry)
            continue

        keys = entry.get("keys", [])
        if not keys or not _keywords_match(combined, keys):
            continue

        if entry.get("selective", False):
            secondary = entry.get("secondary_keys", [])
            if secondary and not _keywords_match(combined, secondary):
                continue

        matched.append(entry)

    matched.sort(key=lambda e: e.get("insertion_order", 100))
    return matched


def build_injection_text(matched_entries: list[dict]) -> tuple[str, str]:
    """Split matched entries into (before_char, after_char) text blocks."""
    before, after = [], []
    for entry in matched_entries:
        text = entry.get("content", "").strip()
        if not text:
            continue
        if entry.get("position", "after_char") == "before_char":
            before.append(text)
        else:
            after.append(text)
    return "\n\n".join(before), "\n\n".join(after)


async def inject_lorebook(ctx: dict) -> dict:
    """Pipeline pre-hook: match lorebook entries and inject into system_prompt."""
    ai_card = ctx.get("ai_card") or {}
    card_id = ai_card.get("id")
    if not card_id:
        return ctx

    lorebook = await db.get_lorebook_for_card(card_id)
    if not lorebook or not lorebook.get("enabled", True):
        return ctx

    entries = await db.get_lorebook_entries(lorebook["id"])
    if not entries:
        return ctx

    matched = match_entries(
        entries, ctx.get("messages", []), lorebook.get("scan_depth", 10))
    if not matched:
        return ctx

    before_text, after_text = build_injection_text(matched)

    if before_text:
        ctx["system_prompt"] = before_text + "\n\n" + ctx.get("system_prompt", "")
    if after_text:
        ctx["system_prompt"] = ctx.get("system_prompt", "") + "\n\n[World Info]\n" + after_text

    names = [e.get("name") or (e.get("keys", ["?"])[0] if e.get("keys") else "?")
             for e in matched]
    ctx["_lorebook_injected"] = names
    ctx["_lorebook_tokens"] = count_tokens(before_text + after_text)
    _log.info("Lorebook: injected %d entries (%d tokens): %s",
              len(matched), ctx["_lorebook_tokens"], names[:5])
    return ctx


def extract_character_book(card_data: dict) -> dict | None:
    """Extract character_book from SillyTavern v2 card_data, or None."""
    data = card_data.get("data", card_data)
    return data.get("character_book") or None
