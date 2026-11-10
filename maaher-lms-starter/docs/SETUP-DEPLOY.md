# 04 — Mac Intel, Tailscale server audit, GitHub & Cloudflare

LMS-01 kini membutuhkan konfigurasi role API/migrasi/mail terpisah, encryption
key dan origin browser. Baca [ADR-001](adr/001-auth-lifecycle.md),
[checklist LMS-01](LMS-01-CHECKLIST.md) dan [handoff](LMS-01-HANDOFF.md) sebelum
memakai instruksi deployment umum di bawah. Belum ada izin deploy/merge;
pengiriman email nyata, operator MFA dan review independen masih menjadi gate.

## A. Mac Intel prerequisites
Use Homebrew: Git, GitHub CLI (`gh`), Node.js LTS, Python supported by FastAPI, Docker Desktop **Intel/amd64 build**, Codex CLI, Claude Code CLI. Validate with:
```bash
uname -m     # x86_64 on Intel Mac
node --version && npm --version
python3 --version && git --version
docker version && docker compose version
gh auth status
codex --version
claude --version
```
Install CLI from **official current** installation docs; do not treat `npm install -g ...` from an unverified package as an official route. `docker compose up --build -d` uses images on the development machine.

## B. Read-only server audit BEFORE deployment
`100.127.103.49` is in Tailscale's `100.64.0.0/10` shared address range; confirm it really belongs to the server and tailnet before connecting.
```bash
tailscale status
ssh <your-server-user>@100.127.103.49 'hostname; uname -a'
# Upload/copy scripts/audit-server.sh; inspect script first
ssh <your-server-user>@100.127.103.49 'bash -s' < scripts/audit-server.sh
```
Report: OS/kernel, architecture, CPU, RAM, storage, swap, Docker/Compose version, listening ports, disk usage, Tailscale connectivity, service managers. Redact hostnames/usernames/public IPs as required. Script does not install/change anything; avoid uploading whole diagnostics publicly.

**Deployment gate:** choose Linux/amd64 or arm64 images based on result; >= recommended capacity only after learner concurrency and grader sizing. Confirm backup location, firewall, SSH keys, non-root deploy user, storage volume space and isolation from existing production services.

## C. GitHub repository — no push automatically performed
```bash
cd maaher-lms-starter
git init -b main
git add . && git commit -m 'chore: initialize maaher LMS factory scaffold'
gh auth login
# Create only after confirming account and repo name:
gh repo create mashudizaini/maaher-lms --private --source=. --remote=origin --push
```
Enable branch protection for `main` (PR required, CI checks, human approval), secret scanning if available; CI does not auto-deploy. Prefer GitHub Environment approvals for `uat`/`production`.

## D. Developer deployment over Tailscale
After audit, transfer repo via GitHub checkout on server using **read-only deploy key**, configure `.env` from vault/secure transfer; use unique strong password. On Linux server:
```bash
cp .env.example .env
# Edit .env; do not leave REPLACE_WITH_LONG_RANDOM_VALUE
# Verify compose configuration
bash scripts/preflight.sh
sudo docker compose config --quiet
sudo docker compose up --build -d
curl --fail http://127.0.0.1:3000/api/health
```
Choose `sudo` only if local Docker user permissions require it; audit Docker privileges. Do not publish ports directly; compose binds Next.js only to loopback.

## E. Cloudflare UAT → production on same hostname
1. Domain `aimz.my.id` must already be under a Cloudflare zone controlled by owner.
2. Create Cloudflare Tunnel with `cloudflared` on audited host; use **Cloudflare dashboard**: Zero Trust → Networks/Connectors → Tunnels → Create tunnel (actual UI can vary).
3. Add published hostname `maaherlms.aimz.my.id` → `http://127.0.0.1:3000`; bind tunnel service to this same host.
4. Apply **Cloudflare Access** policy before exposing UAT; allow only authorized tester identities. Do not use a shared admin password. Test in external network.
5. At production go-live: remove/change UAT Access restrictions only after app auth + privacy + backups + tenant tests + monitoring + security review, and verify public access intentionally.
6. Keep backend PostgreSQL isolated in Docker network; not reachable from public network or Cloudflare. Control DNS, HTTPS, origin headers and rate limits.
7. Hostname DNS/tunnel routes are not created by this package; no Cloudflare API tokens stored in Git.

## F. Rollback & backup
Pre-release DB snapshot and restore rehearsal, version-tagged images and migrations with forward-compatible rollout; preserve old image for rollback. Rolling code back does not automatically reverse DB migrations. Staging test using synthetic learners only.

## References
- https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/
- https://tailscale.com/docs/concepts/tailscale-ip-addresses
- https://docs.docker.com/engine/security/

## Dependency snapshots
`apps/web/package-lock.json` kini tersedia; Dockerfile dan CI memakai `npm ci`.
API memiliki `requirements.lock` dan `requirements-dev.lock`. Lihat handoff
untuk hasil nyata instalasi, audit advisori dan pengujian platform. Snapshot
versi bukan jaminan bebas kerentanan; audit ulang sebelum release. Jangan
mengikuti klaim offline historis pada handoff sebagai status pengujian terbaru.
