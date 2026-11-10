"""Offline all-or-nothing re-encryption under a retained MultiFernet keyring.

Administrative connection, never reachable through an API. No secret output.
Production execution remains gated on independent operator trust approval.
"""
import os
import psycopg
from .auth_support import cipher


def rotate_rows(db):
    if os.environ.get('APP_ENV') not in {'local','test'}:
        raise RuntimeError('Independent production operator trust is unconfigured')
    ring=cipher()
    count=0
    for table,key,column in (('mfa_factors','user_id','encrypted_secret'),
                             ('mfa_enrollments','session_hash','encrypted_secret'),
                             ('oidc_login_flows','browser_hash','encrypted_state'),
                             ('auth_mail_outbox','id','encrypted_token')):
        # Identifiers are a fixed allowlist; a bad row aborts the whole rotation.
        for identity,value in db.execute(f'SELECT {key},{column} FROM {table} WHERE {column} IS NOT NULL FOR UPDATE').fetchall():
            rotated=ring.rotate(value.encode()).decode()
            db.execute(f'UPDATE {table} SET {column}=%s WHERE {key}=%s',(rotated,identity))
            count+=1
    return count


def main():
    if os.environ.get('APP_ENV')!='local':
        raise SystemExit('Local synthetic key rotation only until operator trust is approved')
    with psycopg.connect(os.environ['MIGRATION_DATABASE_URL']) as db:
        assert db.execute('SELECT current_database()').fetchone()[0].startswith('maaher_test_')
        count=rotate_rows(db)
    print('Re-encrypted rows after successful commit:',count)


if __name__=='__main__':
    main()
