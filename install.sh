#!/usr/bin/env bash
# Link the skill into Claude Code and check the one dependency that matters.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
TARGET="$SKILLS/consensus"

command -v python3 >/dev/null || { echo "need python3"; exit 1; }
command -v yt-dlp  >/dev/null || {
  echo "need yt-dlp - install with: brew install yt-dlp"
  echo "                        or: pip install -U yt-dlp"
  exit 1
}

mkdir -p "$SKILLS"
if [ -e "$TARGET" ] && [ ! -L "$TARGET" ]; then
  echo "$TARGET exists and is not a symlink - move it aside first"; exit 1
fi
ln -sfn "$HERE" "$TARGET"

echo "linked $TARGET -> $HERE"
echo "python3 $(python3 -c 'import sys;print(".".join(map(str,sys.version_info[:2])))')  yt-dlp $(yt-dlp --version)"
echo
echo "restart Claude Code, then run:  /consensus <topic>"
