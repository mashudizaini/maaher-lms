"""Synthetic data bridge used only by Playwright; never mounted in the API."""
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))
from app.auth import passwords
from app.auth_support import cipher


def main():
    operation = sys.argv[1]
    payload = json.load(sys.stdin)
    with psycopg.connect(os.environ["TEST_MIGRATION_DATABASE_URL"]) as db:
        name = db.execute("SELECT current_database()").fetchone()[0]
        assert name.startswith("maaher_test_"), "Refusing non-test database"
        if operation in {"seed", "oidc-seed"}:
            user, tenant = uuid4(), uuid4()
            email = f"{user}@example.invalid"
            password = "Synthetic browser password 123!"
            db.execute("INSERT INTO users(id,email,password_hash) VALUES (%s,%s,%s)", (user, email, passwords.hash(password)))
            db.execute("INSERT INTO tenants(id,slug,name) VALUES (%s,%s,'Organisasi tes browser')", (tenant, str(tenant)))
            db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES (%s,%s,%s,'admin')", (uuid4(), tenant, user))
            if operation == 'oidc-seed':
                from app.oidc_provision import bind_identity
                bind_identity(db,user,'https://browser-tests.us.auth0.com/','auth0|synthetic-browser-staff',False,
                              'synthetic-supervised-browser-binding')
            result = {"email": email, "password": password, "tenant": str(tenant), "user": str(user)}
        elif operation == 'member':
            uid=uuid4();email=f'{uid}@example.invalid'
            role=payload.get('role','student')
            assert role in {'student','teacher'}, 'Unsupported synthetic member role'
            db.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,'unused-synthetic-password')",(uid,email))
            db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,%s)",(uuid4(),payload['tenant'],uid,role))
            result={'user':str(uid),'email':email}
        elif operation == 'course-budget':
            # Test-only owner bridge; never part of the API/runtime image.
            assert payload['mode'] in {'exhaust','expire'}
            row=db.execute("UPDATE course_write_limits SET attempts=60,window_start=CASE WHEN %s='expire' THEN now()-interval '2 minutes' ELSE now() END WHERE tenant_id=%s AND user_id=%s RETURNING user_id",
                           (payload['mode'],payload['tenant'],payload['user'])).fetchone()
            assert row, 'Synthetic actor must have made a course write'
            result={'updated':True}
        elif operation == "token":
            row = db.execute("SELECT encrypted_token FROM auth_mail_outbox WHERE recipient=%s AND kind=%s ORDER BY expires_at DESC LIMIT 1",
                             (payload["email"], payload["kind"])).fetchone()
            assert row and row[0]
            result = {"token": cipher().decrypt(row[0].encode()).decode()}
        elif operation == "totp":
            import pyotp,time
            result = {"code": pyotp.parse_uri(payload["uri"]).at(time.time()+int(payload.get("offset",0)))}
        elif operation == 'authorize':
            from app.mfa_operator import approve_request
            with psycopg.connect(os.environ['TEST_OPERATOR_DATABASE_URL'],row_factory=dict_row) as operator:
                authorization=approve_request(operator,payload['request_id'],'browser-synthetic-in-person-proof')
            result={'authorization':authorization}
        else:
            raise ValueError("Unknown test operation")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
