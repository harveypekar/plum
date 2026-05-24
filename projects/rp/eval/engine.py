"""Core evaluation engine: rubric loading, judge prompt assembly, LLM scoring, result parsing.

Uses G-Eval pattern: chain-of-thought rubric in the system prompt, content to evaluate
in the user message, structured score output parsed from the judge's response.
"""

import json
import re
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

RUBRICS_DIR = Path(__file__).parent / "rubrics"


@dataclass
class Dimension:
    key: str
    name: str
    weight: float
    criteria: str
    context_requires: list[str]


@dataclass
class Rubric:
    name: str
    description: str
    scale_min: int
    scale_max: int
    dimensions: list[Dimension]


@dataclass
class DimensionScore:
    dimension: str
    score: int
    explanation: str


@dataclass
class EvalResult:
    evaluator: str
    target_id: str
    target_label: str
    scores: list[DimensionScore]
    weighted_average: float
    raw_judge_output: str
    model: str
    timestamp: str


def load_rubric(domain: str, path: Path | None = None) -> Rubric:
    """Load a TOML rubric file. Use `path` for custom rubrics, or `domain` for built-in."""
    rubric_path = path or (RUBRICS_DIR / f"{domain}.toml")
    with open(rubric_path, "rb") as f:
        data = tomllib.load(f)
    meta = data["meta"]
    dimensions = []
    for key, dim in data["dimensions"].items():
        dimensions.append(Dimension(
            key=key,
            name=dim["name"],
            weight=dim.get("weight", 1.0),
            criteria=dim["criteria"].strip(),
            context_requires=dim.get("context_requires", []),
        ))
    return Rubric(
        name=meta["name"],
        description=meta.get("description", ""),
        scale_min=meta["scale_min"],
        scale_max=meta["scale_max"],
        dimensions=dimensions,
    )


def build_judge_prompt(rubric: Rubric, context: dict) -> tuple[str, str]:
    """Build system + user messages for the LLM judge.

    Returns (system_prompt, user_message).
    """
    dim_blocks = []
    for dim in rubric.dimensions:
        dim_blocks.append(
            f"### {dim.key} — {dim.name} (weight {dim.weight}x)\n{dim.criteria}"
        )
    dimensions_text = "\n\n".join(dim_blocks)

    dim_keys = "\n".join(f"[{dim.key}]" for dim in rubric.dimensions)

    system_prompt = (
        f"You are an expert evaluator of roleplay writing quality.\n"
        f"Evaluate the content below on {len(rubric.dimensions)} dimensions.\n"
        f"Scale: {rubric.scale_min} (worst) to {rubric.scale_max} (best).\n\n"
        f"IMPORTANT: You are EVALUATING the writing, not continuing it. "
        f"Do NOT write fiction or continue the story.\n\n"
        f"Output EXACTLY {len(rubric.dimensions)} blocks using THESE "
        f"dimension keys (no other keys):\n\n"
        f"{dim_keys}\n\n"
        f"Format for each block:\n\n"
        f"[dimension_key]\n"
        f"Score: N\n"
        f"Explanation: 1-2 sentences.\n\n"
        f"=== EVALUATION CRITERIA ===\n\n{dimensions_text}"
    )

    # Build the user message from the context dict
    sections = []
    for key, value in context.items():
        if value and isinstance(value, str) and value.strip():
            label = key.replace("_", " ").title()
            sections.append(f"### {label}\n{value}")
        elif value and isinstance(value, list):
            label = key.replace("_", " ").title()
            formatted = "\n".join(
                f"  {m.get('role', '?')}: {m.get('content', '')}"
                for m in value
                if isinstance(m, dict)
            )
            if formatted:
                sections.append(f"### {label}\n{formatted}")

    user_message = (
        "=== CONTENT TO EVALUATE ===\n\n"
        + "\n\n".join(sections)
        + "\n\n=== END OF CONTENT ===\n\n"
        "Output ONLY the evaluation scores in the format specified above. "
        "Do NOT continue the story."
    )
    return system_prompt, user_message


def _rescale(raw_score: int, raw_max: int, rubric: Rubric) -> int:
    """Rescale a score from an arbitrary range to the rubric's scale."""
    if raw_max <= rubric.scale_max:
        return max(rubric.scale_min, min(rubric.scale_max, raw_score))
    scaled = round(raw_score / raw_max * rubric.scale_max)
    return max(rubric.scale_min, min(rubric.scale_max, scaled))


def _extract_score_from_text(text: str, rubric: Rubric) -> int:
    """Extract a numeric score from text, handling Score: N, N/M, and : N."""
    m = re.search(r"Score:\s*(\d+)", text, re.IGNORECASE)
    if m:
        return _rescale(int(m.group(1)), rubric.scale_max, rubric)
    m = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if m:
        return _rescale(int(m.group(1)), int(m.group(2)), rubric)
    m = re.search(r":\s*(\d+)\b", text)
    if m:
        raw = int(m.group(1))
        raw_max = 10 if raw > rubric.scale_max else rubric.scale_max
        return _rescale(raw, raw_max, rubric)
    return -1


def _extract_explanation(block: str) -> str:
    """Extract explanation text from a score block."""
    m = re.search(r"Explanation:\s*(.+)", block, re.IGNORECASE | re.DOTALL)
    if m:
        text = m.group(1).strip()
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return " ".join(sentences[:3])
    lines = [ln.strip() for ln in block.split('\n') if ln.strip()]
    text_lines = [ln for ln in lines
                  if not re.match(r'^\s*(?:Score|[\d\[#*])', ln, re.IGNORECASE)]
    if text_lines:
        return " ".join(text_lines[:2])[:200]
    return ""


def parse_scores(raw_response: str, rubric: Rubric) -> list[DimensionScore]:
    """Parse structured scores from the judge's response.

    Handles multiple output formats: [key]\\nScore: N, key: N/10,
    N. **Name**: N/10, and numbered lists.
    """
    all_ids = []
    for dim in rubric.dimensions:
        all_ids.append(re.escape(dim.key))
        if dim.name.lower() != dim.key.lower():
            all_ids.append(re.escape(dim.name))

    # Match [key], **key**, ### key, key:, N. key, N. **key**
    header_pattern = (
        r"(?:^|\n)\s*(?:\d+\.\s*)?(?:\[|\*\*|###?\s*)?"
        r"(" + "|".join(all_ids) + r")"
        r"(?:\]|\*\*|)?\s*(?:[—:][^\n]*)?\n?"
    )
    splits = list(re.finditer(header_pattern, raw_response, re.IGNORECASE))

    blocks: dict[str, str] = {}
    for i, m in enumerate(splits):
        matched_id = m.group(1).strip().lower()
        start = m.start()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(raw_response)
        block_text = raw_response[start:end]
        for dim in rubric.dimensions:
            if matched_id in (dim.key.lower(), dim.name.lower()):
                blocks[dim.key] = block_text
                break

    scores = []
    for dim in rubric.dimensions:
        block = blocks.get(dim.key, "")
        score = _extract_score_from_text(block, rubric) if block else -1

        if score < 0:
            for ident in (dim.key, dim.name):
                m = re.search(
                    rf"{re.escape(ident)}[^\n]*?(\d+)\s*/\s*(\d+)",
                    raw_response, re.IGNORECASE,
                )
                if m:
                    score = _rescale(int(m.group(1)), int(m.group(2)), rubric)
                    break
                m = re.search(
                    rf"{re.escape(ident)}[^\n]*?Score:\s*(\d+)",
                    raw_response, re.IGNORECASE,
                )
                if m:
                    score = _rescale(int(m.group(1)), rubric.scale_max, rubric)
                    break

        explanation = _extract_explanation(block) if block else ""
        scores.append(DimensionScore(
            dimension=dim.key,
            score=score,
            explanation=explanation,
        ))
    return scores


def compute_weighted_average(scores: list[DimensionScore], rubric: Rubric) -> float:
    """Compute weighted average across scored dimensions."""
    dim_weights = {d.key: d.weight for d in rubric.dimensions}
    total_weight = 0.0
    total_score = 0.0
    for s in scores:
        if s.score < 0:
            continue
        w = dim_weights.get(s.dimension, 1.0)
        total_score += s.score * w
        total_weight += w
    if total_weight == 0:
        return 0.0
    return total_score / total_weight


async def judge(
    aiserver_url: str,
    model: str,
    rubric: Rubric,
    context: dict,
    evaluator: str = "",
    target_id: str = "",
    target_label: str = "",
) -> EvalResult:
    """Run the LLM judge on a single item and return structured scores."""
    system_prompt, user_message = build_judge_prompt(rubric, context)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{aiserver_url}/chat",
            json={
                "model": model,
                "messages": messages,
                "priority": 10,
                "options": {"temperature": 0.3, "num_predict": 2048},
            },
            timeout=httpx.Timeout(1800.0, connect=30.0),
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise RuntimeError(f"aiserver {resp.status_code}: {body[:300]}")
            tokens = []
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if "error" in chunk:
                    raise RuntimeError(f"aiserver error: {chunk['error']}")
                tok = chunk.get("token", "")
                if tok and not chunk.get("thinking", False):
                    tokens.append(tok)
            raw_output = "".join(tokens)

    scores = parse_scores(raw_output, rubric)
    weighted_avg = compute_weighted_average(scores, rubric)

    return EvalResult(
        evaluator=evaluator,
        target_id=target_id,
        target_label=target_label,
        scores=scores,
        weighted_average=weighted_avg,
        raw_judge_output=raw_output,
        model=model,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    )
