#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$ROOT_DIR"
pyinstaller --clean --onefile --name jterm jterm.py
echo "Build complete: $ROOT_DIR/dist/jterm"
echo "Ensure PATH includes: $ROOT_DIR/dist"
echo "Try: jterm \"http://localhost:8888/?token=1234\""
