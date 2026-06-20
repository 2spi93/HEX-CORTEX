#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-screen-lab-policy-v2}"
RUN_TESTS="${RUN_TESTS:-0}"
INSTALL_VISION="${INSTALL_VISION:-0}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v git >/dev/null 2>&1; then
  echo "git is not available on PATH" >&2
  exit 2
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean. Commit, discard, or manually stash changes before bootstrap." >&2
  exit 2
fi

git fetch origin
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git switch "$BRANCH"
else
  git switch --track -c "$BRANCH" "origin/$BRANCH"
fi
git pull --ff-only origin "$BRANCH"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi

PYTHON="$PROJECT_ROOT/.venv/bin/python"
"$PYTHON" -m pip install --upgrade pip
if [[ "$INSTALL_VISION" == "1" ]]; then
  "$PYTHON" -m pip install -e '.[dev,vision]'
else
  "$PYTHON" -m pip install -e '.[dev]'
fi

DOCTOR="$PROJECT_ROOT/.venv/bin/hexcortex-doctor"
if [[ ! -x "$DOCTOR" ]]; then
  echo "hexcortex-doctor was not generated; package metadata is not aligned" >&2
  exit 2
fi

"$DOCTOR" \
  --project-root . \
  --expected-branch "$BRANCH" \
  --collect-tests \
  --pretty

if [[ "$RUN_TESTS" == "1" ]]; then
  "$PYTHON" -m ruff check .
  "$PYTHON" -m pytest
fi

echo "HEX-CORTEX bootstrap complete on branch $BRANCH"
