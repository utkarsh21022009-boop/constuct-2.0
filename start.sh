#!/usr/bin/env bash
# FixPilot AI Launch Script
# Team Slither · Industrial Troubleshooting Copilot

set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=================================================="
echo " Starting FixPilot AI · Industrial Troubleshooting"
echo " Team Slither · Evidence-Guided Copilot"
echo "=================================================="
echo ""

PORT="${1:-8000}"

# Run tests first to verify integrity
python3 -m unittest discover tests

echo ""
echo "All tests passed. Launching Web Server on port $PORT..."
echo "Open your browser at: http://localhost:$PORT"
echo ""

exec python3 run.py --port "$PORT"
