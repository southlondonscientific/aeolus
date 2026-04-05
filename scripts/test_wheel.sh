#!/usr/bin/env bash
# Build the aeolus wheel and run tests against the *installed* package
# (not the source tree). This catches missing package-data, broken imports,
# and anything else that only manifests in a real install.
#
# Usage:
#   ./scripts/test_wheel.sh              # run packaging tests only
#   ./scripts/test_wheel.sh --full       # run full test suite
#   ./scripts/test_wheel.sh -k test_sos  # pass arbitrary pytest args
#
# Requires: uv

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
VENV_DIR=$(mktemp -d)
trap 'rm -rf "$VENV_DIR"' EXIT

echo "==> Cleaning stale build artifacts..."
rm -rf "$REPO_ROOT/build" "$REPO_ROOT/dist"

echo "==> Building wheel..."
cd "$REPO_ROOT"
uv build --wheel --out-dir "$DIST_DIR" 2>&1 | tail -3

WHEEL=$(ls -t "$DIST_DIR"/aeolus_aq-*.whl | head -1)
echo "==> Built: $(basename "$WHEEL")"

echo "==> Creating isolated venv at $VENV_DIR..."
uv venv "$VENV_DIR" --python 3.11 --quiet

echo "==> Installing wheel + test dependencies..."
uv pip install --python "$VENV_DIR/bin/python" \
    "$WHEEL" \
    pytest responses freezegun pytest-mock tqdm \
    --quiet

echo "==> Listing installed package files..."
"$VENV_DIR/bin/python" -c "
from pathlib import Path
import aeolus
root = Path(aeolus.__file__).parent
print(f'Package root: {root}')
non_py = sorted(p.relative_to(root) for p in root.rglob('*') if p.is_file() and p.suffix != '.py' and '__pycache__' not in str(p) and p.suffix != '.pyc')
print(f'Non-Python data files ({len(non_py)}):')
for p in non_py:
    print(f'  {p}')
"

# Determine what to run
if [[ "${1:-}" == "--full" ]]; then
    shift
    echo "==> Running FULL test suite against installed wheel..."
    PYTEST_ARGS=("$REPO_ROOT/tests/" "$@")
else
    if [[ $# -eq 0 ]]; then
        echo "==> Running packaging tests against installed wheel..."
        PYTEST_ARGS=("$REPO_ROOT/tests/test_packaging.py" "-v")
    else
        echo "==> Running tests with custom args: $*"
        PYTEST_ARGS=("$REPO_ROOT/tests/" "$@")
    fi
fi

# Run pytest from a temp dir so Python can't accidentally import from src/
cd "$VENV_DIR"
"$VENV_DIR/bin/python" -m pytest "${PYTEST_ARGS[@]}" \
    --override-ini="addopts=" \
    --no-header \
    -v

echo "==> All tests passed against the installed wheel."
