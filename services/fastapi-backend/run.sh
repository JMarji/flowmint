#!/bin/bash
set -e
cd "$(dirname "$0")"
source .env 2>/dev/null || true
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
