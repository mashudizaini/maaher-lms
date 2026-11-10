"""Synthetic test helpers; no production trust shortcuts."""
import os
from uuid import uuid4


def sign_in(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password},
                       headers={"origin": "https://testserver"})



def authorize_mfa(client, purpose="bootstrap"):
    import psycopg
    from psycopg.rows import dict_row
    from app.mfa_operator import approve_request
    response=client.post('/auth/mfa/request',json={'purpose':purpose},headers={'origin':'https://testserver'})
    assert response.status_code==200,response.text
    with psycopg.connect(os.environ['TEST_OPERATOR_DATABASE_URL'],row_factory=dict_row) as db:
        authorization=approve_request(db,response.json()['request_id'],'synthetic-in-person-verification')
    return authorization



def enroll_mfa(client, password):
    import pyotp
    response = client.post("/auth/mfa/enroll", json={"password": password,"authorization":authorize_mfa(client)},
                           headers={"origin": "https://testserver"})
    assert response.status_code == 200, response.text
    totp = pyotp.parse_uri(response.json()["provisioning_uri"])
    response = client.post("/auth/mfa/verify", json={"code": totp.now()},
                           headers={"origin": "https://testserver"})
    assert response.status_code == 200, response.text
    return totp



def make_admin(identity):
    import psycopg
    client, owner, user, tenant, foreign, email, password = identity
    with psycopg.connect(owner) as db:
        db.execute("UPDATE memberships SET role='admin' WHERE user_id=%s", (user,))
    assert sign_in(client, email, password).status_code == 200
    totp = enroll_mfa(client, password)
    return {"origin": "https://testserver", "x-tenant-id": str(tenant)}, totp



def mail_token(owner, email, kind):
    import psycopg
    from app.auth_support import cipher
    with psycopg.connect(owner) as db:
        row = db.execute("SELECT encrypted_token FROM auth_mail_outbox WHERE recipient=%s AND kind=%s AND encrypted_token IS NOT NULL ORDER BY expires_at DESC LIMIT 1",
                         (email, kind)).fetchone()
    assert row
    return cipher().decrypt(row[0].encode()).decode()



def issue_invite(identity, headers, email=None, role="student"):
    client, owner = identity[:2]
    email = email or f"{uuid4()}@example.invalid"
    response = client.post("/auth/invitations", json={"email": email, "role": role}, headers=headers)
    assert response.status_code == 202, response.text
    token = mail_token(owner, email, "invitation")
    assert token not in response.text
    return email, token
