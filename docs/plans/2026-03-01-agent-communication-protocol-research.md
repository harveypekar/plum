# Structured Agent Communication for plum-audit

**Created:** 2026-03-01
**Type:** Research report
**Scope:** Structured JSON protocol for parallel audit agents, applied to plum-audit

---

## 1. Background and Motivation

### How plum-audit works today

plum-audit is a Claude Code skill that audits the Plum project across six sections: security, quality, docs, infra, claude, and testing. It runs as a single agent that executes checks serially, interprets results inline, and writes prose findings directly into a markdown report at `docs/audits/YYYY-MM-DD-audit.md`.

The current flow is:

```
run shell command → interpret output → write prose finding → next check
```

Each check is self-contained: a bash command followed by interpretation rules ("if X, flag as [CRITICAL]"). The skill file (`.claude/skills/plum-audit/SKILL.md`) contains all six sections as sequential prompt blocks. There is no intermediate data format — findings exist only as markdown text in the final report.

### What this limits

**Serial execution.** All six sections run sequentially within one agent context. The total audit time is the sum of all sections. Docker builds (infra section) alone can take minutes, during which the security, quality, and testing sections sit idle.

**No structured data.** Findings are prose. A downstream system that wants to act on findings (create issues, apply fixes, compare across runs) must parse natural language. This is fragile and lossy.

**No selective re-runs.** If the infra section fails because Docker isn't running, the only option is to re-run the entire audit. There's no way to say "keep the results from the other 5 sections, just redo infra."

**No cross-section analysis.** The security agent and the testing agent can't see each other's findings. A file that has both a security vulnerability and no test coverage is a compound risk, but this connection only surfaces if the human reading the report notices it.

**No audit history.** Each run produces a standalone markdown file. Comparing "what changed since last audit" requires a human reading two reports side by side. There's no programmatic way to identify new findings, resolved findings, or persistent issues.

### What a structured protocol would enable

The core idea: insert a structured intermediate format between "agent runs checks" and "human reads report." Agents write structured findings (JSON). A coordinator reads all structured findings and produces outputs: the markdown report (same as today), but also diffs against previous audits, compound findings from cross-referencing, and a machine-readable feed for downstream automation (issue creation, auto-fix branches).

---

## 2. The Problem Space

### Agent-to-agent communication patterns

The broader question behind plum-audit is: how do autonomous agents share information with each other? This is a well-studied problem in distributed systems and multi-agent AI. Several patterns exist, each with different trade-offs.

#### 2.1 Blackboard architecture

A shared data structure (the "blackboard") that all agents can read from and write to. Each agent watches for changes relevant to its role and contributes its own findings. A control component decides which agent to activate next based on the current state of the blackboard.

This pattern originated in the 1980s for speech recognition (the Hearsay-II system) and has been applied to many multi-agent problems since. It works well when agents have overlapping concerns and need to build on each other's partial results.

**Strengths:**
- Natural for problems where agents build incrementally on shared state
- Any agent can see any other agent's contributions
- The control component can prioritize dynamically

**Weaknesses:**
- Concurrency is hard — multiple agents writing simultaneously can corrupt state
- No clear ownership of data — debugging "who wrote this" is difficult
- The blackboard can become a bottleneck as the number of agents grows
- Requires careful locking or conflict resolution

**Relevance to plum-audit:** Low to moderate. Audit sections are largely independent — the security agent doesn't need to build on the quality agent's findings in real time. The cross-referencing that would benefit from shared state (e.g., "this file has both a security issue and no tests") can be done post-hoc by a coordinator rather than requiring live shared state.

#### 2.2 Message passing / mailboxes

Each agent has an inbox. Agents communicate by posting messages to each other's mailboxes. Messages can be requests, responses, notifications, or data payloads. This is the model used by actor systems (Erlang, Akka) and most microservice architectures.

**Strengths:**
- Clear ownership — each agent owns its inbox
- No shared mutable state — agents communicate through immutable messages
- Supports request/response patterns, fan-out, and fan-in
- Well-understood concurrency model

**Weaknesses:**
- Requires a message routing layer (even if simple)
- Message ordering and delivery guarantees add complexity
- Agents need to agree on message formats (schemas)
- Debugging message flows across many agents is non-trivial

**Relevance to plum-audit:** Low. The audit pattern is fan-out/fan-in (coordinator dispatches 6 agents, waits for all 6 results, synthesizes). There's no agent-to-agent messaging during execution. The "messages" are just final result payloads.

#### 2.3 Event streams / append-only logs

All agents write to a shared append-only log. Each entry is a structured event (JSON line, Kafka message, etc.). Agents can read the log from any point and process events they care about. This is the model used by Kafka, event sourcing, and many data pipeline architectures.

**Strengths:**
- Natural ordering (events have timestamps)
- No lost messages — the log is permanent
- Agents can "catch up" by replaying from a checkpoint
- Supports real-time processing and batch processing from the same source
- Append-only means no corruption from concurrent writes (if properly implemented)

**Weaknesses:**
- Log can grow large if not managed
- Querying the log for specific events requires scanning or indexing
- Agents reading the log in real time need a polling or notification mechanism
- Schema evolution is important — old events and new events need to coexist

**Relevance to plum-audit:** Moderate. An audit event log would support incremental reporting (show findings as they're discovered, not just at the end) and historical analysis (replay the log to see all findings across all audits). However, the complexity of managing a persistent event log is high relative to the current scale (6 agents, occasional runs).

#### 2.4 Shared filesystem with conventions

Agents communicate through files in agreed-upon locations with agreed-upon formats. No message bus, no server, no dependencies. Just files and naming conventions.

**Strengths:**
- Zero infrastructure — works anywhere with a filesystem
- Easy to inspect and debug (just read the files)
- Natural fit for Claude Code (agents already read/write files)
- Files persist automatically — no separate storage layer needed
- Tooling ecosystem is mature (jq, diff, grep work on JSON files)

**Weaknesses:**
- No notification mechanism — the coordinator must poll or wait
- Concurrent writes to the same file can corrupt it
- No built-in ordering or sequencing
- Cleanup is manual (stale files accumulate)

**Relevance to plum-audit:** High. This is the most natural fit. Audit agents already produce output that could be files. The coordinator already runs after all agents complete. The filesystem is the simplest "message bus" available, and Claude Code agents are built around file I/O.

#### 2.5 Tool-mediated communication

Agents don't communicate directly — they interact through a shared tool or service (like an MCP server). The tool handles serialization, conflict resolution, access control, and persistence. Agents call tool functions rather than reading/writing files.

**Strengths:**
- The tool can enforce schemas and validate data
- Conflict resolution is centralized
- Access control is possible (agent A can write but not read agent B's data)
- The tool can provide notifications, aggregation, and other services

**Weaknesses:**
- Requires building and maintaining the tool/service
- Adds a dependency — if the tool is down, agents can't communicate
- More complex than files for simple use cases
- Tool becomes a single point of failure

**Relevance to plum-audit:** Low for now. The audit use case doesn't need the sophistication of a dedicated communication service. Files with conventions are sufficient. If Plum grows to have many agent workflows beyond auditing, a shared service might become worthwhile, but that's premature today.

### Which pattern fits plum-audit?

The audit workflow is a classic **fan-out/fan-in** pattern:

1. Coordinator dispatches N agents (fan-out)
2. Each agent works independently, produces results
3. Coordinator collects all results, synthesizes (fan-in)
4. Coordinator produces final output

There is no agent-to-agent communication during execution. Agents don't need to see each other's intermediate state. The only communication is: coordinator → agent (here's your task), agent → coordinator (here are my findings).

This makes **shared filesystem with conventions** (pattern 2.4) the natural choice. It's the simplest pattern that satisfies the requirements, adds no infrastructure dependencies, and fits naturally into how Claude Code agents work.

The more interesting design questions are:
- What goes in the files (schema design)
- How the coordinator processes them (coordinator logic)
- What happens after the report (auto-fix pipeline)

---

## 3. Schema Design

The schema is the contract between agents and coordinator. It defines what information agents must provide, what's optional, and how findings are structured. Getting the schema right determines whether the coordinator can do useful work with the data.

### 3.1 Design principles

#### Separate facts from opinions

A finding has two components: what was observed (fact) and how it's assessed (opinion). These should live in separate fields.

**Fact:** "Line 42 of `scripts/deploy/push.sh` contains `curl http://api.example.com/status`"
**Opinion:** "This is a security risk because it uses unencrypted HTTP"

Separating them lets the coordinator weight assessments differently. A security agent's severity rating carries more weight for security findings than a quality agent's. It also lets humans disagree with the assessment while preserving the observation.

#### Capture confidence

Not all findings are equally certain. A regex scan for secrets will have false positives (a variable named `api_key_format` isn't a leaked key). An agent that actually found `AKIA` followed by 20 alphanumeric characters in a tracked file is nearly certain.

If you don't capture confidence, the coordinator treats a "maybe this is a hardcoded key" the same as "this is definitely a hardcoded key." This either buries real issues in noise or creates alert fatigue.

Three levels are enough for audit purposes:
- **certain** — the agent verified the finding with high reliability (e.g., file exists, permission confirmed, tool returned definitive output)
- **likely** — the evidence is strong but could have an alternative explanation (e.g., pattern match that looks like a secret but could be a variable name)
- **possible** — heuristic match that needs human verification (e.g., "this function is complex" based on line count)

#### Use hierarchical categories

Flat categories like `"security"` or `"quality"` run out fast. A finding that's about secret management and a finding about TLS are both "security" but are very different in nature and remediation.

A simple two-level hierarchy works: `domain/subdomain`. Examples:

```
security/secrets
security/transport
security/permissions
security/enforcement
quality/linting
quality/conventions
quality/complexity
quality/dead-code
docs/drift
docs/completeness
docs/accuracy
infra/docker
infra/hooks
infra/git
testing/coverage
testing/patterns
testing/naming
claude/skills
claude/hooks
claude/redundancy
```

This lets the coordinator group at whatever level makes sense. The summary table groups by domain (security, quality, etc.). The detailed findings can be organized by subdomain. Trend analysis can track specific subdomains over time ("are we getting better at testing/coverage?").

#### Include actionable suggestions

A finding that says "this is bad" is less useful than one that says what to do about it. Including a suggestion, estimated effort, and whether the fix can be automated transforms the audit from "here's what's wrong" to "here's what to do about it, in priority order."

```json
{
  "suggestion": "Replace http:// with https://",
  "effort": "trivial",
  "auto_fixable": true
}
```

Effort levels:
- **trivial** — a single-line change, no testing required (e.g., fix a URL, add a missing flag)
- **small** — a few lines, straightforward, might need a test update (e.g., add error handling, fix a linting issue)
- **medium** — requires understanding context, multiple files, or new tests (e.g., refactor a function, add missing test coverage)
- **large** — architectural change, significant new code, or cross-cutting concern (e.g., redesign a module, add a new enforcement layer)

The `auto_fixable` flag is important for the downstream pipeline. Only `trivial` and some `small` findings should be candidates for automated fix branches. Anything `medium` or `large` needs human design decisions.

#### Scope matters as much as findings

Knowing what an agent checked is as important as knowing what it found. If the security agent only scanned `scripts/deploy/`, the coordinator shouldn't report "no security issues in scripts/backup/." The absence of findings is only meaningful relative to the scope of the search.

The scope field also enables coverage analysis: "these directories were never checked by any agent" is a finding the coordinator can generate by comparing all agents' scopes against the full file tree.

### 3.2 The finding schema

Putting the principles together, here's the full schema for a single finding:

```json
{
  "id": "sec-001",
  "check": "plaintext-http",
  "observation": "HTTP URL used without TLS",
  "file": "scripts/deploy/push.sh",
  "line": 42,
  "evidence": "curl http://api.example.com/status",
  "assessment": {
    "severity": "high",
    "confidence": "certain",
    "category": "security/transport"
  },
  "suggestion": "Change to https://",
  "effort": "trivial",
  "auto_fixable": true,
  "related_to": [],
  "context": "This endpoint is called during deployment to check service health before pushing changes."
}
```

Field descriptions:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Unique within the agent's result. Format: `{section-prefix}-{number}` (e.g., `sec-001`, `qual-003`). Used for cross-referencing. |
| `check` | yes | Which check produced this finding. Maps back to the check names in the skill definition (e.g., `hardcoded-secrets-scan`, `shellcheck`, `template-adherence`). |
| `observation` | yes | What was observed, stated as fact. No assessment language ("bad", "risk", "should"). |
| `file` | no | File path relative to project root. Absent for findings that aren't file-specific (e.g., "Docker build failed"). |
| `line` | no | Line number. Absent when the finding is about a whole file or non-file entity. |
| `evidence` | no | The raw evidence — the actual line of code, command output, or data that supports the observation. Included so the coordinator (and human reader) can verify without re-running the check. |
| `assessment.severity` | yes | One of: `critical`, `high`, `medium`, `low`. Maps to the existing plum-audit severity levels: critical → P0, high/medium → P2, low → P3. |
| `assessment.confidence` | yes | One of: `certain`, `likely`, `possible`. |
| `assessment.category` | yes | Hierarchical category string: `domain/subdomain`. |
| `suggestion` | no | What to do about it. Absent when the fix isn't obvious or requires human judgment. |
| `effort` | no | One of: `trivial`, `small`, `medium`, `large`. Present only when a suggestion is provided. |
| `auto_fixable` | no | Boolean. Whether an agent could reasonably apply the fix automatically. Defaults to false if absent. |
| `related_to` | no | Array of finding IDs from the same or other agents. Used for cross-referencing (e.g., "this finding relates to `test-007`"). Agents within the same run can reference their own findings; cross-agent references are added by the coordinator post-hoc. |
| `context` | no | Free-text explanation of why this matters or what surrounding context is relevant. The escape hatch for information that doesn't fit other fields. |

### 3.3 The result envelope

Each agent writes one result file containing all its findings wrapped in an envelope:

```json
{
  "protocol_version": 1,
  "agent_id": "plum-audit-security",
  "section": "security",
  "scope": {
    "checks_run": [
      "hardcoded-secrets-scan",
      "env-gitignored",
      "enforcement-layers",
      "plaintext-http",
      "gitignore-patterns",
      "file-permissions"
    ],
    "checks_skipped": [],
    "files_checked": 23,
    "directories": ["scripts/deploy/", "scripts/backup/", "scripts/monitor/", "scripts/common/"],
    "exclusions": [".git/", "node_modules/", ".venv/", "bak/", "tmp/"]
  },
  "timing": {
    "started_at": "2026-03-01T10:00:00Z",
    "completed_at": "2026-03-01T10:02:30Z",
    "duration_seconds": 150
  },
  "status": "completed",
  "findings": [],
  "summary": {
    "total": 5,
    "by_severity": { "critical": 1, "high": 1, "medium": 2, "low": 1 },
    "by_confidence": { "certain": 3, "likely": 1, "possible": 1 },
    "auto_fixable_count": 2
  },
  "notes": "The deploy scripts have no consistent error handling pattern. This is an architectural concern that doesn't map to individual findings."
}
```

Key design decisions in the envelope:

**`checks_skipped`** — If a check couldn't run (e.g., Docker not available for the build check, ruff not installed for Python linting), it goes here with a reason. This is how the coordinator distinguishes "no findings" from "check didn't run." Example:

```json
"checks_skipped": [
  { "check": "docker-build", "reason": "Docker daemon not running" }
]
```

**`summary`** — Pre-aggregated counts. The coordinator could recompute these from the findings array, but including them in the envelope saves work and provides a quick sanity check (if `summary.total` doesn't match `findings.length`, something went wrong).

**`notes`** — Free-text observations that don't fit the structured findings schema. Some audit observations are inherently fuzzy ("the overall architecture feels brittle," "there's a pattern of missing error handling across multiple scripts"). These are valuable but can't be reduced to a file/line/severity tuple. The notes field preserves them without forcing them into a structure they don't fit.

**`status`** — One of: `started`, `completed`, `failed`, `partial`. An agent writes `started` at the beginning and updates to `completed` when done. If the agent crashes, the status remains `started`, and the coordinator knows it didn't finish. `partial` means some checks completed but others failed — the findings array contains what was collected, and `checks_skipped` explains what didn't run.

**`protocol_version`** — Enables schema evolution. If the finding schema changes (new fields, renamed fields, different severity levels), old results with `protocol_version: 1` can still be parsed by a coordinator that understands version 2. This is a boring field that saves significant pain later. Without it, changing the schema requires migrating all historical data or breaking backward compatibility.

### 3.4 File layout

```
docs/audits/.staging/
├── security.json
├── quality.json
├── docs.json
├── infra.json
├── claude.json
└── testing.json
```

Each agent writes exactly one file. File names match section names. The staging directory is created before dispatch and cleaned up after the coordinator finishes (or preserved with a flag for debugging).

Alternative layouts considered:

**Single file (JSONL):** All agents append to one file, one JSON object per line. Simpler file management but risks corruption from concurrent writes. Also makes selective re-runs harder — you'd need to filter out old entries for the re-run section.

**Nested directories:** `docs/audits/.staging/security/results.json`, `docs/audits/.staging/security/metadata.json`, etc. More organized for complex agents but overkill for the current use case where each agent produces a single result.

**Timestamped files:** `docs/audits/.staging/security-2026-03-01T10-00-00.json`. Supports keeping multiple results per section (e.g., from re-runs) but adds complexity to the coordinator's file discovery logic.

The flat one-file-per-section layout is the simplest option that works. It can be extended later if needed.

### 3.5 Schema constraints and validation

The coordinator should validate each result file before processing. Minimum validation:

1. `protocol_version` is present and supported
2. `section` is one of the 6 known sections
3. `status` is present
4. If `status` is `completed`, `findings` is a non-null array
5. Each finding has at minimum: `id`, `check`, `observation`, `assessment.severity`, `assessment.category`
6. `id` values are unique within the file
7. `summary.total` matches `findings.length`

Validation failures don't crash the coordinator — they produce a meta-finding in the report ("security section result file was malformed: missing severity on finding sec-003"). The coordinator processes what it can and reports what it can't.

---

## 4. Coordinator Architecture

The coordinator is the brain of the system. It reads all agent results, validates them, deduplicates, cross-references, and produces outputs. It runs after all agents have completed (or timed out).

### 4.1 Execution phases

The coordinator runs through five phases sequentially:

#### Phase 1: Collection and validation

```
for each expected section:
    if result file missing:
        record "section did not report"
    elif file is malformed JSON:
        record "section produced invalid output"
    elif status == "started":
        record "section agent did not complete (likely crashed)"
    elif status == "failed":
        record "section failed: {error message}"
    elif status == "partial":
        process available findings
        record skipped checks
    elif status == "completed":
        validate schema
        process all findings
```

The distinction between "missing file" and "status: started" matters. A missing file means the agent was never dispatched (coordinator bug or configuration error). A `started` status means the agent was dispatched but didn't finish (crash, timeout, or context window exhaustion).

The coordinator maintains a list of all sections and their status. This list itself becomes part of the report: "6 sections dispatched, 5 completed, 1 timed out."

#### Phase 2: Deduplication

Two agents can flag the same issue from different perspectives:
- Security agent: "hardcoded URL on line 42 uses HTTP" → `security/transport`
- Quality agent: "magic string on line 42" → `quality/conventions`

These are the same underlying problem viewed through different lenses. The coordinator should merge them rather than reporting them twice.

**Dedup strategy:** Two findings are potential duplicates if they share the same file AND their line numbers are within ±3 lines of each other. When duplicates are detected:

1. Create a merged finding that preserves both assessments
2. Use the highest severity as the primary severity
3. Use the highest confidence as the primary confidence
4. Keep both suggestions (they may be different)
5. Note which agents contributed to the finding

```json
{
  "id": "merged-001",
  "type": "merged",
  "observation": "HTTP URL used without TLS (also flagged as magic string)",
  "file": "scripts/deploy/push.sh",
  "line": 42,
  "assessments": [
    {
      "agent": "plum-audit-security",
      "original_id": "sec-004",
      "severity": "high",
      "confidence": "certain",
      "category": "security/transport"
    },
    {
      "agent": "plum-audit-quality",
      "original_id": "qual-007",
      "severity": "low",
      "confidence": "certain",
      "category": "quality/conventions"
    }
  ],
  "primary_severity": "high",
  "suggestion": "Replace http:// with https:// and extract URL to a constant or config",
  "effort": "small",
  "auto_fixable": true
}
```

A finding flagged by multiple agents is generally more important than one flagged by a single agent, because it indicates the problem crosses domain boundaries. The coordinator can surface this: "Found by 2 agents (security, quality)."

**Edge cases in dedup:**
- Same file, different lines, same category → not duplicates (two separate issues in the same file)
- Same file, same line, same agent → this shouldn't happen if agents produce unique IDs, but if it does, it's a schema violation to report
- Different files, similar observation → not duplicates (e.g., HTTP URLs in two different scripts are separate findings)

#### Phase 3: Cross-referencing

This is where the coordinator creates value beyond simple aggregation. It looks for patterns across agents' findings that no individual agent could see.

**Compound findings:** Combinations that are worse than the sum of their parts.

| Finding A | Finding B | Compound risk |
|-----------|-----------|---------------|
| Security: no input validation | Testing: no tests | High-risk untested code with no input validation |
| Quality: cyclomatic complexity > 10 | Testing: no tests | Complex untested code |
| Security: hardcoded secret | Infra: pre-commit hook missing | Secret leak without enforcement |
| Docs: design.md out of date | Quality: dead code detected | Potentially abandoned code area |

The coordinator creates synthetic "compound" findings:

```json
{
  "id": "compound-001",
  "type": "compound",
  "observation": "scripts/deploy/push.sh is complex (complexity 15), has no tests, and contains unvalidated input",
  "severity": "critical",
  "composed_of": ["sec-003", "test-007", "qual-012"],
  "context": "Three independent agents flagged overlapping concerns in this file. The combination of complexity, missing tests, and missing validation creates a high-risk area."
}
```

**Coverage gap analysis:** The coordinator compares all agents' scopes against the full project file tree to identify blind spots.

```
Files checked by at least one agent: 42
Total tracked files: 58
Unchecked files: 16
  - docker/Dockerfile (not in any agent's scope)
  - docker/docker-compose.local.yml
  - .claude/hooks/block-env.sh (checked by claude section but not by security)
  - ...
```

This is a coordinator-generated meta-finding, not something any individual agent produces.

**Cluster analysis:** Group findings by file to identify hotspots.

```
scripts/deploy/push.sh: 4 findings (1 critical, 2 high, 1 medium)
scripts/backup/backup-issues.sh: 3 findings (0 critical, 1 high, 2 medium)
scripts/common/logging.sh: 0 findings
```

Files with many findings across multiple categories are likely areas that need broader attention, not just point fixes.

#### Phase 4: Trend comparison

If previous audit results exist (as JSON), the coordinator can diff against the most recent one.

```
# Find the most recent previous audit result
previous=$(ls -t docs/audits/.archive/*.json | head -1)
```

The diff produces three lists:

**New findings:** Present in this audit but not the previous one. Matching is done by file + line + category (not by ID, since IDs are generated fresh each run).

**Resolved findings:** Present in the previous audit but not this one. These are issues that were fixed since the last audit. Reporting them provides positive feedback — the team is making progress.

**Persistent findings:** Present in both audits. These are especially important to surface because they represent known issues that nobody has fixed. The coordinator can track how many consecutive audits a finding has appeared in:

```
PERSISTENT (3 consecutive audits):
  ! No tests for scripts/deploy/push.sh [testing/coverage]
  ! Missing set -euo pipefail in scripts/backup/backup-issues.sh [quality/conventions]

PERSISTENT (2 consecutive audits):
  ! Pre-push hook not installed [security/enforcement]
```

**Implementation note:** For trend comparison to work, the coordinator must archive the current run's structured data (not just the markdown report). A reasonable approach:

```
docs/audits/
├── .archive/
│   ├── 2026-02-15.json    # merged results from Feb 15 audit
│   └── 2026-03-01.json    # merged results from today (written by coordinator after synthesis)
├── .staging/              # temporary, cleaned up after run
│   ├── security.json
│   └── ...
├── 2026-02-15-audit.md    # human-readable report
└── 2026-03-01-audit.md    # today's human-readable report
```

The `.archive/` directory contains the merged, coordinator-processed results (after dedup, cross-referencing, etc.) as a single JSON file per audit run. This is the source of truth for trend comparison.

#### Phase 5: Report generation

The coordinator produces the final markdown report from the processed, structured data. The report structure matches what plum-audit produces today, but with additional sections.

**Executive summary** (3 lines, for quick scanning):

```markdown
Audit found 14 issues: 1 critical, 4 high, 6 medium, 3 low.
2 findings are new since last audit. 1 critical finding is persistent (3rd consecutive audit).
4 findings are auto-fixable.
```

**Summary table** (same format as today's plum-audit):

```markdown
| Section   | Critical | High | Medium | Low | Auto-fixable |
|-----------|----------|------|--------|-----|-------------|
| security  |        0 |    2 |      1 |   0 |           1 |
| quality   |        0 |    1 |      3 |   2 |           2 |
| docs      |        0 |    0 |      1 |   1 |           0 |
| infra     |        1 |    0 |      0 |   0 |           0 |
| claude    |        0 |    1 |      1 |   0 |           1 |
| testing   |        0 |    0 |      2 |   0 |           0 |
| **Total** |    **1** |**4** |  **8** |**3**|       **4** |
```

**Compound findings** (new section, not in current plum-audit):

```markdown
## Compound Findings

### [CRITICAL] scripts/deploy/push.sh — complex, untested, unvalidated
Found by: security, quality, testing
This file was independently flagged by 3 agents for overlapping concerns...
```

**Section details** (same as today):

```markdown
## Security

- [HIGH] `scripts/deploy/push.sh:42` — HTTP URL used without TLS
  Evidence: `curl http://api.example.com/status`
  Suggestion: Change to https://
  Confidence: certain | Effort: trivial | Auto-fixable: yes

- [MEDIUM] Missing `*.pem` pattern in .gitignore
  ...
```

**Trend analysis** (new section):

```markdown
## Changes Since Last Audit (2026-02-15)

### New findings (2)
- [HIGH] Hardcoded URL without TLS in push.sh:42
- [MEDIUM] Ruff warning in validate-secrets.py

### Resolved (1)
- ~~[WARNING] Missing set -e in backup-issues.sh~~ ✓ Fixed

### Persistent (3 audits)
- [MEDIUM] No tests for scripts/deploy/push.sh
```

**Coverage gaps** (new section):

```markdown
## Coverage

Agents that did not complete:
- infra: timed out after 120s (partial results included)

Directories not in any agent's scope:
- docker/ (only checked during Docker build, not scanned for code issues)
```

**Recommendations** (same as today, with `gh issue create` commands):

```markdown
## Recommendations

### 1. [CRITICAL] Docker build failing
gh issue create --title "AUDIT: Docker build failing" ...

### 2. [HIGH] HTTP URL without TLS in push.sh
gh issue create --title "AUDIT: HTTP URL without TLS in push.sh:42" ...
```

### 4.2 Coordinator implementation considerations

**Where does the coordinator run?** The coordinator is the parent agent in the plum-audit skill. After dispatching 6 section agents and collecting their JSON results, the parent agent itself runs the coordinator logic. This means the coordinator is a prompt within the skill, not a separate script.

Alternatively, the coordinator could be a Python script that processes JSON files and outputs markdown. This would be more deterministic (no LLM involved in aggregation) but less flexible (can't generate natural-language insights about compound findings). A hybrid approach is possible: Python script for deterministic steps (validation, dedup, counting, trend diff), LLM for interpretive steps (compound finding narratives, coverage gap analysis, recommendations).

**Timeout handling:** If an agent hasn't produced a result file after N seconds, the coordinator should proceed without it. The timeout is section-dependent — the infra section (Docker build) may legitimately take 5 minutes, while the security section (grep scans) should finish in 30 seconds.

**Idempotency:** Running the coordinator multiple times on the same staging directory should produce the same report. This means the coordinator shouldn't modify the staging files — it reads them and writes to a separate output location.

---

## 5. Auto-Fix Pipeline

This is the most sensitive part of the design. Automated fixes to code require careful guardrails. The user's constraint is clear: **every fix must be approved before it lands.** The pipeline must enforce this structurally, not just by convention.

### 5.1 Approval model

The auto-fix pipeline is a **two-gate** process. Nothing is created — no issues, no branches, no PRs — without explicit user approval at each gate.

**Gate 1: Approval to create issues.** After the coordinator finishes the report, it presents the user with a summary of all findings that qualify for issue creation (CRITICAL and WARNING findings, same as today's `gh issue create` recommendations). The user reviews the list and approves which findings should become GitHub Issues. Only approved findings get issues created.

**Gate 2: Approval to create fix branches.** For findings that are both approved as issues AND marked `auto_fixable: true`, the coordinator presents a second list: "These N findings have automated fixes available. Create fix branches?" The user approves which (if any) should get branches and draft PRs.

```
coordinator finishes report
  → presents list of issue-worthy findings
  → USER APPROVES which findings become issues
  → issues created for approved findings only
  → presents list of auto-fixable findings (subset of approved issues)
  → USER APPROVES which findings get fix branches
  → fix agents create branches + draft PRs for approved findings only
  → user reviews each draft PR and merges or closes
```

No issues, branches, or PRs are created without the user explicitly approving them. The `gh issue create` commands in the recommendations section remain as copy-pasteable commands (same as today) for findings the user wants to handle manually.

### 5.2 What qualifies for auto-fix

Not every finding should get an automated fix branch. The criteria:

1. **`auto_fixable: true`** — the agent explicitly marked it
2. **`effort: trivial` or `effort: small`** — only simple, mechanical fixes
3. **`confidence: certain`** — no fixes based on uncertain findings
4. **The suggestion is specific enough to implement** — "Replace http:// with https://" is specific; "improve error handling" is not

The coordinator filters findings through these criteria before presenting them to the user at Gate 2. A finding that passes all criteria is shown as a candidate for auto-fix. A finding that fails any criterion is not offered for auto-fix (it may still get a manually-created issue via Gate 1). The user makes the final decision on which candidates actually get fix branches.

### 5.3 Fix agent workflow

For each auto-fixable finding, a fix agent runs in an **isolated worktree** (using Claude Code's worktree isolation). This ensures:

- Fixes don't interfere with each other
- Fixes don't modify the working tree the user is currently in
- Each fix is on its own branch, reviewable independently
- If a fix agent crashes or produces bad output, nothing is corrupted

The fix agent receives the finding's structured data (only after user approval at Gate 2) and performs:

1. Read the file at the specified path and line
2. Apply the suggested fix
3. Run relevant checks (shellcheck for .sh files, ruff for .py files)
4. If checks pass, commit the change
5. Push the branch
6. Create a draft PR linking to the audit issue

If the fix agent can't apply the fix cleanly (file changed, suggestion doesn't apply, checks fail after fix), it abandons the branch and adds a comment to the issue: "Automated fix attempted but failed: {reason}. Manual fix required."

### 5.4 Issue format

Each auto-fix issue follows a consistent template:

```markdown
## Audit Finding: {observation}

**Section:** {section}
**Severity:** {severity}
**Category:** {category}
**Found:** {audit date}
**File:** {file}:{line}

### Evidence

\`\`\`
{evidence}
\`\`\`

### Suggested Fix

{suggestion}

**Effort:** {effort}
**Confidence:** {confidence}

### Auto-Fix

{if branch exists:}
A fix has been proposed in branch `fix/audit-{id}` — see draft PR #{pr_number}.
Review the diff before merging.

{if fix failed:}
Automated fix was attempted but failed: {reason}.
Manual fix required.

{if not auto-fixable:}
This finding requires manual review and fix.

---
*Found by plum-audit on {date}. Finding ID: {id}.*
```

Labels applied:
- Severity label: `P0-critical`, `P2-normal`, or `P3-low`
- Section label: `security`, `quality`, `docs`, `infra`, `claude`, `testing`
- `audit` label (for filtering)
- `auto-fix` label (if a fix branch was created)

### 5.5 Batch behavior

An audit might produce 10+ auto-fixable findings. Creating 10 PRs simultaneously is noisy. Options:

**One PR per finding (current design).** Each finding gets its own branch and PR. Clean isolation, easy to review individually, but can flood the PR list.

**Batched PR.** Group auto-fixable findings by file or section into a single branch/PR. Reduces noise but makes individual findings harder to approve/reject independently. If you want to accept fix A but reject fix B, you need to cherry-pick.

**Staged rollout.** Create issues for all findings but only create fix branches for the top 3-5 by severity. After those are reviewed and merged, create branches for the next batch. Prevents overwhelming the reviewer.

The one-per-finding approach is the safest default for a project where the user must approve everything. Batching can be added later as an optimization if the volume of findings becomes unmanageable.

### 5.6 Safety constraints

Hard rules for the auto-fix pipeline:

1. **User approves all issue creation.** No GitHub Issues are created without explicit user approval (Gate 1). The coordinator presents candidates; the user selects which ones to create.
2. **User approves all fix branches.** No branches or PRs are created without explicit user approval (Gate 2). The coordinator presents auto-fixable candidates; the user selects which ones to attempt.
3. **Never push to master.** All fix branches are created from master but never merged automatically.
4. **Never force-push.** If a branch already exists (from a previous audit), fail and report the conflict rather than overwriting.
5. **Draft PRs only.** PRs are created in draft state. The user explicitly marks them ready and merges.
6. **No cascading fixes.** A fix agent works on exactly one finding. It doesn't "while I'm here, let me also fix this other thing."
7. **Checks must pass.** If the fix introduces a shellcheck or ruff error, the fix is abandoned, not committed.
8. **Existing worktree conventions.** Fix agents use the same worktree pattern as `/plum-todo-pop` and `/plum-churn` — isolated worktrees in `.claude/worktrees/`.

---

## 6. Implementation Approaches

Three approaches for implementing the structured protocol, ranging from minimal change to full rebuild.

### 6.1 Approach A: JSON Sidecar

**Description:** Each section agent writes a structured JSON file to a staging directory. The coordinator reads all JSON files, runs the five phases (collect, dedup, cross-ref, trend, report), and generates the markdown report plus archived JSON.

**What changes from today:**
- Each section in the skill becomes a prompt for a dispatched subagent
- Agents write JSON instead of contributing to a shared markdown string
- A new coordinator section in the skill processes the JSON and generates output
- The auto-fix pipeline is a separate post-coordinator step

**File flow:**
```
dispatch 6 agents in parallel
  → each writes to docs/audits/.staging/{section}.json
  → coordinator reads all 6 files
  → coordinator writes docs/audits/YYYY-MM-DD-audit.md (report)
  → coordinator writes docs/audits/.archive/YYYY-MM-DD.json (for trends)
  → coordinator routes auto-fixable findings to fix pipeline
  → fix pipeline creates issues + branches
  → staging directory cleaned up
```

**Pros:**
- Clean separation between agents and coordinator
- Agents are truly parallel — wall clock time = slowest agent
- JSON is diffable across runs
- Selective re-runs: re-run one section, coordinator merges with cached others
- Auto-fix pipeline has structured data to work with
- The coordinator can do sophisticated analysis (dedup, compound findings, trends)

**Cons:**
- More moving parts than today
- Need to define, validate, and maintain a schema
- The coordinator prompt is complex (five phases of logic)
- Staging directory needs creation and cleanup
- Debugging requires understanding the JSON intermediate format, not just reading the report

**Estimated complexity:** Medium-high. The skill file grows significantly (coordinator logic), and each section's prompt needs rewriting to output JSON instead of prose. Testing requires running the full pipeline end-to-end.

### 6.2 Approach B: JSONL Append Log

**Description:** All agents append findings to a single shared JSONL file (one JSON object per line). Each line is a self-contained finding or status event. The coordinator reads the file sequentially at the end.

**What changes from today:**
- Same as Approach A, except agents write to a shared file instead of individual files
- The coordinator reads one file instead of six
- Findings are interleaved by agent execution order

**File flow:**
```
dispatch 6 agents in parallel
  → each appends to docs/audits/.staging/YYYY-MM-DD.jsonl
  → coordinator reads the single file
  → same processing as Approach A
```

**JSONL format:**
```
{"type": "status", "section": "security", "status": "started", "timestamp": "..."}
{"type": "finding", "section": "security", "id": "sec-001", ...}
{"type": "finding", "section": "quality", "id": "qual-001", ...}
{"type": "finding", "section": "security", "id": "sec-002", ...}
{"type": "status", "section": "security", "status": "completed", "summary": {...}}
{"type": "status", "section": "quality", "status": "completed", "summary": {...}}
```

**Pros:**
- Single file to manage (simpler cleanup)
- Supports incremental progress — coordinator can read partial results before all agents finish
- Natural chronological ordering shows which agents are fastest
- JSONL is easy to process with `jq` and standard Unix tools

**Cons:**
- **Concurrent write risk.** Multiple agents appending to the same file simultaneously can produce corrupted lines (partial writes, interleaved bytes). This is the critical flaw. File-level locking is possible but adds complexity and may not work reliably across all environments.
- Harder to re-run one section (need to filter out old entries for that section)
- No clear file-level ownership — harder to debug "which agent wrote this malformed line"
- The interleaved format is harder to read than per-section files
- Selective re-runs require either appending new results (duplicating the section) or rewriting the file (defeating the append-only property)

**Estimated complexity:** Medium. Simpler file management than Approach A, but the concurrent write problem is a real engineering challenge. In practice, you'd likely need a locking mechanism or a sequencer, which erases the simplicity advantage.

### 6.3 Approach C: Structured Markdown (Minimal Change)

**Description:** Keep the current serial, prose-based approach but add machine-readable metadata to the report. Each section's findings include YAML frontmatter or HTML comments with structured data. The coordinator (or a post-processing script) can extract this metadata for trending and auto-fix routing.

**What changes from today:**
- Each finding in the markdown report includes a hidden structured data block
- A post-processing step extracts structured data from the markdown for archiving and auto-fix
- No change to the execution model (still serial, still one agent)

**Format:**
```markdown
## Security

<!-- audit-finding: {"id": "sec-001", "severity": "high", "category": "security/transport", "file": "scripts/deploy/push.sh", "line": 42, "auto_fixable": true} -->
### [HIGH] HTTP URL used without TLS
- **File:** `scripts/deploy/push.sh:42`
- **Evidence:** `curl http://api.example.com/status`
- **Suggestion:** Change to https://
```

Or with YAML frontmatter per section:

```markdown
## Security

---
findings:
  - id: sec-001
    severity: high
    category: security/transport
    file: scripts/deploy/push.sh
    line: 42
    auto_fixable: true
---

### [HIGH] HTTP URL used without TLS
...
```

**Pros:**
- Smallest change from today — the report looks identical to what plum-audit already produces
- No new files, no staging directory, no cleanup
- Reports are human-readable without tooling
- Easy migration path — add structured data incrementally, one section at a time
- Doesn't require parallelism — works with the current serial execution

**Cons:**
- Parsing structured data from markdown is fragile (HTML comments can be stripped, YAML-in-markdown is non-standard)
- Limited cross-referencing ability — the coordinator still runs serially and can't easily build compound findings
- No parallelism gain — this approach doesn't change the execution model
- Deduplication is harder when findings are embedded in prose rather than in a clean data structure
- The structured data and prose can drift apart — someone edits the prose but forgets to update the metadata
- You get some structure but not enough to build a reliable auto-fix pipeline on

**Estimated complexity:** Low. This is an incremental enhancement, not a redesign. However, the value is also incremental — you get basic trending and auto-fix routing, but not the full benefits of parallel execution, proper deduplication, or compound finding analysis.

### 6.4 Comparison matrix

| Dimension | A: JSON Sidecar | B: JSONL Log | C: Structured Markdown |
|-----------|----------------|-------------|----------------------|
| Parallel execution | Yes (6 agents) | Yes (6 agents) | No (serial) |
| Concurrent write safety | Yes (separate files) | Risky (shared file) | N/A (serial) |
| Selective re-runs | Yes (replace one file) | Difficult | No |
| Cross-referencing | Full (coordinator phase) | Full (coordinator phase) | Limited |
| Trend comparison | Full (archived JSON) | Full (archived JSONL) | Partial (parse markdown) |
| Auto-fix pipeline input | Clean structured data | Clean structured data | Fragile embedded metadata |
| Human readability of intermediate format | JSON files (needs jq) | JSONL file (needs jq) | Markdown (readable as-is) |
| Implementation effort | Medium-high | Medium | Low |
| Migration from current | Full rewrite of skill | Full rewrite of skill | Incremental enhancement |
| Debugging ease | Read individual JSON files | Search through interleaved log | Read the report |
| Infrastructure requirements | None (files) | None (files, but needs locking) | None |
| Risk of data corruption | Low | Medium (concurrent writes) | Low |

### 6.5 Recommendation

**Approach A (JSON Sidecar)** is the strongest choice for the full vision: parallel agents, structured data, dedup, cross-referencing, trends, and auto-fix pipeline. The upfront cost is highest, but it's the only approach that supports all the goals.

**Approach C (Structured Markdown)** is a reasonable stepping stone if the full redesign feels too large for one effort. It adds basic machine-readable data to the current report format, enabling simple trending and auto-fix routing without changing the execution model. However, it doesn't address parallelism or cross-referencing, and the embedded-metadata approach has fragility risks.

**Approach B (JSONL Log)** sits in an awkward middle — it has the same complexity as Approach A (parallel agents, coordinator logic) but adds a concurrent write risk that Approach A avoids entirely. There's no scenario where B is clearly better than A.

A reasonable migration path: start with C to get basic trending, then move to A when parallel execution and cross-referencing become priorities. Each step is independently valuable.

---

## 7. Failure Modes and Edge Cases

### 7.1 Agent failures

**Agent crashes mid-execution.** The agent writes `status: started` at the beginning and `status: completed` at the end. If the result file shows `started`, the coordinator knows the agent didn't finish. It reports the section as incomplete and includes whatever partial findings exist (if the agent managed to write any before crashing).

**Agent produces no findings.** This is a legitimate outcome (e.g., the security section finds no issues). The coordinator must distinguish "zero findings because everything is clean" from "zero findings because the agent didn't run." The `checks_run` field in the scope provides this: if the agent reports 6 checks run and 0 findings, the section is clean. If the agent reports 0 checks run (or is missing), something went wrong.

**Agent exceeds context window.** For large projects, an agent might run out of context before finishing all checks. The skill prompt should instruct agents to write partial results if they're running low — better to report 4 of 6 checks than to crash and report 0.

**Agent writes malformed JSON.** The coordinator validates JSON before processing. Malformed files are reported as "section produced invalid output" in the report, with the raw file contents included for debugging.

### 7.2 Coordinator failures

**Coordinator runs out of context.** The coordinator needs to process up to 6 JSON files, perform dedup and cross-referencing, and generate a full report. For a large project with many findings, this could be substantial. Mitigation: the coordinator can process sections in batches, writing partial output as it goes.

**Dedup produces false positives.** The ±3 line heuristic might merge findings that happen to be near each other but are actually distinct. Risk is low for the current project size, but the coordinator should include both original findings in the merged result so the human can verify.

**Cross-referencing misidentifies compound findings.** The coordinator might create a compound finding that doesn't actually represent a compound risk (e.g., a file has a linting issue and no tests, but the linting issue is cosmetic and the file is test infrastructure). Compound findings should be labeled as "coordinator-generated" so the reader knows they're synthetic.

### 7.3 Auto-fix failures

**Fix agent can't apply the fix.** The file may have changed since the audit ran, the suggested fix may not apply cleanly, or the fix may introduce new issues. The fix agent abandons the branch and comments on the issue.

**Fix branch already exists.** If a previous audit created a fix branch for the same finding and it wasn't merged or deleted, the fix agent should not overwrite it. It reports "branch already exists for this finding — previous fix may still be pending review."

**Fix passes checks but is wrong.** The fix agent applies the suggested change and shellcheck/ruff pass, but the fix is semantically wrong (e.g., changing `http://` to `https://` but the target server doesn't support TLS). This is why the user must review every fix — automated checks catch syntax errors but not semantic errors.

**Too many auto-fix PRs.** An audit with 20 auto-fixable findings creates 20 draft PRs. This can overwhelm the reviewer. Mitigation options: cap the number of fix PRs per audit run, prioritize by severity, or batch findings into fewer PRs (with the trade-off of harder individual review).

### 7.4 Trend comparison edge cases

**First audit run.** No previous archive exists. The coordinator skips the trend comparison section and notes "No previous audit data available for trend comparison."

**Schema version mismatch.** The current audit uses `protocol_version: 2` but the archived previous audit uses `protocol_version: 1`. The coordinator should attempt best-effort comparison using fields that exist in both versions, and note any fields that couldn't be compared.

**Finding moved but not fixed.** A finding at `deploy.sh:42` in the previous audit appears at `deploy.sh:45` in the current audit (because lines were added above it). The finding isn't resolved — it moved. Matching by file + line will misidentify this as "old finding resolved, new finding appeared." Matching by file + category + observation text is more robust but less precise.

**File renamed.** A finding in `old-name.sh` was "resolved" because the file is now `new-name.sh`. The coordinator can't detect this automatically. Git rename detection (`git log --follow`) could help but adds complexity.

---

## 8. Honest Assessment

### What this adds

- **Parallelism:** Wall clock time drops from sum-of-all-sections to max-of-all-sections. For an audit that currently takes 5+ minutes (especially with Docker builds), this could cut it to 2-3 minutes.
- **Structured data:** Findings become machine-processable. This enables trending, auto-fix, and programmatic queries ("show me all critical findings across the last 5 audits").
- **Cross-referencing:** Compound findings surface risks that no individual agent can see.
- **Auto-fix pipeline:** Routine fixes (TLS URLs, missing flags, linting issues) get automated to the point of "review and merge," not "figure out what to do."

### What this costs

- **Complexity:** The current plum-audit skill is ~450 lines of straightforward prompt. The redesigned version would be significantly larger, with schema definitions, coordinator logic, and auto-fix pipeline.
- **Debugging difficulty:** When the current plum-audit produces a wrong finding, you read the skill and see the shell command. When the redesigned version produces a wrong finding, you need to trace through: which agent produced it, what JSON it wrote, how the coordinator processed it, whether dedup or cross-referencing modified it.
- **Maintenance burden:** The schema is a contract. Changing how a check works requires updating both the agent prompt and potentially the coordinator logic and any downstream consumers.
- **Over-engineering risk:** For a solo sysadmin project with ~30 scripts, the full vision (parallel agents, coordinator with 5 phases, auto-fix pipeline with worktrees and draft PRs) might be more machinery than the problem warrants. The question isn't whether the design is sound — it's whether the investment pays off at this scale.

### When it makes sense

The full redesign is worth it if:
- Audits are run frequently (weekly or more) and the time savings compound
- The project grows to a size where cross-referencing and trend analysis provide real signal
- Auto-fix saves meaningful time on routine issues
- The protocol is reused for other agent workflows beyond auditing

The minimal version (Approach C) is worth it if:
- You want basic trending without changing the execution model
- The auto-fix pipeline is the main value driver and doesn't need sophisticated structured data
- The project stays small and parallel execution doesn't provide meaningful speedup

---

## 9. Open Questions

These are decisions that would need to be made before implementation:

1. **Coordinator: LLM or script?** Should the coordinator be a Python script that deterministically processes JSON, an LLM prompt that reads JSON and generates the report, or a hybrid? The deterministic script is more reliable for aggregation and counting; the LLM is better at narrative and interpretation.

2. **How many auto-fix PRs per run?** Should there be a cap? If so, what's the prioritization: severity first, effort first (quick wins), or section-based?

3. **Archive retention.** How many previous audits should be kept in `.archive/`? All of them? Last 10? Time-based (last 90 days)?

4. **Single-section runs.** If you run `/plum-audit security`, should the coordinator still try to cross-reference with cached results from other sections (if they exist from a previous full run)? Or does a single-section run produce only section-specific output?

5. **Notification on persistent findings.** Should the coordinator escalate findings that persist across N audits? (e.g., promote a WARNING to CRITICAL if it's been unfixed for 5 consecutive audits, or create a summary issue "These 3 findings have been open for 2 months.")

6. **Fix branch naming.** `fix/audit-sec-004-http-tls` is descriptive but verbose. `fix/audit-001` is short but meaningless. What convention?
