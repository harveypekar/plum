#!/usr/bin/env python3
"""Automated PR review agent using Claude API.

Triggered by GitHub Actions on every PR open/sync. Posts a review
comment with findings on bugs, security, quality, and conventions.
"""

import json
import os
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REVIEW_MODEL = "claude-sonnet-4-6"
MAX_DIFF_CHARS = 120_000
MAX_TOKENS = 3000

SYSTEM_PROMPT = """\
You are a code reviewer for the Plum monorepo. Review the PR diff below.

Project conventions:
- Commit messages: imperative mood, type-prefixed (feat:, fix:, docs:, chore:)
- Line endings: Unix LF, never CRLF
- Shell scripts must pass shellcheck
- Never put secrets, API keys, passwords, or PII in code or logs
- Secrets go in .env only (never committed)
- Python preferred over bash when logic gets complex
- Agents commit under their own name/email, never the user's

Review focus (in priority order):
1. Security issues (secrets in code, injection, unsafe patterns)
2. Bugs and logic errors
3. Missing error handling at system boundaries
4. Convention violations from the list above
5. Code clarity — only flag if genuinely confusing

Rules for your review:
- Be concise. Use short bullet points, not paragraphs.
- Only flag real issues. Do not nitpick style, naming, or formatting.
- If the PR looks good, say so in one line. Do not pad with generic praise.
- Group findings under headings: Security, Bugs, Conventions, Suggestions.
- Omit empty sections entirely.
- For each issue, reference the file and line if possible.
"""


PR_SIZE_WARN = 1000  # lines added — warn above this


def run(cmd: list[str], *, binary: bool = False) -> str | bytes:
    result = subprocess.run(cmd, capture_output=True, check=True,
                            text=not binary)
    return result.stdout if binary else result.stdout.strip()


def get_pr_diff(pr_number: str, repo: str) -> str:
    raw = run(["gh", "pr", "diff", pr_number, "--repo", repo], binary=True)
    return raw.decode("utf-8", errors="replace").strip()


def get_pr_info(pr_number: str, repo: str) -> dict:
    raw = run(["gh", "pr", "view", pr_number, "--repo", repo,
               "--json", "title,body"])
    return json.loads(raw)


def call_claude(diff: str, pr_info: dict, api_key: str) -> str:
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n\n... (diff truncated)"

    user_msg = (
        f"PR title: {pr_info['title']}\n"
        f"PR description: {pr_info.get('body') or '(none)'}\n\n"
        f"Diff:\n```\n{diff}\n```"
    )

    body = json.dumps({
        "model": REVIEW_MODEL,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_msg}],
    }).encode()

    req = Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return data["content"][0]["text"]
    except HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"API error {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


def get_pr_stats(pr_number: str, repo: str) -> dict:
    raw = run(["gh", "pr", "view", pr_number, "--repo", repo,
               "--json", "additions,deletions"])
    return json.loads(raw)


def post_review(pr_number: str, repo: str, review_text: str) -> None:
    body = f"## Automated Review\n\n{review_text}"
    subprocess.run(
        ["gh", "pr", "review", pr_number, "--repo", repo,
         "--comment", "--body", body],
        check=True,
    )


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    pr_number = os.environ.get("PR_NUMBER")
    repo = os.environ.get("GITHUB_REPOSITORY")

    missing = []
    if not api_key:
        missing.append("ANTHROPIC_API_KEY")
    if not pr_number:
        missing.append("PR_NUMBER")
    if not repo:
        missing.append("GITHUB_REPOSITORY")
    if missing:
        print(f"Missing env vars: {', '.join(missing)}", file=sys.stderr)
        if "ANTHROPIC_API_KEY" in missing and len(missing) == 1:
            print("Skipping review (no API key configured).", file=sys.stderr)
            return
        sys.exit(1)

    print(f"Reviewing PR #{pr_number} in {repo}...")
    diff = get_pr_diff(pr_number, repo)

    if not diff.strip():
        print("Empty diff, skipping review.")
        return

    stats = get_pr_stats(pr_number, repo)
    additions = stats.get("additions", 0)
    size_note = ""
    if additions > PR_SIZE_WARN:
        size_note = (
            f"\n\n> **Size warning**: this PR adds **{additions:,}** lines "
            f"(threshold: {PR_SIZE_WARN:,}). Consider splitting into "
            "smaller, reviewable chunks."
        )

    pr_info = get_pr_info(pr_number, repo)
    review = call_claude(diff, pr_info, api_key)
    post_review(pr_number, repo, review + size_note)
    print(f"Review posted on PR #{pr_number}")


if __name__ == "__main__":
    main()
