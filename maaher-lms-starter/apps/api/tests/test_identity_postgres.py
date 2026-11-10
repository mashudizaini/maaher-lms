"""Real PostgreSQL tests. An empty disposable maaher_test_* database is required.

Never point these URLs at a shared database. Missing configuration skips this
suite, which must not be interpreted as passing the tenant security gate.
"""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from auth_helpers import sign_in,authorize_mfa,enroll_mfa,make_admin,mail_token,issue_invite
from app.database import session_context
from app.security import token_digest

pytestmark = pytest.mark.skipif(
    not all(os.environ.get(k) for k in ("TEST_MIGRATION_DATABASE_URL","TEST_DATABASE_URL","TEST_AUTH_DATABASE_URL","TEST_OPERATOR_DATABASE_URL")),
    reason="Requires disposable PostgreSQL owner and runtime URLs",
)


    # Leave test database intact for inspection. Next run needs a new empty DB.










def test_session_cookie_tenant_role_and_logout(identity):
    client, _, user, tenant, foreign, email, password = identity
    assert client.get("/auth/me").status_code == 401
    assert client.post("/auth/login", json={"email": email, "password": password}).status_code == 403
    response = sign_in(client, email, password)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert all(flag in cookie for flag in ("httponly", "secure", "samesite=lax"))
    assert "no-store" in response.headers["cache-control"]
    assert client.get("/auth/memberships").json() == [
        {"tenant_id": str(tenant), "name": "Test", "role": "student"}]
    assert client.get("/auth/me", headers={"x-tenant-id": str(foreign)}).status_code == 403
    assert client.get("/auth/me", headers={"x-tenant-id": "invalid"}).status_code == 403
    headers = {"x-tenant-id": str(tenant), "origin": "https://testserver"}
    assert client.get("/auth/me", headers=headers).json()["user_id"] == str(user)
    assert client.get("/auth/audit", headers=headers).status_code == 403
    assert client.post("/auth/tenant-selection", headers=headers).status_code == 200
    old_token = client.cookies.get("maaher_session")
    assert client.post("/auth/logout", headers=headers).status_code == 200
    client.cookies.set("maaher_session", old_token)
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_revocation_expiry_disabled_user_and_tenant(identity):
    import psycopg
    client, owner, user, tenant, _, email, password = identity
    headers = {"x-tenant-id": str(tenant)}
    assert sign_in(client, email, password).status_code == 200
    with psycopg.connect(owner) as db:
        db.execute("UPDATE memberships SET status='revoked' WHERE user_id=%s", (user,))
    assert client.get("/auth/me", headers=headers).status_code == 403
    with psycopg.connect(owner) as db:
        db.execute("UPDATE memberships SET status='active' WHERE user_id=%s", (user,))
        db.execute("UPDATE tenants SET status='disabled' WHERE id=%s", (tenant,))
    assert client.get("/auth/me", headers=headers).status_code == 403
    with psycopg.connect(owner) as db:
        db.execute("UPDATE tenants SET status='active' WHERE id=%s", (tenant,))
        db.execute("UPDATE sessions SET expires_at=now()-interval '1 second' WHERE user_id=%s", (user,))
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert sign_in(client, email, password).status_code == 200
    with psycopg.connect(owner) as db:
        db.execute("UPDATE users SET status='disabled' WHERE id=%s", (user,))
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_failed_login_throttle_persists(identity):
    client, _, _, _, _, email, password = identity
    for _ in range(10):
        assert sign_in(client, email, "wrong password").status_code == 401
    # A correct password must not be vetoed by an attacker's failed attempts.
    assert sign_in(client, email, "wrong password").status_code == 429
    assert sign_in(client, email, password).status_code == 200
    assert sign_in(client, email, "wrong password").status_code == 401


def test_direct_rls_reads_writes_context_and_audit_immutability(identity):
    import psycopg
    from app.database import transaction, user_context, tenant_context
    client, owner, user, tenant, foreign, email, password = identity
    assert sign_in(client, email, password).status_code == 200
    headers = {"x-tenant-id": str(tenant), "origin": "https://testserver"}
    assert client.post("/auth/tenant-selection", headers=headers).status_code == 200
    with psycopg.connect(owner) as db:
        db.execute("UPDATE memberships SET role='admin' WHERE user_id=%s", (user,))
    enroll_mfa(client, password)
    assert len(client.get("/auth/audit", headers=headers).json()) == 1
    with transaction() as db:
        assert db.execute("SELECT * FROM tenants").fetchall() == []
        assert db.execute("SELECT * FROM memberships").fetchall() == []
        assert db.execute("SELECT * FROM audit_events").fetchall() == []
        user_context(db, user)
        session_context(db, token_digest(client.cookies.get("maaher_session", "")))
        tenant_context(db, foreign)
        assert db.execute("SELECT * FROM tenants WHERE id=%s", (foreign,)).fetchall() == []
        assert db.execute("SELECT * FROM audit_events").fetchall() == []
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with transaction() as db:
            user_context(db, user)
            session_context(db, token_digest(client.cookies.get("maaher_session", "")))
            tenant_context(db, foreign)
            db.execute("INSERT INTO audit_events(id,tenant_id,actor_id,action) VALUES (%s,%s,%s,'forged')",
                       (uuid4(), foreign, user))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with transaction() as db:
            user_context(db, user)
            session_context(db, token_digest(client.cookies.get("maaher_session", "")))
            tenant_context(db, tenant)
            db.execute("UPDATE memberships SET role='admin' WHERE user_id=%s", (user,))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with transaction() as db:
            user_context(db, user)
            session_context(db, token_digest(client.cookies.get("maaher_session", "")))
            tenant_context(db, tenant)
            db.execute("DELETE FROM audit_events WHERE tenant_id=%s", (tenant,))
    with transaction() as db:
        assert db.execute("SELECT * FROM tenants").fetchall() == []


def test_owner_database_connection_is_rejected(identity, monkeypatch):
    from app.database import transaction
    monkeypatch.setenv("DATABASE_URL", identity[1])
    with pytest.raises(RuntimeError, match="role runtime"):
        with transaction():
            pass


def test_all_private_routes_require_authentication(identity):
    client = identity[0]
    for path in ("/auth/me", "/auth/memberships", "/auth/audit", "/auth/security-events"):
        assert client.get(path).status_code == 401
    for path in ("/auth/logout", "/auth/tenant-selection"):
        assert client.post(path, headers={"origin": "https://testserver"}).status_code == 401


def test_runtime_role_and_forced_rls_are_verified(identity):
    from app.database import transaction

    with transaction() as db:
        role = db.execute("""SELECT rolsuper,rolbypassrls FROM pg_roles
                             WHERE rolname=current_user""").fetchone()
        assert role == {"rolsuper": False, "rolbypassrls": False}
        tables = db.execute("""
            SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,
                   pg_has_role(current_user,c.relowner,'USAGE') AS owns
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relname IN ('tenants','memberships','audit_events')
        """).fetchall()
        assert len(tables) == 3
        assert all(t["relrowsecurity"] and t["relforcerowsecurity"] and not t["owns"] for t in tables)


def test_existing_foreign_object_is_hidden_and_role_changes_take_effect(identity):
    import psycopg
    from app.database import transaction, user_context, tenant_context

    client, owner, user, tenant, foreign, email, password = identity
    event_id = uuid4()
    with psycopg.connect(owner) as db:
        actor = db.execute("SELECT user_id FROM memberships WHERE tenant_id=%s", (foreign,)).fetchone()[0]
        db.execute("INSERT INTO audit_events(id,tenant_id,actor_id,action) VALUES (%s,%s,%s,'private.event')",
                   (event_id, foreign, actor))
        db.execute("UPDATE memberships SET role='teacher' WHERE user_id=%s", (user,))
    assert sign_in(client, email, password).status_code == 200
    headers = {"x-tenant-id": str(tenant)}
    assert client.get("/auth/audit", headers=headers).status_code == 403
    with psycopg.connect(owner) as db:
        db.execute("UPDATE memberships SET role='admin' WHERE user_id=%s", (user,))
    assert client.get("/auth/audit", headers=headers).status_code == 403
    enroll_mfa(client, password)
    assert client.get("/auth/audit", headers=headers).status_code == 200
    with transaction() as db:
        user_context(db, user)
        session_context(db, token_digest(client.cookies.get("maaher_session", "")))
        tenant_context(db, tenant)
        assert db.execute("SELECT id FROM audit_events WHERE id=%s", (event_id,)).fetchall() == []
        assert db.execute("SELECT count(*) AS n FROM audit_events WHERE id=%s", (event_id,)).fetchone()["n"] == 0
    with psycopg.connect(owner) as db:
        db.execute("UPDATE memberships SET role='student' WHERE user_id=%s", (user,))
    assert client.get("/auth/audit", headers=headers).status_code == 403


def test_session_and_audit_survive_api_process_restart(identity):
    """Restart only API processes created by this test; keep the same test DB."""
    from contextlib import contextmanager
    import socket
    import subprocess
    import sys
    import time

    import httpx
    import psycopg

    client, owner, user, tenant, _, email, password = identity
    with psycopg.connect(owner) as db:
        db.execute("UPDATE memberships SET role='admin' WHERE user_id=%s", (user,))
    assert sign_in(client, email, password).status_code == 200
    enroll_mfa(client, password)
    token = client.cookies.get("maaher_session")
    headers = {"cookie": f"maaher_session={token}", "x-tenant-id": str(tenant),
               "origin": "https://testserver"}

    @contextmanager
    def running_api():
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parents[1])
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
             "--port", str(port), "--no-access-log", "--log-level", "error"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=2, trust_env=False) as api:
                deadline = time.monotonic() + 15
                while True:
                    assert process.poll() is None, "Test API exited before readiness"
                    try:
                        if api.get("/healthz").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    assert time.monotonic() < deadline, "Test API readiness timed out"
                    time.sleep(0.05)
                yield api
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    # Explicit Cookie header exercises an existing Secure session over the
    # test-only loopback transport. No browser cookie policy claim is made here.
    with running_api() as api:
        assert api.get("/auth/me", headers=headers).json()["user_id"] == str(user)
        assert api.post("/auth/tenant-selection", headers=headers).status_code == 200
    # The first process has fully exited before the second starts.
    with running_api() as api:
        assert api.get("/auth/me", headers=headers).json()["user_id"] == str(user)
        persisted = api.get("/auth/audit", headers=headers)
        assert persisted.status_code == 200
        assert [event["action"] for event in persisted.json()] == ["tenant.selected"]
        assert api.post("/auth/logout", headers=headers).status_code == 200
        assert api.get("/auth/me", headers=headers).status_code == 401








def test_invitation_new_user_one_use_and_no_secret_in_audit(identity):
    import psycopg
    from app.security import token_digest
    client, owner, _, tenant, _, _, password = identity
    headers, _ = make_admin(identity)
    email, token = issue_invite(identity, headers, role="teacher")
    with psycopg.connect(owner) as db:
        assert db.execute("SELECT token_hash FROM invitations WHERE email=%s", (email,)).fetchone()[0] == token_digest(token)
    client.cookies.clear()
    body = {"token": token, "password": password}
    response = client.post("/auth/invitations/accept", json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert client.post("/auth/invitations/accept", json=body, headers=headers).status_code == 400
    assert sign_in(client, email, password).status_code == 200
    assert client.get("/auth/me", headers=headers).json()["role"] == "teacher"
    with psycopg.connect(owner) as db:
        actions = db.execute("SELECT action FROM audit_events WHERE tenant_id=%s", (tenant,)).fetchall()
        assert sorted(a[0] for a in actions) == ["invitation.accepted", "invitation.created"]
        assert token not in repr(actions) and password not in repr(actions)


def test_existing_invitee_requires_own_session_and_keeps_password(identity):
    import psycopg
    client, owner, _, tenant, foreign, _, password = identity
    headers, _ = make_admin(identity)
    with psycopg.connect(owner) as db:
        invited = db.execute("SELECT u.email FROM users u JOIN memberships m ON m.user_id=u.id WHERE m.tenant_id=%s", (foreign,)).fetchone()[0]
    _, token = issue_invite(identity, headers, email=invited)
    body = {"token": token, "password": "Cannot change existing password 123!"}
    assert client.post("/auth/invitations/accept", json=body, headers=headers).status_code == 400
    client.cookies.clear()
    assert client.post("/auth/invitations/accept", json=body, headers=headers).status_code == 400
    assert sign_in(client, invited, password).status_code == 200
    assert client.post("/auth/invitations/accept", json={"token": token}, headers=headers).status_code == 200
    client.cookies.clear()
    assert sign_in(client, invited, body["password"]).status_code == 401
    assert sign_in(client, invited, password).status_code == 200
    assert len(client.get("/auth/memberships").json()) == 2


@pytest.mark.parametrize("invalidate", ["expired", "revoked", "inviter_revoked", "tenant_disabled"])
def test_invitation_invalidations(identity, invalidate):
    import psycopg
    client, owner, user, tenant, _, _, password = identity
    headers, _ = make_admin(identity)
    email, token = issue_invite(identity, headers)
    with psycopg.connect(owner) as db:
        if invalidate == "expired":
            db.execute("UPDATE invitations SET expires_at=now()-interval '1 second' WHERE email=%s", (email,))
        elif invalidate == "revoked":
            db.execute("UPDATE invitations SET revoked_at=now() WHERE email=%s", (email,))
        elif invalidate == "inviter_revoked":
            db.execute("UPDATE memberships SET status='revoked' WHERE user_id=%s", (user,))
        else:
            db.execute("UPDATE tenants SET status='disabled' WHERE id=%s", (tenant,))
    client.cookies.clear()
    assert client.post("/auth/invitations/accept", json={"token": token, "password": password}, headers=headers).status_code == 400
    with psycopg.connect(owner) as db:
        assert db.execute("SELECT id FROM users WHERE email=%s", (email,)).fetchone() is None


def test_invitation_resend_invalidates_old_token(identity):
    client, owner, _, _, _, _, password = identity
    headers, _ = make_admin(identity)
    email, old = issue_invite(identity, headers)
    _, new = issue_invite(identity, headers, email=email)
    client.cookies.clear()
    assert client.post("/auth/invitations/accept", json={"token": old, "password": password}, headers=headers).status_code == 400
    assert client.post("/auth/invitations/accept", json={"token": new, "password": password}, headers=headers).status_code == 200


def test_invitation_tenant_roles_and_direct_rls(identity):
    import psycopg
    from app.database import transaction, tenant_context, user_context
    client, owner, user, tenant, foreign, email, password = identity
    assert sign_in(client, email, password).status_code == 200
    headers = {"origin": "https://testserver", "x-tenant-id": str(tenant)}
    body = {"email": "new@example.invalid", "role": "student"}
    for role in ("student", "teacher"):
        with psycopg.connect(owner) as db:
            db.execute("UPDATE memberships SET role=%s WHERE user_id=%s", (role, user))
        assert client.post("/auth/invitations", json=body, headers=headers).status_code == 403
    headers, _ = make_admin(identity)
    _, _ = issue_invite(identity, headers)
    assert client.post("/auth/invitations", json=body, headers={**headers, "x-tenant-id": str(foreign)}).status_code == 403
    assert client.post("/auth/invitations", json={**body, "tenant_id": str(foreign)}, headers=headers).status_code == 422
    with transaction() as db:
        assert db.execute("SELECT * FROM invitations").fetchall() == []
        user_context(db, user)
        session_context(db, token_digest(client.cookies.get("maaher_session", "")))
        tenant_context(db, foreign)
        assert db.execute("SELECT * FROM invitations").fetchall() == []
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with transaction() as db:
            user_context(db, user)
            session_context(db, token_digest(client.cookies.get("maaher_session", "")))
            tenant_context(db, foreign)
            db.execute("INSERT INTO invitations(id,tenant_id,invited_by,email,role,token_hash,expires_at) VALUES (%s,%s,%s,'evil@example.invalid','admin','fake',now())", (uuid4(), foreign, user))


def test_invitation_concurrent_accept_has_one_winner(identity):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi.testclient import TestClient
    from app.main import app
    client, _, _, _, _, _, password = identity
    headers, _ = make_admin(identity)
    _, token = issue_invite(identity, headers)
    def accept(_):
        with TestClient(app, base_url="https://testserver") as independent:
            return independent.post("/auth/invitations/accept", json={"token": token, "password": password}, headers=headers).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(accept, range(2))) == [200, 400]


def test_reset_generic_response_one_use_revokes_all_sessions(identity):
    import psycopg
    from fastapi.testclient import TestClient
    from app.main import app
    client, owner, user, tenant, _, email, password = identity
    headers = {"origin": "https://testserver", "x-tenant-id": str(tenant)}
    assert sign_in(client, email, password).status_code == 200
    old_token = client.cookies.get("maaher_session")
    with TestClient(app, base_url="https://testserver") as second:
        assert sign_in(second, email, password).status_code == 200
        known = client.post("/auth/password-reset/request", json={"email": email}, headers=headers)
        unknown = client.post("/auth/password-reset/request", json={"email": f"{uuid4()}@example.invalid"}, headers=headers)
        assert known.status_code == unknown.status_code == 202
        assert known.json() == unknown.json()
        token = mail_token(owner, email, "password-reset")
        new_password = "New synthetic password 987654!"
        body = {"token": token, "password": new_password}
        assert client.post("/auth/password-reset/confirm", json=body, headers=headers).status_code == 200
        assert second.get("/auth/me", headers=headers).status_code == 401
        assert client.get("/auth/me", headers=headers).status_code == 401
        assert client.post("/auth/password-reset/confirm", json=body, headers=headers).status_code == 400
    assert sign_in(client, email, password).status_code == 401
    assert sign_in(client, email, new_password).status_code == 200
    actions = client.get("/auth/security-events").json()
    assert "password.reset" in [a["action"] for a in actions]
    assert all(secret not in repr(actions) for secret in (token, old_token, password, new_password))
    with psycopg.connect(owner) as db:
        assert db.execute("SELECT count(*) FROM sessions WHERE user_id=%s", (user,)).fetchone()[0] == 1


@pytest.mark.parametrize("invalidate", ["expired", "disabled", "replaced"])
def test_reset_invalidations_and_password_policy(identity, invalidate):
    import psycopg
    client, owner, user, _, _, email, password = identity
    headers = {"origin": "https://testserver"}
    assert client.post("/auth/password-reset/request", json={"email": email}, headers=headers).status_code == 202
    token = mail_token(owner, email, "password-reset")
    assert client.post("/auth/password-reset/confirm", json={"token": token, "password": "short"}, headers=headers).status_code == 422
    with psycopg.connect(owner) as db:
        if invalidate == "expired":
            db.execute("UPDATE password_resets SET expires_at=now()-interval '1 second' WHERE user_id=%s", (user,))
        elif invalidate == "disabled":
            db.execute("UPDATE users SET status='disabled' WHERE id=%s", (user,))
    if invalidate == "replaced":
        assert client.post("/auth/password-reset/request", json={"email": email}, headers=headers).status_code == 202
    assert client.post("/auth/password-reset/confirm", json={"token": token, "password": password}, headers=headers).status_code == 400


def test_reset_throttle_is_persistent_and_does_not_enumerate(identity):
    import psycopg
    client, owner, _, _, _, email, _ = identity
    headers = {"origin": "https://testserver"}
    for _ in range(7):
        response = client.post("/auth/password-reset/request", json={"email": email}, headers=headers)
        assert response.status_code == 202
    with psycopg.connect(owner) as db:
        assert db.execute("SELECT count(*) FROM auth_mail_outbox WHERE recipient=%s AND kind='password-reset'", (email,)).fetchone()[0] == 5


def test_admin_mfa_required_each_login_replay_and_no_password_bypass(identity):
    import psycopg
    client, owner, user, tenant, _, email, password = identity
    with psycopg.connect(owner) as db:
        db.execute("UPDATE memberships SET role='admin' WHERE user_id=%s", (user,))
    assert sign_in(client, email, password).status_code == 200
    headers = {"origin": "https://testserver", "x-tenant-id": str(tenant)}
    for path in ("/auth/me", "/auth/audit"):
        assert client.get(path, headers=headers).status_code == 403
    password_only_token = client.cookies.get("maaher_session")
    totp = enroll_mfa(client, password)
    assert client.cookies.get("maaher_session") != password_only_token
    assert client.get("/auth/me", headers={**headers, "cookie": f"maaher_session={password_only_token}"}).status_code == 401
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.post("/auth/mfa/verify", json={"code": totp.now()}, headers=headers).status_code == 400
    assert client.post("/auth/mfa/enroll", json={"password": password}, headers=headers).status_code == 403
    # New password-authenticated session must not inherit prior MFA verification.
    assert sign_in(client, email, password).status_code == 200
    assert client.get("/auth/audit", headers=headers).status_code == 403
    assert client.post("/auth/password-reset/request", json={"email": email}, headers=headers).status_code == 202
    token = mail_token(owner, email, "password-reset")
    assert client.post("/auth/password-reset/confirm", json={"token": token, "password": password}, headers=headers).status_code == 200
    assert sign_in(client, email, password).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 403
    with psycopg.connect(owner) as db:
        assert db.execute("SELECT confirmed FROM mfa_factors WHERE user_id=%s", (user,)).fetchone()[0]


def test_mfa_throttles_expired_enrollment_across_logins_on_attacking_network(identity):
    import psycopg
    client,owner,user,_,_,email,password=identity
    assert sign_in(client,email,password).status_code==200
    headers={'origin':'https://testserver'}
    grant=authorize_mfa(client)
    assert client.post('/auth/mfa/enroll',json={'password':password,'authorization':grant},headers=headers).status_code==200
    with psycopg.connect(owner) as db:
        db.execute("UPDATE mfa_enrollments SET expires_at=now()-interval '1 second' WHERE user_id=%s",(user,))
    for _ in range(5):
        assert client.post('/auth/mfa/verify',json={'code':'000000'},headers=headers).status_code==400
    assert client.post('/auth/mfa/verify',json={'code':'000000'},headers=headers).status_code==429
    assert sign_in(client,email,password).status_code==200
    assert client.post('/auth/mfa/verify',json={'code':'000000'},headers=headers).status_code==429


def test_revoke_is_tenant_scoped_and_does_not_allow_invite_reactivation(identity):
    import psycopg
    from fastapi.testclient import TestClient
    from app.main import app
    client, owner, user, tenant, foreign, _, password = identity
    headers, _ = make_admin(identity)
    with psycopg.connect(owner) as db:
        other, email = db.execute("SELECT u.id,u.email FROM users u JOIN memberships m ON m.user_id=u.id WHERE m.tenant_id=%s", (foreign,)).fetchone()
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES (%s,%s,%s,'teacher')", (uuid4(), tenant, other))
    _, token = issue_invite(identity, headers, email=email, role="admin")
    with TestClient(app, base_url="https://testserver") as target:
        assert sign_in(target, email, password).status_code == 200
        assert target.get("/auth/me", headers=headers).status_code == 200
        assert client.post(f"/auth/memberships/{other}/revoke", headers={**headers, "x-tenant-id": str(foreign)}).status_code == 403
        assert client.post(f"/auth/memberships/{other}/revoke", headers=headers).status_code == 200
        assert target.get("/auth/me", headers=headers).status_code == 403
        assert target.get("/auth/me", headers={"x-tenant-id": str(foreign)}).status_code == 200
        assert target.post("/auth/invitations/accept", json={"token": token}, headers=headers).status_code == 400
    assert client.post(f"/auth/memberships/{user}/revoke", headers=headers).status_code == 404
    assert client.post(f"/auth/memberships/{uuid4()}/revoke", headers=headers).status_code == 404
    assert "membership.revoked" in [e["action"] for e in client.get("/auth/audit", headers=headers).json()]
    revoked = next(e for e in client.get("/auth/audit", headers=headers).json() if e["action"] == "membership.revoked")
    assert revoked["target_type"] == "user" and revoked["target_id"] == str(other)


def test_new_mutations_require_origin_and_private_routes_reject_anonymous(identity):
    client = identity[0]
    for path, body in (("/auth/invitations", {"email": "x@example.invalid", "role": "student"}),
                       ("/auth/invitations/accept", {"token": "x"*43}),
                       ("/auth/password-reset/request", {"email": "x@example.invalid"}),
                       ("/auth/password-reset/confirm", {"token": "x"*43, "password": "Synthetic password 123"}),
                       ("/auth/mfa/enroll", {"password": "x"}),
                       ("/auth/mfa/verify", {"code": "123456"}),
                       (f"/auth/memberships/{uuid4()}/revoke", None)):
        assert client.post(path, json=body).status_code == 403
        assert client.post(path, json=body, headers={"origin": "https://evil.invalid"}).status_code == 403
    for path, body in (("/auth/invitations", {"email": "x@example.invalid", "role": "student"}),
                       ("/auth/mfa/enroll", {"password": "x"}), ("/auth/mfa/verify", {"code": "123456"}),
                       (f"/auth/memberships/{uuid4()}/revoke", None)):
        assert client.post(path, json=body, headers={"origin": "https://testserver"}).status_code == 401


def test_mail_role_delivery_retry_expiry_and_runtime_cannot_read_outbox(identity, monkeypatch):
    import smtplib
    import psycopg
    from psycopg.rows import dict_row
    from app.database import transaction
    from app.mail_worker import deliver_one
    client, owner, _, _, _, email, _ = identity
    headers = {"origin": "https://testserver"}
    monkeypatch.setenv("SMTP_FROM", "lms@example.invalid")
    assert client.post("/auth/password-reset/request", json={"email": email}, headers=headers).status_code == 202
    token = mail_token(owner, email, "password-reset")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with transaction() as db:
            db.execute("SELECT * FROM auth_mail_outbox")
    sent = []
    with psycopg.connect(owner, row_factory=dict_row) as db:
        # Other tests leave mail; isolate only this test's recipient for the worker.
        db.execute("UPDATE auth_mail_outbox SET expires_at=now()-interval '1 second' WHERE recipient<>%s", (email,))
        db.execute("SET LOCAL ROLE maaher_mailer")
        def fail(message):
            raise smtplib.SMTPException("synthetic failure")
        mail_id=db.execute('SELECT id FROM auth_mail_outbox WHERE recipient=%s',(email,)).fetchone()['id']
        assert deliver_one(db, fail)
        assert db.execute("SELECT attempts FROM auth_mail_outbox WHERE recipient=%s", (email,)).fetchone()["attempts"] == 1
        assert not deliver_one(db, sent.append)
        db.execute("UPDATE auth_mail_outbox SET next_attempt_at=now() WHERE recipient=%s", (email,))
        assert deliver_one(db, sent.append)
        assert len(sent) == 1
        assert f"/auth#password-reset={token}" in sent[0].get_content()
        row = db.execute("SELECT sent_at,encrypted_token,attempts,recipient FROM auth_mail_outbox WHERE id=%s", (mail_id,)).fetchone()
        assert row["sent_at"] and row["encrypted_token"] is None and row["attempts"] == 2 and row["recipient"] == ""
        assert not deliver_one(db, sent.append)
    assert client.post("/auth/password-reset/request", json={"email": email}, headers=headers).status_code == 202
    with psycopg.connect(owner, row_factory=dict_row) as db:
        db.execute("UPDATE auth_mail_outbox SET expires_at=now()-interval '1 second' WHERE recipient=%s", (email,))
        db.execute("SET LOCAL ROLE maaher_mailer")
        assert not deliver_one(db, sent.append)
        assert db.execute("SELECT count(*) AS n FROM auth_mail_outbox WHERE encrypted_token IS NOT NULL").fetchone()["n"] == 0


def test_auth_events_and_factors_are_private_and_audit_append_only(identity):
    import psycopg
    from app.database import transaction, user_context
    client, owner, user, _, foreign, email, password = identity
    assert sign_in(client, email, password).status_code == 200
    enroll_mfa(client, password)
    with psycopg.connect(owner) as db:
        other = db.execute("SELECT user_id FROM memberships WHERE tenant_id=%s", (foreign,)).fetchone()[0]
        db.execute("INSERT INTO auth_events(id,user_id,action) VALUES (%s,%s,'login.succeeded')", (uuid4(), other))
    # The tenant role now has no access at all to auth history/factor secrets.
    for table in ('auth_events','mfa_factors'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with transaction() as db:
                db.execute(f'SELECT * FROM {table}')
    from app.database import auth_transaction
    with auth_transaction() as db:
        assert db.execute('SELECT * FROM auth_events').fetchall()==[]
        assert db.execute('SELECT * FROM mfa_factors').fetchall()==[]
        user_context(db,user)
        assert db.execute('SELECT * FROM auth_events WHERE user_id=%s',(other,)).fetchall()==[]
        factor=db.execute('SELECT * FROM mfa_factors').fetchone()
        assert factor['user_id']==user and factor['confirmed']
    for query in ("DELETE FROM auth_events", "UPDATE auth_events SET action='logout'", "UPDATE users SET password_hash='bad'"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with transaction() as db:
                user_context(db, user)
                session_context(db, token_digest(client.cookies.get("maaher_session", "")))
                db.execute(query)


def test_missing_encryption_config_fails_closed_without_sending(identity, monkeypatch):
    client, owner, _, _, _, email, password = identity
    assert sign_in(client, email, password).status_code == 200
    monkeypatch.delenv("AUTH_ENCRYPTION_KEY")
    headers = {"origin": "https://testserver"}
    assert client.post("/auth/password-reset/request", json={"email": email}, headers=headers).status_code == 503
    assert client.post("/auth/mfa/enroll", json={"password": password}, headers=headers).status_code == 503


def test_mfa_new_session_verification_and_replay_are_serialized(identity):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timezone
    from fastapi.testclient import TestClient
    from app.main import app
    client, _, _, _, _, email, password = identity
    headers, totp = make_admin(identity)
    # Use the next allowed counter so the enrollment code is never reused.
    code = totp.at((totp.timecode(datetime.now(timezone.utc))+1)*totp.interval)
    def verify(_):
        with TestClient(app, base_url="https://testserver") as independent:
            assert sign_in(independent, email, password).status_code == 200
            response = independent.post("/auth/mfa/verify", json={"code": code}, headers=headers)
            if response.status_code == 200:
                assert independent.get("/auth/me", headers=headers).status_code == 200
            else:
                assert independent.get("/auth/me", headers=headers).status_code == 403
            return response.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(verify, range(2))) == [200, 400]


def test_password_reset_concurrent_confirm_has_one_winner(identity):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi.testclient import TestClient
    from app.main import app
    client, owner, _, _, _, email, password = identity
    headers = {"origin": "https://testserver"}
    assert client.post("/auth/password-reset/request", json={"email": email}, headers=headers).status_code == 202
    token = mail_token(owner, email, "password-reset")
    def confirm(_):
        with TestClient(app, base_url="https://testserver") as independent:
            return independent.post("/auth/password-reset/confirm", json={"token": token, "password": password}, headers=headers).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(confirm, range(2))) == [200, 400]


def test_mail_worker_rejects_owner_and_api_credentials(identity):
    import psycopg
    from psycopg.rows import dict_row
    from app.database import transaction
    from app.mail_worker import validate_mail_role
    with psycopg.connect(identity[1], row_factory=dict_row) as db:
        with pytest.raises(RuntimeError, match="role khusus email"):
            validate_mail_role(db)
    with transaction() as db:
        with pytest.raises(RuntimeError, match="role khusus email"):
            validate_mail_role(db)
