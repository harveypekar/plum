#!/usr/bin/env python3
"""
Pre-commit hook to prevent committing secrets, PII, or sensitive data.
Must pass before any commit is allowed.
"""

import re
import sys
import io
from pathlib import Path

# Force UTF-8 output on all platforms
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Patterns that indicate secrets/PII (common formats)
DANGEROUS_PATTERNS = [
    (r'api[_-]?key\s*=\s*["\']?[a-zA-Z0-9_\-]{20,}', 'API key'),
    (r'password\s*=\s*["\']?[a-zA-Z0-9_\-@.]{8,}', 'Password'),
    (r'token\s*=\s*["\']?[a-zA-Z0-9_\-]{20,}', 'Token'),
    (r'secret\s*=\s*["\']?[a-zA-Z0-9_\-]{20,}', 'Secret'),
    (r'bearer\s+[a-zA-Z0-9_\-]{20,}', 'Bearer token'),
    (r'[\w\.-]+@[\w\.-]+\.\w+', 'Email address (PII)'),
    (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN (PII)'),
    (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', 'Credit card (PII)'),
]

# Files that should NEVER be committed
FORBIDDEN_FILES = [
    r'\.env$',
    r'\.env\.',
    r'.*\.key$',
    r'.*\.pem$',
    r'secrets/.*',
    r'credentials/.*',
]

def check_file(filepath):
    """Check a file for dangerous content."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return True  # Skip binary files

    # Check forbidden filenames
    for pattern in FORBIDDEN_FILES:
        if re.search(pattern, filepath):
            print(f"❌ BLOCKED: Forbidden file pattern: {filepath}")
            return False

    # Check for dangerous patterns
    for pattern, description in DANGEROUS_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            print(f"❌ BLOCKED: {description} found in {filepath}")
            print(f"   Pattern: {pattern}")
            return False

    return True

def main():
    """Check all staged files."""
    import subprocess

    # Get staged files from git
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only'],
        capture_output=True,
        text=True
    )

    files = result.stdout.strip().split('\n')
    failed = False

    for filepath in files:
        if filepath and not check_file(filepath):
            failed = True

    if failed:
        print("\n⚠️  COMMIT BLOCKED: Dangerous content detected")
        print("This is a security protection. Do NOT bypass this check.")
        print("\nIf this is a false positive:")
        print("1. Review the detected pattern")
        print("2. Use generic placeholder names in code/docs")
        print("3. Put sensitive values only in .env (never committed)")
        sys.exit(1)
    else:
        print("✅ Security check passed")
        sys.exit(0)

if __name__ == '__main__':
    main()
