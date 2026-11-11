"""Run real Chromium against production Next + API on an empty disposable DB.

Requires TEST_MIGRATION_DATABASE_URL and TEST_DATABASE_URL, Python test deps,
npm ci/build and Playwright Chromium. Leaves the DB intact, stops only children.
"""
from contextlib import ExitStack
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import psycopg
from cryptography.fernet import Fernet


ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def ready(process, url):
    deadline = time.monotonic()+45
    with httpx.Client(timeout=2, trust_env=False) as client:
        while time.monotonic() < deadline:
            assert process.poll() is None, "Test server exited before readiness"
            try:
                if client.get(url).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.1)
    raise RuntimeError("Test server readiness timeout")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--oidc', action='store_true', help='Use the test-only signed OIDC provider probe')
    parser.add_argument('--dev-totp', action='store_true', help='Exercise local synthetic TOTP assurance with --oidc')
    parser.add_argument('--courses', action='store_true', help='Run course authoring after synthetic OIDC login')
    parser.add_argument('--enrollment', action='store_true', help='Run enrollment and student access browser tests with --oidc')
    parser.add_argument('--learning', action='store_true', help='Run completion and student navigation browser tests with --oidc')
    args = parser.parse_args()
    if args.learning and not args.oidc:
        parser.error('--learning requires --oidc')
    if args.enrollment and not args.oidc:
        parser.error('--enrollment requires --oidc')
    if args.dev_totp and not args.oidc:
        parser.error('--dev-totp requires --oidc')
    if args.courses and not args.oidc:
        parser.error('--courses requires --oidc')
    owner = os.environ["TEST_MIGRATION_DATABASE_URL"]
    runtime = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(owner) as db:
        name = db.execute("SELECT current_database()").fetchone()[0]
        assert name.startswith("maaher_test_"), "Refusing non-test database"
        assert db.execute("SELECT to_regclass('public.users')").fetchone()[0] is None, "Needs empty DB"
    with psycopg.connect(runtime) as db:
        assert db.execute("SELECT current_database()").fetchone()[0] == name
    auth=os.environ['TEST_AUTH_DATABASE_URL']
    with psycopg.connect(auth) as db:
        assert db.execute('SELECT current_database()').fetchone()[0] == name
    api_port, web_port = free_port(), free_port()
    env = os.environ.copy()
    env.update(MIGRATION_DATABASE_URL=owner, DATABASE_URL=runtime, AUTH_DATABASE_URL=auth, APP_ENV="local",
               LOCAL_INSECURE_COOKIES="true", AUTH_ENCRYPTION_KEY=Fernet.generate_key().decode(),
               APP_ORIGIN=f"http://127.0.0.1:{web_port}", API_BASE_URL=f"http://127.0.0.1:{api_port}",
               PYTHONPATH=str(ROOT/"apps/api"), LMS_TEST_PYTHON=sys.executable,
               LMS_TEST_ROOT=str(ROOT), NEXT_TELEMETRY_DISABLED="1",
               AUTH0_DOMAIN="", AUTH0_CLIENT_ID="", AUTH0_CLIENT_SECRET="")
    env['AUTH0_ASSURANCE_PROFILE'] = 'dev-totp' if args.dev_totp else 'fido2'
    target = 'app.main:app'
    test_file = 'auth.spec.ts'
    if args.oidc:
        # Probe module is under tests/, never copied into the runtime API image.
        target = 'oidc_browser_probe:app'
        test_file = 'oidc.spec.ts'
        if args.courses:
            test_file = 'courses.spec.ts'
        if args.enrollment:
            test_file = 'enrollment.spec.ts'
        if args.learning:
            test_file = 'learning.spec.ts'
        env.update(AUTH0_DOMAIN='browser-tests.us.auth0.com', AUTH0_CLIENT_ID='synthetic-browser-client',
                   AUTH0_CLIENT_SECRET='synthetic-browser-client-secret-not-a-real-credential',
                   PYTHONPATH=os.pathsep.join((str(ROOT/'apps/api'),str(ROOT/'apps/api/tests'))))
    subprocess.run([sys.executable, "-m", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head"],
                   env=env, cwd=ROOT, check=True)
    with ExitStack() as stack:
        api = subprocess.Popen([sys.executable, "-m", "uvicorn", target, "--host", "127.0.0.1",
                                "--port", str(api_port), "--no-access-log", "--log-level", "error"],
                               env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        stack.callback(stop, api)
        ready(api, env["API_BASE_URL"]+"/healthz")
        web = subprocess.Popen(["node", "node_modules/next/dist/bin/next", "start", "-H", "127.0.0.1", "-p", str(web_port)],
                               env=env, cwd=ROOT/"apps/web", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        stack.callback(stop, web)
        ready(web, env["APP_ORIGIN"]+"/auth")
        result = subprocess.run(["node", "node_modules/@playwright/test/cli.js", "test", test_file],
                                env=env, cwd=ROOT/"apps/web")
        print(f"Browser tests exit={result.returncode}; database retained: {name}")
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
