#!/bin/bash
set -e

REPO_URL="https://github.com/tieguy/rubber-duck.git"
REPO_DIR="/app/repo"

echo "=== Rubber Duck Startup ==="

# Clone or update repo
if [[ -d "$REPO_DIR/.git" ]]; then
    echo "Repo exists, pulling latest..."
    cd "$REPO_DIR"
    git fetch origin
    git reset --hard origin/main
else
    echo "Cloning repo..."
    # Use token for auth if available
    if [[ -n "$GITHUB_TOKEN" ]]; then
        git clone "https://${GITHUB_TOKEN}@github.com/tieguy/rubber-duck.git" "$REPO_DIR"
    else
        echo "WARNING: No GITHUB_TOKEN set, cloning without auth (push will fail)"
        git clone "$REPO_URL" "$REPO_DIR"
    fi
    cd "$REPO_DIR"
fi

# Configure git identity
git config user.email "${GIT_EMAIL:-rubber-duck@bot.local}"
git config user.name "${GIT_NAME:-Rubber Duck Bot}"

# Set up push URL with token
if [[ -n "$GITHUB_TOKEN" ]]; then
    git remote set-url origin "https://${GITHUB_TOKEN}@github.com/tieguy/rubber-duck.git"
fi

# Link persistent state directory
# fly.toml mounts persistent storage at /app/state
# Code expects state at /app/repo/state (relative to cloned repo)
echo "Linking persistent state..."
rm -rf "$REPO_DIR/state" 2>/dev/null || true
ln -s /app/state "$REPO_DIR/state"

# Install/update dependencies
echo "Installing dependencies..."
uv sync --frozen

# Run the bot from the cloned repo
echo "Starting bot..."
exec uv run python -m rubber_duck
