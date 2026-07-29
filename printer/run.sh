#!/bin/bash
cd "$(dirname "$0")"
set -a; [ -f .env ] && . ./.env; set +a
exec python3 label_agent.py
