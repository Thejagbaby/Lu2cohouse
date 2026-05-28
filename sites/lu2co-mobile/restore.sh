#!/bin/bash
# LU2CO V1 — Restore Tool
# Usage:
#   ./restore.sh          → show all saved checkpoints
#   ./restore.sh <hash>   → restore to that checkpoint

cd "$(dirname "$0")"

if [ -z "$1" ]; then
  echo "=== Saved checkpoints ==="
  git log --oneline --format="%C(yellow)%h%Creset  %C(green)%ar%Creset  %s"
  echo ""
  echo "To restore: ./restore.sh <hash>"
else
  echo "Restoring to $1..."
  git checkout "$1" -- index.html
  echo "Done. index.html restored to checkpoint $1"
fi
