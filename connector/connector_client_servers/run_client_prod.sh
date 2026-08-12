#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt

echo ""
echo "ClientDocs source API (prod) -> http://localhost:8002/docs"
echo "Ctrl-C to stop."
CLIENTDOCS_DATA=data/prod.json uvicorn clientdocs:app --port 8002
