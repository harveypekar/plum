"""Core evaluation engine: rubric loading, judge prompt assembly, LLM scoring, result parsing.

Uses G-Eval pattern: chain-of-thought rubric in the system prompt, content to evaluate
in the user message, structured score output parsed from the judge's response.
"""

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

    system_prompt = (
        f"You are an expert evaluator of roleplay writing quality.\n"
        f"Evaluate the content below on {len(rubric.dimensions)} dimensions.\n"
        f"Scale: {rubric.scale_min} (worst) to {rubric.scale_max} (best).\n\n"
        f"For each dimension, reason step-by-step about the criteria, "
        f"then assign a score.\n\n"
        f"Output format — one block per dimension, in this exact order:\n\n"
        f"[dimension_key]\n"
        f"Score: N\n"
        f"Explanation: Your reasoning in 1-2 sentences.\n\n"
        f"Evaluate ALL dimensions listed below. Do not skip any.\n\n"
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

    user_message = "=== CONTENT TO EVALUATE ===\n\n" + "\n\n".join(sections)
    return system_prompt, user_message


def parse_scores(raw_response: str, rubric: Rubric) -> list[DimensionScore]:
    """Parse structured scores from the judge's response.

    Strategy: find each dimension's section by its key or name header,
    then extract Score and Explanation from that section only.
    """
    # Build a list of all dimension identifiers (keys and names) for splitting
    all_ids = []
    for dim in rubric.dimensions:
        all_ids.append(re.escape(dim.key))
        if dim.name.lower() != dim.key.lower():
            all_ids.append(re.escape(dim.name))

    # Split response into sections by dimension headers
    # Match [key], **key**, ### key, or bare key on its own line followed by newline
    header_pattern = (
        r"(?:^|\n)\s*(?:\[|\*\*|###?\s*)?"
        r"(" + "|".join(all_ids) + r")"
        r"(?:\]|\*\*|)?\s*(?:—[^\n]*)?\n"
    )
    splits = list(re.finditer(header_pattern, raw_response, re.IGNORECASE))

    # Map each dimension key to its text block
    blocks: dict[str, str] = {}
    for i, m in enumerate(splits):
        matched_id = m.group(1).strip().lower()
        start = m.end()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(raw_response)
        block_text = raw_response[start:end]
        # Map to canonical dimension key
        for dim in rubric.dimensions:
            if matched_id in (dim.key.lower(), dim.name.lower()):
                blocks[dim.key] = block_text
                break

    scores = []
    for dim in rubric.dimensions:
        block = blocks.get(dim.key, "")

        # Extract score
        score = -1
        score_match = re.search(r"Score:\s*(\d+)", block, re.IGNORECASE)
        if score_match:
            score = int(score_match.group(1))
            score = max(rubric.scale_min, min(rubric.scale_max, score))
        elif not block:
            # Fallback: search whole response for this dimension's score
            fallback = re.search(
                rf"{re.escape(dim.key)}[^\n]*Score:\s*(\d+)",
                raw_response, re.IGNORECASE,
            )
            if fallback:
                score = int(fallback.group(1))
                score = max(rubric.scale_min, min(rubric.scale_max, score))

        # Extract explanation
        explanation = ""
        exp_match = re.search(r"Explanation:\s*(.+)", block, re.IGNORECASE | re.DOTALL)
        if exp_match:
            explanation = exp_match.group(1).strip()
            # Trim to first 2-3 sentences
            sentences = re.split(r'(?<=[.!?])\s+', explanation)
            explanation = " ".join(sentences[:3])

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
        resp = await client.post(
            f"{aiserver_url}/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "priority": 10,
                "options": {"temperature": 0.3, "num_predict": 4096, "think": True},
            },
            timeout=1800.0,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"aiserver {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"aiserver error: {data['error']}")
        raw_output = data["message"]["content"]

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
