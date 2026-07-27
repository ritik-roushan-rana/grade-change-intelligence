#!/usr/bin/env bash
# Publish the current commit to a Hugging Face Space (Docker SDK).
#
#   ./deploy/huggingface/deploy.sh <user-or-org>/<space-name>
#
# Why a script rather than a git remote: a Space is its own repository whose
# README front matter carries the runtime configuration (SDK, port). This
# exports the tracked files of HEAD, prepends that front matter to the README,
# and pushes the result as a single commit — leaving this repository untouched.
#
# Authentication: an HF access token with write scope. Either export HF_TOKEN,
# or let git prompt (username = your HF username, password = the token).

set -euo pipefail

SPACE_ID="${1:-}"
if [[ -z "$SPACE_ID" || "$SPACE_ID" != */* ]]; then
    echo "Usage: $0 <user-or-org>/<space-name>" >&2
    exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CARD="$REPO_ROOT/deploy/huggingface/space_card.md"
cd "$REPO_ROOT"

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Working tree is dirty. Commit or stash first — this pushes HEAD, not your edits." >&2
    exit 1
fi

COMMIT="$(git rev-parse --short HEAD)"
if [[ -n "${HF_TOKEN:-}" ]]; then
    REMOTE="https://user:${HF_TOKEN}@huggingface.co/spaces/${SPACE_ID}"
else
    REMOTE="https://huggingface.co/spaces/${SPACE_ID}"
fi

STAGE="$(mktemp -d)"
# The token can appear in the remote URL, so never leave the staging clone behind.
trap 'rm -rf "$STAGE"' EXIT

echo "Cloning Space $SPACE_ID ..."
git clone --depth 1 "$REMOTE" "$STAGE/space" 2>&1 | sed "s|${HF_TOKEN:-__none__}|***|g"

echo "Exporting tracked files from $COMMIT ..."
# Drop everything except .git so files deleted upstream disappear from the Space.
find "$STAGE/space" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
git archive HEAD | tar -x -C "$STAGE/space"

# Front matter first, then the project README as the body of the Space card.
{
    sed '/^<!--$/,$d' "$CARD"
    echo
    cat "$REPO_ROOT/README.md"
} > "$STAGE/space/README.md"

cd "$STAGE/space"
if [[ -z "$(git status --porcelain)" ]]; then
    echo "Space already matches $COMMIT — nothing to push."
    exit 0
fi

git add -A
git -c user.name="gci-deploy" -c user.email="deploy@localhost" \
    commit -q -m "Deploy grade-change-intelligence @ ${COMMIT}"
git push origin HEAD:main 2>&1 | sed "s|${HF_TOKEN:-__none__}|***|g"

echo
echo "Pushed. Build progress: https://huggingface.co/spaces/${SPACE_ID}?logs=build"
echo "App:                    https://huggingface.co/spaces/${SPACE_ID}"
echo "Health:                 https://$(echo "$SPACE_ID" | tr '/' '-' | tr '[:upper:]' '[:lower:]').hf.space/api/health"
