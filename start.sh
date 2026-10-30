#!/usr/bin/env sh
# macOS / Linux: ./start.sh
cd "$(dirname "$0")" && uv run server/main.py
