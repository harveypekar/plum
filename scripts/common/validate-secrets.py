#!/usr/bin/env python3
"""
Pre-commit hook to prevent committing secret files (.env, keys, certs).

Does NOT scan file contents — secrets belong in .env (which is blocked here
and in .gitignore), so pattern-matching content just causes false positives.
"""

import re
import subprocess
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

FORBIDDEN_FILES = [
    (r'(^|/)\.env$', '.env file'),
    (r'(^|/)\.env\.(?!example$)', '.env variant'),
    (r'\.key$', 'private key'),
    (r'\.pem$', 'certificate/key'),
    (r'(^|/)secrets/', 'secrets directory'),
    (r'(^|/)credentials/', 'credentials directory'),
]


def main():
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only'],
        capture_output=True, text=True,
    )

    blocked = []
    for filepath in result.stdout.strip().split('\n'):
        if not filepath:
            continue
        for pattern, description in FORBIDDEN_FILES:
            if re.search(pattern, filepath):
                blocked.append((filepath, description))
                break

    if blocked:
        for filepath, description in blocked:
            print(f"  BLOCKED: {description} — {filepath}")
        print(f"\n  {len(blocked)} forbidden file(s). Move secrets to .env (never committed).")
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
