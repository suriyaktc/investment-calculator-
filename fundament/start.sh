#!/usr/bin/env bash
# Fundament — Investor Education Platform
# macOS / Linux startup script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   F U N D A M E N T  v1.0.0          ║"
echo "  ║   Investor Education Platform         ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Find Python
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "  ERROR: Python 3 not found."
    echo "  Install it from: https://www.python.org/downloads/"
    echo "  Or via Homebrew: brew install python3"
    exit 1
fi

PYVER=$($PYTHON -c "import sys; print(sys.version_info.major)")
if [ "$PYVER" -lt "3" ]; then
    echo "  ERROR: Python 3 required (found Python 2)"
    exit 1
fi

echo "  Using: $($PYTHON --version)"
echo "  Starting server at http://localhost:8080"
echo ""

$PYTHON server.py
