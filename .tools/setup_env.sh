#!/usr/bin/env bash
set -e
echo "=== .dev-tools environment setup ==="

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found on PATH."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

if [ -f requirements.txt ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

echo "Environment ready."
