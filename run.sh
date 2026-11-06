#!/usr/bin/env sh
cd "$(dirname "$0")"
if [ -x ".venv/bin/python" ]; then
    .venv/bin/python -m kleinos
else
    python3 -m kleinos
fi
