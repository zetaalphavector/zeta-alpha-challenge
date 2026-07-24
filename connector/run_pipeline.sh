#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo "Pipeline Service (ingestion) -> http://localhost:8001/docs"
echo "Ctrl-C to stop."
uvicorn pipeline_mock:app --port 8001
