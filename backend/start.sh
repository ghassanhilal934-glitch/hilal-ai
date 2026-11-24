#!/bin/sh
set -e
cd "$(dirname "$0")"
: "${PORT:=8000}"
exec uvicorn app:app --host 0.0.0.0 --port "$PORT"
