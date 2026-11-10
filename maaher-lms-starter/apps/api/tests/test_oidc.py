"""Exercise real Authlib/JWKS/RS256 verification against an in-memory HTTPS IdP."""
import json
import os
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.jwk import RSAKey, OctKey
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from app import oidc
from app.auth_support import cipher
from app.database import transaction
from app.main import app
from app.security import new_token, token_digest
from auth_helpers import sign_in

ORIGIN = {"origin": "https://testserver"}
ISSUER = "https://maaher-tests.us.auth0.com/"
SUBJECT = "auth0|verified-synthetic-staff"
CLIENT = "synthetic-client-id"
SECRET = "synthetic-client-secret-not-a-real-credential-12345"


@pytest.fixture(scope="session")
def provider_key():
    return RSAKey.generate_key(2048, parameters={"kid": "synthetic-provider-key"})


@pytest.fixture
def provider(identity, monkeypatch, provider_key):
    monkeypatch.setenv("AUTH0_DOMAIN", "maaher-tests.us.auth0.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID", CLIENT)
    monkeypatch.setenv("AUTH0_CLIENT_SECRET", SECRET)
    codes, calls = {}, []

    def handle(request):
        calls.append((request.method, str(request.url)))
        assert str(request.url).startswith(ISSUER)
        if request.url.path == "/.well-known/jwks.json":
            return httpx.Response(200, json={"keys": [provider_key.as_dict(private=False)]})
        assert request.method == "POST" and request.url.path == "/oauth/token"
        assert request.headers["authorization"].startswith("Basic ")
        form = parse_qs(request.content.decode())
        assert form["grant_type"] == ["authorization_code"]
        assert form["redirect_uri"] == [os.environ["APP_ORIGIN"] + "/api/auth/oidc/callback"]
        spec = codes.pop(form["code"][0])
        assert create_s256_code_challenge(form["code_verifier"][0]) == spec["challenge"]
        if spec.get("error"):
            return httpx.Response(400, json={"error": "invalid_grant", "error_description": "private provider diagnostic"})
        now = int(time.time())
        claims = {"iss": ISSUER, "sub": SUBJECT + '-' + str(identity[2]), "aud": CLIENT, "iat": now, "exp": now + 300,
                  "nonce": spec["nonce"], "auth_time": now, "amr": ["pwd", "mfa"],
                  oidc.ASSURANCE_CLAIM: oidc.ASSURANCE}
        claims.update(spec.get("claims", {}))
        for key in spec.get("omit", []):
            claims.pop(key)
        alg = spec.get("alg", "RS256")
        signing = OctKey.import_key(SECRET.encode()) if alg == "HS256" else spec.get("key", provider_key)
        encoded = jwt.encode({"alg": alg, "kid": signing.kid}, claims, signing)
        return httpx.Response(200, json={"access_token": "synthetic-access-token-never-persisted",
                                        "token_type": "Bearer", "expires_in": 300, "id_token": encoded})

    original = oidc.make_client

    def make(config):
        client = original(config)
        client.client_kwargs.update(transport=httpx.MockTransport(handle), trust_env=False)
        return client

    monkeypatch.setattr(oidc, "make_client", make)
    return {"codes": codes, "calls": calls}


def bind(identity, subject=None, operator=False, admin=True):
    owner, user, tenant = identity[1:4]
    subject = subject if subject is not None else SUBJECT + '-' + str(user)
    identifier = uuid4()
    with psycopg.connect(owner) as db:
        if admin:
            db.execute("UPDATE memberships SET role='admin' WHERE user_id=%s AND tenant_id=%s", (user, tenant))
        db.execute("""INSERT INTO oidc_identities(id,user_id,issuer,subject,is_operator,provision_reference)
                      VALUES(%s,%s,%s,%s,%s,'synthetic-supervised-key-verification')""",
                   (identifier, user, ISSUER, subject, operator))
    return identifier


def begin(client, provider, **spec):
    response = client.post("/auth/oidc/login", json={}, headers={"origin": os.environ["APP_ORIGIN"]})
    assert response.status_code == 200, response.text
    query = parse_qs(urlsplit(response.json()["authorization_url"]).query)
    assert query["response_type"] == ["code"] and query["scope"] == ["openid"]
    assert query["code_challenge_method"] == ["S256"] and query["prompt"] == ["login"]
    assert query["max_age"] == ["0"]
    assert SECRET not in response.text
    code = new_token()
    provider["codes"][code] = {"nonce": query["nonce"][0], "challenge": query["code_challenge"][0], **spec}
    return {"state": query["state"][0], "code": code}


def test_oidc_rotates_into_a_private_session_and_keeps_tenant_authorization(identity, provider):
    client, owner, user, tenant, foreign = identity[:5]
    assert sign_in(client, identity[5], identity[6]).status_code == 200
    bind(identity)
    flow = begin(client, provider)
    with psycopg.connect(owner) as db:
        encrypted = db.execute("SELECT encrypted_state FROM oidc_login_flows").fetchone()[0]
        assert flow["state"] not in encrypted
        state = json.loads(cipher().decrypt(encrypted.encode()))
        assert "code_verifier" in next(iter(state.values()))["data"]
    old_cookie = client.cookies.get("maaher_session")
    response = client.get("/auth/oidc/callback", params=flow)
    assert response.status_code == 200, response.text
    cookie = client.cookies.get("maaher_session")
    assert cookie and cookie != old_cookie and "." not in cookie
    assert all(value in response.headers["set-cookie"].lower() for value in ("httponly", "secure", "samesite=lax"))
    assert client.get("/auth/me", headers={"x-tenant-id": str(tenant)}).json()["role"] == "admin"
    assert client.get("/auth/me", headers={"x-tenant-id": str(foreign)}).status_code == 403
    assert client.get("/auth/tenant-members", headers={"x-tenant-id": str(tenant)}).status_code == 200
    assert client.get("/auth/oidc/session").json()["provider"] == "auth0"
    with psycopg.connect(owner) as db:
        assert db.execute("SELECT count(*) FROM oidc_login_flows").fetchone()[0] == 0
        assert db.execute("SELECT user_id,mfa_verified FROM sessions WHERE token_hash=%s", (token_digest(cookie),)).fetchone() == (user, True)
    assert client.get("/auth/oidc/callback", params=flow).status_code == 400


@pytest.mark.parametrize("spec", [
    {"claims": {"iss": "https://other.us.auth0.com/"}},
    {"claims": {"aud": "another-client"}},
    {"claims": {"azp": "another-client"}},
    {"claims": {"nonce": "another-flow"}},
    {"claims": {"exp": 1}},
    {"claims": {"iat": 9999999999}},
    {"claims": {"auth_time": 1}},
    {"claims": {"auth_time": 9999999999}},
    {"claims": {"auth_time": True}},
    {"claims": {"amr": ["pwd"]}},
    {"claims": {oidc.ASSURANCE_CLAIM: "otp-is-not-the-security-key-policy"}},
    {"claims": {oidc.ASSURANCE_CLAIM: oidc.DEV_TOTP_ASSURANCE}},
    {"omit": [oidc.ASSURANCE_CLAIM]},
    {"omit": ["nonce"]},
    {"omit": ["auth_time"]},
    {"omit": ["sub"]},
    {"omit": ["aud"]},
    {"alg": "HS256"},
    {"alg": "RS512"},
    {"error": True},
])
def test_oidc_rejects_invalid_tokens_without_issuing_a_session(identity, provider, spec):
    client, owner = identity[:2]
    bind(identity)
    response = client.get("/auth/oidc/callback", params=begin(client, provider, **spec))
    assert response.status_code == 400, response.text
    assert not client.cookies.get("maaher_session")
    assert "private provider diagnostic" not in response.text
    with psycopg.connect(owner) as db:
        assert db.execute("SELECT count(*) FROM sessions WHERE user_id=%s", (identity[2],)).fetchone()[0] == 0


def test_oidc_rejects_a_signature_from_an_untrusted_key(identity, provider):
    bind(identity)
    rogue = RSAKey.generate_key(2048, parameters={"kid": "untrusted-key"})
    response = identity[0].get("/auth/oidc/callback", params=begin(identity[0], provider, key=rogue))
    assert response.status_code == 400


def test_same_email_never_links_an_unregistered_provider_subject(identity, provider):
    bind(identity, subject="auth0|different-subject")
    response = identity[0].get("/auth/oidc/callback", params=begin(identity[0], provider, claims={"email": identity[5], "email_verified": True}))
    assert response.status_code == 400
    assert not identity[0].cookies.get("maaher_session")


def test_prebound_staff_can_login_without_the_local_password_or_email(identity, provider):
    from app.auth import passwords
    bind(identity)
    client, owner, user, tenant = identity[:4]
    with psycopg.connect(owner) as db:
        db.execute("UPDATE users SET email=%s,password_hash=%s WHERE id=%s",
                   (f'{uuid4()}@no-inbox.example.invalid', passwords.hash(new_token()), user))
    assert sign_in(client, identity[5], identity[6]).status_code == 401
    response = client.get('/auth/oidc/callback', params=begin(client, provider, claims={'email': identity[5]}))
    assert response.status_code == 200
    assert client.get('/auth/me', headers={'x-tenant-id': str(tenant)}).json()['user_id'] == str(user)


def test_flow_is_bound_to_browser_and_invalid_attempt_does_not_consume_it(identity, provider):
    client = identity[0]; bind(identity)
    params = begin(client, provider)
    with TestClient(app, base_url="https://testserver") as other:
        assert other.get("/auth/oidc/callback", params=params).status_code == 400
    assert not provider["calls"]
    assert client.get("/auth/oidc/callback", params=params).status_code == 200


@pytest.mark.parametrize("tamper", ["expired", "config", "encrypted", "state", "duplicate", "issuer"])
def test_flow_tampering_fails_before_exchange(identity, provider, monkeypatch, tamper):
    client, owner = identity[:2]; bind(identity)
    params = begin(client, provider)
    if tamper == "config": monkeypatch.setenv("AUTH0_CLIENT_ID", "changed-client")
    elif tamper == "state": params["state"] = new_token()
    elif tamper == "issuer": params["iss"] = "https://other.us.auth0.com/"
    elif tamper in {"expired", "encrypted"}:
        with psycopg.connect(owner) as db:
            if tamper == "expired": db.execute("UPDATE oidc_login_flows SET expires_at=now()-interval '1 second'")
            else: db.execute("UPDATE oidc_login_flows SET encrypted_state='invalid-ciphertext'")
    if tamper == "duplicate": params = [("state", params["state"]), ("state", params["state"]), ("code", params["code"])]
    response = client.get("/auth/oidc/callback", params=params)
    assert response.status_code == 400 and not provider["calls"]


def test_bound_and_revoked_staff_have_no_password_or_reset_fallback(identity, provider):
    client, owner, user, tenant, _, email, password = identity
    assert sign_in(client, email, password).status_code == 200
    local = client.cookies.get("maaher_session")
    assert client.post("/auth/password-reset/request", json={"email": email}, headers=ORIGIN).status_code == 202
    with psycopg.connect(owner) as db:
        old_reset = db.execute("SELECT token_hash FROM password_resets WHERE user_id=%s", (user,)).fetchone()[0]
    identifier = bind(identity)
    assert client.get("/auth/me", headers={"x-tenant-id": str(tenant)}).status_code == 401
    assert sign_in(client, email, password).status_code == 401
    response = client.get("/auth/oidc/callback", params=begin(client, provider))
    assert response.status_code == 200
    # A reset issued before binding must not revoke the new staff session.
    with psycopg.connect(os.environ["TEST_AUTH_DATABASE_URL"]) as db:
        assert db.execute("SELECT reset_password(%s,'should-not-be-written')", (old_reset,)).fetchone()[0] is False
    with psycopg.connect(owner) as db:
        db.execute("DELETE FROM auth_mail_outbox WHERE recipient=%s", (email,))
    assert client.post("/auth/password-reset/request", json={"email": email}, headers=ORIGIN).status_code == 202
    with psycopg.connect(owner) as db:
        assert db.execute("SELECT count(*) FROM auth_mail_outbox WHERE recipient=%s", (email,)).fetchone()[0] == 0
        db.execute("UPDATE oidc_identities SET status='revoked' WHERE id=%s", (identifier,))
    assert client.get("/auth/me", headers={"x-tenant-id": str(tenant)}).status_code == 401
    assert sign_in(client, email, password).status_code == 401
    client.cookies.set("maaher_session", local)
    assert client.get("/auth/me", headers={"x-tenant-id": str(tenant)}).status_code == 401


def test_operator_marker_does_not_grant_tenant_admin_or_local_mfa_changes(identity, provider):
    client, _, _, tenant = identity[:4]
    bind(identity, operator=True, admin=False)
    assert client.get("/auth/oidc/callback", params=begin(client, provider)).json()["is_operator"] is True
    assert client.get("/auth/oidc/session").json()["is_operator"] is True
    assert client.get("/auth/audit", headers={"x-tenant-id": str(tenant)}).status_code == 403
    for path, payload in [("request", {"purpose": "recovery"}), ("enroll", {"password": identity[6]}), ("verify", {"code": "123456"})]:
        assert client.post("/auth/mfa/" + path, json=payload, headers=ORIGIN).status_code == 403


def test_membership_revocation_is_checked_after_oidc_login(identity, provider):
    bind(identity)
    client, owner, user, tenant = identity[:4]
    assert client.get("/auth/oidc/callback", params=begin(client, provider)).status_code == 200
    with psycopg.connect(owner) as db: db.execute("UPDATE memberships SET status='revoked' WHERE user_id=%s", (user,))
    assert client.get("/auth/me", headers={"x-tenant-id": str(tenant)}).status_code == 403


def test_disabling_the_bound_user_revokes_existing_oidc_access(identity, provider):
    bind(identity)
    client, owner, user, tenant = identity[:4]
    assert client.get("/auth/oidc/callback", params=begin(client, provider)).status_code == 200
    with psycopg.connect(owner) as db: db.execute("UPDATE users SET status='disabled' WHERE id=%s", (user,))
    assert client.get("/auth/me", headers={"x-tenant-id": str(tenant)}).status_code == 401


@pytest.mark.parametrize("table", ["oidc_identities", "oidc_sessions", "oidc_login_flows"])
def test_tenant_runtime_cannot_read_oidc_material(identity, table):
    with transaction() as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("SELECT * FROM " + table)


def test_runtime_cannot_mint_oidc_sessions_and_auth_cannot_bind_a_subject(identity):
    with transaction() as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("INSERT INTO oidc_sessions(token_hash,identity_id,authenticated_at,assurance) VALUES('forged',gen_random_uuid(),now(),'maaher-fido2-uv-v1')")
    with psycopg.connect(os.environ['TEST_AUTH_DATABASE_URL']) as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute("INSERT INTO oidc_identities(id,user_id,issuer,subject,provision_reference) VALUES(gen_random_uuid(),gen_random_uuid(),'https://example.us.auth0.com/','forged','forged-reference')")
    with psycopg.connect(identity[1]) as db:
        assert db.execute("SELECT has_column_privilege('maaher_definer','oidc_login_flows','expires_at','SELECT')").fetchone()[0] is True
        assert db.execute("SELECT has_column_privilege('maaher_definer','oidc_login_flows','encrypted_state','SELECT')").fetchone()[0] is False


def use_dev_totp(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_ORIGIN", "http://127.0.0.1:3000")
    monkeypatch.setenv("LOCAL_INSECURE_COOKIES", "true")
    monkeypatch.setenv("AUTH0_ASSURANCE_PROFILE", "dev-totp")


def test_dev_totp_uses_a_distinct_session_and_checks_tenant_and_policy_on_every_request(identity, provider, monkeypatch):
    use_dev_totp(monkeypatch)
    bind(identity)
    _, owner, user, tenant, foreign = identity[:5]
    with TestClient(app, base_url=os.environ["APP_ORIGIN"]) as client:
        assert client.get("/auth/oidc/config").json()["assurance"] == oidc.DEV_TOTP_ASSURANCE
        flow = begin(client, provider, claims={oidc.ASSURANCE_CLAIM: oidc.DEV_TOTP_ASSURANCE})
        assert client.get("/auth/oidc/callback", params=flow).status_code == 200
        opaque = client.cookies.get("maaher_session")
        assert client.get("/auth/me", headers={"x-tenant-id": str(tenant)}).json()["role"] == "admin"
        assert client.get("/auth/tenant-members", headers={"x-tenant-id": str(tenant)}).status_code == 200
        assert client.get("/auth/me", headers={"x-tenant-id": str(foreign)}).status_code == 403
        with psycopg.connect(owner) as db:
            assert db.execute("SELECT assurance FROM oidc_sessions WHERE token_hash=%s", (token_digest(opaque),)).fetchone()[0] == oidc.DEV_TOTP_ASSURANCE
        # Direct SQL defaults to FIDO2 and does not inherit app's dev profile.
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as db:
            assert db.execute("SELECT * FROM resolve_session(%s)", (token_digest(opaque),)).fetchone() is None
            assert db.execute("SELECT count(*) FROM list_members(%s,%s,NULL)", (token_digest(opaque), tenant)).fetchone() == (0,)
        monkeypatch.setenv("AUTH0_ASSURANCE_PROFILE", "fido2")
        assert client.get("/auth/me", headers={"x-tenant-id": str(tenant)}).status_code == 401
        monkeypatch.setenv("APP_ENV", "production")
        assert client.get("/auth/oidc/session").status_code == 401
        monkeypatch.setenv("AUTH0_ASSURANCE_PROFILE", "dev-totp")
        assert client.get("/auth/oidc/config").json() == {"enabled": False}
        assert client.post("/auth/oidc/login", headers={"origin": os.environ["APP_ORIGIN"]}).status_code == 503
        assert client.get("/auth/oidc/session").status_code == 401
        # A request cannot re-enable the dev policy using a header/query value.
        assert client.get("/auth/me?AUTH0_ASSURANCE_PROFILE=dev-totp", headers={"x-tenant-id": str(tenant), "app-env": "local"}).status_code == 401


def test_dev_profile_rejects_a_fido2_claim_and_a_policy_change_invalidates_inflight_state(identity, provider, monkeypatch):
    bind(identity)
    use_dev_totp(monkeypatch)
    with TestClient(app, base_url=os.environ["APP_ORIGIN"]) as client:
        assert client.get("/auth/oidc/callback", params=begin(client, provider)).status_code == 400
        flow = begin(client, provider, claims={oidc.ASSURANCE_CLAIM: oidc.DEV_TOTP_ASSURANCE})
        before = len(provider["calls"])
        monkeypatch.setenv("AUTH0_ASSURANCE_PROFILE", "fido2")
        assert client.get("/auth/oidc/callback", params=flow).status_code == 400
        assert len(provider["calls"]) == before
        assert not client.cookies.get("maaher_session")


def test_dev_profile_rejects_an_actual_non_test_database(identity, provider, monkeypatch):
    from fastapi import HTTPException
    from psycopg.conninfo import make_conninfo
    from psycopg.rows import dict_row
    use_dev_totp(monkeypatch)
    config = oidc.settings()
    assert config.assurance == oidc.DEV_TOTP_ASSURANCE
    # Read only the actual DB name, with no schema/data writes to this database.
    with psycopg.connect(make_conninfo(identity[1], dbname="postgres"), row_factory=dict_row,
                         options="-c default_transaction_read_only=on") as db:
        with pytest.raises(HTTPException) as denied:
            oidc.require_policy_database(config, db)
        assert denied.value.status_code == 503


def test_offline_binding_revokes_local_sessions_and_cannot_reassign_a_subject(identity, provider):
    from app.oidc_provision import bind_identity
    client, owner, user, tenant, foreign, email, password = identity
    assert sign_in(client, email, password).status_code == 200
    with psycopg.connect(owner) as db:
        db.execute("UPDATE memberships SET role='admin' WHERE user_id=%s", (user,))
        subject = SUBJECT + '-' + str(user)
        identifier = bind_identity(db,user,ISSUER,subject,False,'synthetic-supervised-binding')
    assert client.get('/auth/me',headers={'x-tenant-id':str(tenant)}).status_code == 401
    with psycopg.connect(owner) as db:
        assert db.execute('SELECT count(*) FROM sessions WHERE user_id=%s',(user,)).fetchone()[0] == 0
        other = db.execute('SELECT user_id FROM memberships WHERE tenant_id=%s',(foreign,)).fetchone()[0]
    with pytest.raises(psycopg.errors.UniqueViolation), psycopg.connect(owner) as db:
        bind_identity(db,other,ISSUER,subject,True,'synthetic-attempted-reassignment')
    with psycopg.connect(owner) as db:
        assert db.execute('SELECT user_id FROM oidc_identities WHERE id=%s',(identifier,)).fetchone()[0] == user


def test_oidc_start_requires_origin_and_never_accepts_a_return_url(identity, provider):
    client = identity[0]
    assert client.post("/auth/oidc/login", json={}).status_code == 403
    response = client.post("/auth/oidc/login", json={"return_to": "https://evil.invalid"}, headers=ORIGIN)
    assert response.status_code == 200 and "evil.invalid" not in response.text


def test_missing_provider_configuration_is_explicit(identity, monkeypatch):
    for key in ("AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET"): monkeypatch.delenv(key, raising=False)
    client = identity[0]
    assert client.get("/auth/oidc/config").json() == {"enabled": False}
    assert client.post("/auth/oidc/login", json={}, headers=ORIGIN).status_code == 503


@pytest.mark.parametrize("domain", ["https://demo.us.auth0.com", "demo.auth0.com.evil.invalid", "localhost", "demo..auth0.com", "demo.auth0.com:443"])
def test_invalid_auth0_domain_cannot_be_used_as_a_network_destination(identity, provider, monkeypatch, domain):
    monkeypatch.setenv("AUTH0_DOMAIN", domain)
    assert identity[0].post("/auth/oidc/login", json={}, headers=ORIGIN).status_code == 503
    assert not provider["calls"]


@pytest.mark.parametrize('origin', ['http://production.example', 'https://example.invalid/path',
                                  'https://example.invalid:invalid', 'https://[broken',
                                  'https://user:synthetic@example.invalid'])
def test_unsafe_callback_origin_is_not_configured(identity, provider, monkeypatch, origin):
    from fastapi import HTTPException
    monkeypatch.setenv('APP_ENV','production'); monkeypatch.setenv('APP_ORIGIN',origin)
    with pytest.raises(HTTPException) as failure: oidc.settings()
    assert failure.value.status_code == 503


def test_http_callback_is_only_available_for_explicit_local_loopback(identity, provider, monkeypatch):
    monkeypatch.setenv('APP_ENV','local'); monkeypatch.setenv('APP_ORIGIN','http://127.0.0.1:3000')
    assert oidc.settings().callback == 'http://127.0.0.1:3000/api/auth/oidc/callback'
