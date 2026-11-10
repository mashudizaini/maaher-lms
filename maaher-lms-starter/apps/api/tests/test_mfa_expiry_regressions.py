"""Regression cases for MFA setup that expires before it is completed."""
import time

import psycopg
import pyotp

from auth_helpers import authorize_mfa, enroll_mfa, sign_in
from app.security import token_digest


ORIGIN = {"origin": "https://testserver"}


def test_expired_operator_request_can_be_renewed_on_the_same_session(identity):
    client, owner, user, _, _, email, password = identity
    assert sign_in(client, email, password).status_code == 200
    first_grant = authorize_mfa(client)
    with psycopg.connect(owner) as db:
        first_id = db.execute(
            "UPDATE mfa_requests SET expires_at=now()-interval '1 second' "
            "WHERE user_id=%s RETURNING id", (user,)
        ).fetchone()[0]
    renewed = client.post("/auth/mfa/request", json={"purpose": "bootstrap"}, headers=ORIGIN)
    assert renewed.status_code == 200
    assert renewed.json()["request_id"] != str(first_id)
    # A replacement request must not make the old approval usable again.
    assert client.post("/auth/mfa/enroll", json={
        "password": password, "authorization": first_grant,
    }, headers=ORIGIN).status_code == 403
    replacement_grant = authorize_mfa(client)
    response = client.post("/auth/mfa/enroll", json={
        "password": password, "authorization": replacement_grant,
    }, headers=ORIGIN)
    assert response.status_code == 200
    factor = pyotp.parse_uri(response.json()["provisioning_uri"])
    assert client.post("/auth/mfa/verify", json={"code": factor.now()}, headers=ORIGIN).status_code == 200
    with psycopg.connect(owner) as db:
        # Expiring a request must not erase the independent approval audit.
        assert db.execute("SELECT count(*) FROM mfa_operator_audit WHERE user_id=%s", (user,)).fetchone()[0] == 2


def test_unexpired_request_retries_preserve_id_and_one_use_approval(identity):
    client, _, _, _, _, email, password = identity
    assert sign_in(client, email, password).status_code == 200
    first = client.post("/auth/mfa/request", json={"purpose": "bootstrap"}, headers=ORIGIN)
    grant = authorize_mfa(client)
    repeated = client.post("/auth/mfa/request", json={"purpose": "bootstrap"}, headers=ORIGIN)
    assert first.status_code == repeated.status_code == 200
    assert first.json()["request_id"] == repeated.json()["request_id"]
    payload = {"password": password, "authorization": grant}
    assert client.post("/auth/mfa/enroll", json=payload, headers=ORIGIN).status_code == 200
    assert client.post("/auth/mfa/enroll", json=payload, headers=ORIGIN).status_code == 403


def test_expired_recovery_setup_does_not_block_the_active_authenticator(identity):
    client, owner, user, tenant, _, email, password = identity
    assert sign_in(client, email, password).status_code == 200
    active = enroll_mfa(client, password)
    assert sign_in(client, email, password).status_code == 200
    grant = authorize_mfa(client, "recovery")
    response = client.post("/auth/mfa/enroll", json={
        "password": password, "authorization": grant,
        "new_password": "Never committed recovery password 123!",
    }, headers=ORIGIN)
    assert response.status_code == 200
    with psycopg.connect(owner) as db:
        old_factor = db.execute("SELECT encrypted_secret FROM mfa_factors WHERE user_id=%s", (user,)).fetchone()[0]
        db.execute("UPDATE mfa_enrollments SET expires_at=now()-interval '1 second' WHERE user_id=%s", (user,))
    # The next accepted TOTP step avoids replaying the enrollment confirmation.
    verified = client.post("/auth/mfa/verify", json={"code": active.at(time.time() + 30)}, headers=ORIGIN)
    assert verified.status_code == 200, verified.text
    assert client.get("/auth/me", headers={"x-tenant-id": str(tenant)}).status_code == 200
    with psycopg.connect(owner) as db:
        assert db.execute("SELECT encrypted_secret FROM mfa_factors WHERE user_id=%s", (user,)).fetchone()[0] == old_factor
        assert db.execute("SELECT count(*) FROM mfa_enrollments WHERE user_id=%s", (user,)).fetchone()[0] == 0
    assert sign_in(client, email, password).status_code == 200


def test_expired_pending_factor_cannot_complete_bootstrap(identity):
    client, owner, user, _, _, email, password = identity
    assert sign_in(client, email, password).status_code == 200
    grant = authorize_mfa(client)
    response = client.post("/auth/mfa/enroll", json={
        "password": password, "authorization": grant,
    }, headers=ORIGIN)
    assert response.status_code == 200
    pending = pyotp.parse_uri(response.json()["provisioning_uri"])
    digest = token_digest(client.cookies.get("maaher_session"))
    with psycopg.connect(owner) as db:
        db.execute("UPDATE mfa_enrollments SET expires_at=now()-interval '1 second' WHERE session_hash=%s", (digest,))
    assert client.post("/auth/mfa/verify", json={"code": pending.now()}, headers=ORIGIN).status_code == 400
    with psycopg.connect(owner) as db:
        assert db.execute("SELECT count(*) FROM mfa_factors WHERE user_id=%s", (user,)).fetchone()[0] == 0
        assert db.execute("SELECT mfa_verified FROM sessions WHERE token_hash=%s", (digest,)).fetchone()[0] is False
