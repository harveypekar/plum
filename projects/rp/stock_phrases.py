"""Post-hook that rewrites stock phrases in AI responses via targeted model call."""

import logging

_log = logging.getLogger("rp.stock_phrases")

REWRITE_MODEL = "q25"

_REWRITE_PROMPT = """\
The AI response below contains cliché stock phrases. Replace ONLY the listed \
phrases with vivid, character-specific physical details for {ai_name}. Keep \
everything else exactly the same — same structure, same length, same meaning.

Stock phrases to replace:
{phrase_list}

Original response:
{response}

Rewritten response (change ONLY the stock phrases, nothing else):"""


def make_stock_phrase_rewriter(ollama, resolve_model=None):
    """Return an async post-hook that rewrites stock phrases via a fast model call."""

    async def rewrite_stock_phrases(ctx: dict) -> dict:
        violations = ctx.get("_stock_phrase_violations")
        if not violations:
            return ctx

        response = ctx.get("response", "")
        ai_name = ctx.get("ai_name", "Character")

        phrase_list = "\n".join(f"- \"{v}\"" for v in violations)
        prompt = _REWRITE_PROMPT.format(
            ai_name=ai_name, phrase_list=phrase_list, response=response,
        )

        model = resolve_model(REWRITE_MODEL) if resolve_model else REWRITE_MODEL

        try:
            result = await ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.7, "num_predict": 2048},
            )
            rewritten = result.get("message", {}).get("content", "").strip()
            if not rewritten or len(rewritten) < len(response) * 0.5:
                _log.warning("Stock phrase rewrite too short, keeping original")
                return ctx

            ctx["response"] = rewritten
            ctx["_stock_phrases_rewritten"] = True
            _log.info(
                "Rewrote %d stock phrase(s) for %s", len(violations), ai_name,
            )
        except Exception as e:
            _log.warning("Stock phrase rewrite failed: %s", e)

        return ctx

    return rewrite_stock_phrases
