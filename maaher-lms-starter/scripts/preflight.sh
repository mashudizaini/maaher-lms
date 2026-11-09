#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] || { echo 'ERROR: Create .env from .env.example'; exit 1; }
password="$(sed -n 's/^POSTGRES_PASSWORD=//p' .env | tail -1)"
[[ -n "$password" && "$password" != "REPLACE_WITH_LONG_RANDOM_VALUE" && ${#password} -ge 20 ]] || { echo 'ERROR: set strong POSTGRES_PASSWORD (>=20 chars)'; exit 1; }
if git ls-files --error-unmatch .env >/dev/null 2>&1; then echo 'ERROR: .env is tracked in git'; exit 1; fi
echo 'PASS: env credentials preflight (not a comprehensive security audit)'
