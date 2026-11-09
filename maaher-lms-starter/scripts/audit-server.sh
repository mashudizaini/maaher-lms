#!/usr/bin/env bash
# Read-only server inventory. Review before use; no sudo, no changes.
set -u
printf '== Basic ==\n'; date -u; uname -a; (cat /etc/os-release 2>/dev/null || true) | head -12
printf '\n== CPU/memory ==\n'; (command -v nproc >/dev/null && nproc) || true; (command -v free >/dev/null && free -h) || true
printf '\n== Filesystems ==\n'; df -hT 2>/dev/null || true; (command -v lsblk >/dev/null && lsblk -o NAME,SIZE,TYPE,MOUNTPOINTS) || true
printf '\n== Docker ==\n'; (docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'Docker unavailable/permission denied'); (docker compose version 2>/dev/null || true)
printf '\n== Listening ports (local only) ==\n'; (ss -lnt 2>/dev/null || true) | head -60
printf '\n== Security/ops availability ==\n'; command -v ufw || true; command -v firewalld || true; command -v tailscale || true; command -v cloudflared || true
printf '\nDo not publish raw logs; review & redact identifiers before sharing.\n'
