import os
from pathlib import Path
from uuid import uuid4
import pytest


@pytest.fixture(scope="session")
def database():
    required=('TEST_MIGRATION_DATABASE_URL','TEST_DATABASE_URL','TEST_AUTH_DATABASE_URL','TEST_OPERATOR_DATABASE_URL')
    if not all(os.environ.get(key) for key in required):
        pytest.skip('Requires separate disposable owner/runtime/auth/operator URLs')
    import psycopg
    from alembic import command
    from alembic.config import Config
    from psycopg.rows import dict_row

    owner_url = os.environ["TEST_MIGRATION_DATABASE_URL"]
    with psycopg.connect(owner_url, row_factory=dict_row) as db:
        name = db.execute("SELECT current_database() AS name").fetchone()["name"]
        assert name.startswith("maaher_test_"), "Refusing non-test database"
        assert db.execute("SELECT to_regclass('public.users') AS t").fetchone()["t"] is None
    with psycopg.connect(os.environ["TEST_DATABASE_URL"], row_factory=dict_row) as db:
        runtime_name = db.execute("SELECT current_database() AS name").fetchone()["name"]
        assert runtime_name == name and runtime_name.startswith("maaher_test_"), "Runtime URL must use the test DB"
    previous = os.environ.get("MIGRATION_DATABASE_URL")
    os.environ["MIGRATION_DATABASE_URL"] = owner_url
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    try:
        # Upgrade an existing stage-1 account/session without losing its data.
        command.upgrade(config, "0001_identity")
        legacy_user, legacy_tenant = uuid4(), uuid4()
        with psycopg.connect(owner_url) as db:
            db.execute("INSERT INTO users(id,email,password_hash) VALUES (%s,%s,'legacy-hash')",
                       (legacy_user, f"{legacy_user}@example.invalid"))
            db.execute("INSERT INTO tenants(id,slug,name) VALUES (%s,%s,'Legacy')", (legacy_tenant, str(legacy_tenant)))
            db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES (%s,%s,%s,'student')",
                       (uuid4(), legacy_tenant, legacy_user))
            db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES ('legacy-token-hash',%s,now()+interval '1 hour')", (legacy_user,))
        command.upgrade(config, "head")
        command.downgrade(config, "0005_dev_totp")
        with psycopg.connect(owner_url) as db:
            for table in ("courses", "courses_teachers", "course_modules", "course_lessons"):
                assert db.execute("SELECT to_regclass(%s)", ("public." + table,)).fetchone()[0] is None
            assert db.execute("SELECT password_hash FROM users WHERE id=%s", (legacy_user,)).fetchone()[0] == 'legacy-hash'
        command.upgrade(config, "head")
        with psycopg.connect(owner_url) as db:
            assert db.execute("SELECT password_hash FROM users WHERE id=%s", (legacy_user,)).fetchone()[0] == 'legacy-hash'
            assert db.execute("SELECT mfa_verified FROM sessions WHERE user_id=%s", (legacy_user,)).fetchone()[0] is False
            assert db.execute("SELECT role FROM memberships WHERE user_id=%s AND tenant_id=%s", (legacy_user, legacy_tenant)).fetchone()[0] == 'student'
            external_user, external_identity = uuid4(), uuid4()
            db.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,'external-fixture-hash')",
                       (external_user,f'{external_user}@example.invalid'))
            db.execute("INSERT INTO oidc_identities(id,user_id,issuer,subject,provision_reference) VALUES(%s,%s,'https://fixture.us.auth0.com/','fixture-subject','synthetic-fixture-reference')",
                       (external_identity,external_user))
            db.execute("INSERT INTO sessions(token_hash,user_id,expires_at,mfa_verified) VALUES('oidc-downgrade-fixture',%s,now()+interval '1 hour',true)", (external_user,))
            db.execute("INSERT INTO oidc_sessions(token_hash,identity_id,authenticated_at,assurance) VALUES('oidc-downgrade-fixture',%s,now(),'maaher-fido2-uv-v1')", (external_identity,))
            db.execute("INSERT INTO sessions(token_hash,user_id,expires_at,mfa_verified) VALUES('dev-downgrade-fixture',%s,now()+interval '1 hour',true)", (external_user,))
            db.execute("INSERT INTO oidc_sessions(token_hash,identity_id,authenticated_at,assurance) VALUES('dev-downgrade-fixture',%s,now(),'maaher-dev-totp-v1')", (external_identity,))
        command.downgrade(config, "0004_auth0_oidc")
        with psycopg.connect(owner_url) as db:
            assert db.execute("SELECT 1 FROM sessions WHERE token_hash='dev-downgrade-fixture'").fetchone() is None
            assert db.execute("SELECT 1 FROM sessions WHERE token_hash='oidc-downgrade-fixture'").fetchone() == (1,)
            assert db.execute("SELECT password_hash FROM users WHERE id=%s", (external_user,)).fetchone()[0] == 'external-fixture-hash'
        command.upgrade(config, "head")
        command.downgrade(config, "0003_security_review")
        with psycopg.connect(owner_url) as db:
            for table in ("oidc_identities", "oidc_login_flows", "oidc_sessions"):
                assert db.execute("SELECT to_regclass(%s)", ("public." + table,)).fetchone()[0] is None
            assert db.execute("SELECT password_hash FROM users WHERE id=%s", (legacy_user,)).fetchone()[0] == 'legacy-hash'
            assert db.execute("SELECT token_hash FROM sessions WHERE token_hash='oidc-downgrade-fixture'").fetchone() is None
            assert db.execute("SELECT password_hash FROM users WHERE id=%s", (external_user,)).fetchone()[0] == 'external-fixture-hash'
        command.upgrade(config, "head")
        command.downgrade(config, "0002_auth_lifecycle")
        with psycopg.connect(owner_url) as db:
            assert db.execute("SELECT to_regclass('public.mfa_requests')").fetchone()[0] is None
            assert db.execute("SELECT password_hash FROM users WHERE id=%s", (legacy_user,)).fetchone()[0] == 'legacy-hash'
        command.upgrade(config, "head")
        command.downgrade(config, "0001_identity")
        with psycopg.connect(owner_url) as db:
            assert db.execute("SELECT password_hash FROM users WHERE id=%s", (legacy_user,)).fetchone()[0] == 'legacy-hash'
            assert db.execute("SELECT token_hash FROM sessions WHERE user_id=%s", (legacy_user,)).fetchone()[0] == 'legacy-token-hash'
            assert db.execute("SELECT to_regclass('public.invitations')").fetchone()[0] is None
        command.upgrade(config, "head")
        # Verify reversibility before creating any test records.
        command.downgrade(config, "base")
        with psycopg.connect(owner_url) as db:
            for table in ("users", "tenants", "memberships", "sessions", "login_attempts", "audit_events",
                          "invitations", "password_resets", "mfa_factors", "auth_events", "auth_mail_outbox",
                          "mfa_requests", "mfa_enrollments", "auth_rate_buckets", "mfa_operator_audit",
                          "oidc_identities", "oidc_login_flows", "oidc_sessions",
                          "courses", "courses_teachers", "course_modules", "course_lessons"):
                assert db.execute("SELECT to_regclass(%s)", (f"public.{table}",)).fetchone()[0] is None
        command.upgrade(config, "head")
        with psycopg.connect(owner_url) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0006_courses"
        yield owner_url
    finally:
        if previous is None:
            os.environ.pop("MIGRATION_DATABASE_URL", None)
        else:
            os.environ["MIGRATION_DATABASE_URL"] = previous



@pytest.fixture(scope='session')
def auth_key():
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


@pytest.fixture
def identity(database, monkeypatch, auth_key):
    import psycopg
    from fastapi.testclient import TestClient
    from app.auth import passwords
    from app.main import app
    from cryptography.fernet import Fernet

    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("AUTH_DATABASE_URL", os.environ["TEST_AUTH_DATABASE_URL"])
    monkeypatch.setenv("APP_ORIGIN", "https://testserver")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("AUTH0_ASSURANCE_PROFILE", raising=False)
    monkeypatch.setenv("AUTH_ENCRYPTION_KEY", auth_key)
    user, other, tenant, foreign = (uuid4() for _ in range(4))
    email = f"{user}@example.invalid"
    password = "A synthetic test password 123!"
    with psycopg.connect(database) as db:
        db.execute("DELETE FROM auth_rate_buckets")
        for uid, mail in ((user, email), (other, f"{other}@example.invalid")):
            db.execute("INSERT INTO users(id,email,password_hash) VALUES (%s,%s,%s)",
                       (uid, mail, passwords.hash(password)))
        for tid in (tenant, foreign):
            db.execute("INSERT INTO tenants(id,slug,name) VALUES (%s,%s,'Test')", (tid, str(tid)))
        for uid, tid in ((user, tenant), (other, foreign)):
            db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES (%s,%s,%s,'student')",
                       (uuid4(), tid, uid))
    with TestClient(app, base_url="https://testserver") as client:
        yield client, database, user, tenant, foreign, email, password
