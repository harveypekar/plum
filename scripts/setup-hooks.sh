#!/bin/bash
# Install git hooks from scripts/common/ into .git/hooks/
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

echo "Installing pre-commit hook..."
cat > "$HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
exec "$(git rev-parse --show-toplevel)/scripts/common/pre-commit"
EOF
chmod +x "$HOOKS_DIR/pre-commit"

echo "Installing pre-push hook..."
cat > "$HOOKS_DIR/pre-push" << 'EOF'
#!/bin/bash
exec "$(git rev-parse --show-toplevel)/scripts/common/pre-push"
EOF
chmod +x "$HOOKS_DIR/pre-push"

echo "Done. Hooks installed."
