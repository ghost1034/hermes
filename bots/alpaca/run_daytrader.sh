#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -a
[ -f "$SCRIPT_DIR/.env" ] && source "$SCRIPT_DIR/.env"
set +a

python3 "$SCRIPT_DIR/daytrader.py" >> "$SCRIPT_DIR/daytrader.log" 2>&1