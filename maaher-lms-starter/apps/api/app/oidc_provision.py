"""Offline binding of a verified Auth0 subject to an existing synthetic user.

There is no HTTP/email linking route. Real infrastructure provisioning requires
an independently reviewed operator runbook; this CLI targets development only.
"""
import os
from uuid import UUID, uuid4
from urllib.parse import urlsplit

import psycopg


def bind_identity(db, user_id, issuer, subject, is_operator, reference):
    name = db.execute('SELECT current_database()').fetchone()[0]
    if not name.startswith('maaher_test_'):
        raise ValueError('Development binding requires a disposable maaher_test_* database')
    parsed = urlsplit(issuer)
    if (parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.auth0.com')
            or parsed.netloc != parsed.hostname or parsed.path != '/' or parsed.query or parsed.fragment
            or not 1 <= len(subject) <= 255 or not 8 <= len(reference) <= 120):
        raise ValueError('Canonical issuer, exact subject and verification reference required')
    user = db.execute("SELECT email FROM users WHERE id=%s AND status='active'", (user_id,)).fetchone()
    if not user:
        raise ValueError('Existing active user required; email is not an identity binding')
    if not is_operator and not db.execute("SELECT 1 FROM memberships WHERE user_id=%s AND role='admin' AND status='active'", (user_id,)).fetchone():
        raise ValueError('A tenant admin membership or explicit operator binding is required')
    db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('auth-email:' + user[0],))
    identifier = uuid4()
    db.execute('''INSERT INTO oidc_identities(id,user_id,issuer,subject,is_operator,provision_reference)
                  VALUES(%s,%s,%s,%s,%s,%s)''', (identifier,user_id,issuer,subject,is_operator,reference))
    db.execute('DELETE FROM sessions WHERE user_id=%s', (user_id,))
    db.execute('DELETE FROM password_resets WHERE user_id=%s', (user_id,))
    return identifier


def main():
    if os.environ.get('APP_ENV') != 'local':
        raise SystemExit('Development binding only; production operator review is pending')
    user = UUID(input('ID user sintetis yang sudah ada: ').strip())
    issuer = input('Issuer Auth0 HTTPS canonical (akhiri /): ').strip()
    subject = input('Auth0 User ID (sub) yang diverifikasi independen: ').strip()
    operator = input('Operator platform, bukan sekadar admin tenant? [yes/no]: ').strip() == 'yes'
    reference = input('Referensi verifikasi non-PII (8-120 karakter): ').strip()
    with psycopg.connect(os.environ['MIGRATION_DATABASE_URL']) as db:
        identifier = bind_identity(db,user,issuer,subject,operator,reference)
    print('Development identity binding committed:', identifier)


if __name__ == '__main__':
    main()
