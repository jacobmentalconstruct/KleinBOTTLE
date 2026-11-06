#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"

echo "[KleinBOTTLE] Creating virtual environment..."
python3 -m venv .venv

echo "[KleinBOTTLE] Installing dependencies..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt

echo ""
echo "Setup complete.  Run ./run.sh to start KleinBOTTLE."
