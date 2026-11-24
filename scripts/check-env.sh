#!/usr/bin/env bash
# check-env.sh — verify the local development environment (PHASE 0).
# Usage: bash scripts/check-env.sh
# Exits non-zero if a REQUIRED tool is missing. Docker is reported as a
# WARNING (blocking `docker compose up`, documented in PROJECT_STATUS.md).

set -u

ok()   { printf '[OK]   %s\n' "$1"; }
warn() { printf '[WARN] %s\n' "$1"; }
fail() { printf '[FAIL] %s\n' "$1"; }

failures=0

check() {
  local name="$1" min_version="${2:-}"
  if ! command -v "$name" >/dev/null 2>&1; then
    fail "$name not found"
    failures=$((failures + 1))
    return
  fi
  local version
  version=$("$name" --version 2>&1 | head -n 1)
  ok "$name — $version"
}

check node
check npm
check python3
check pip3
check git

if command -v docker >/dev/null 2>&1; then
  ok "docker — $(docker --version)"
  if docker compose version >/dev/null 2>&1; then
    ok "docker compose — $(docker compose version)"
  else
    warn "docker compose plugin missing (docker compose up will fail)"
  fi
else
  warn "docker not found — 'docker compose up' is BLOCKED on this machine."
  warn "Install Docker (https://docs.docker.com/engine/install/) before PHASE 1."
fi

if [ "$failures" -gt 0 ]; then
  echo "check-env: $failures required tool(s) missing."
  exit 1
fi
echo "check-env: required tools present (see warnings above)."
