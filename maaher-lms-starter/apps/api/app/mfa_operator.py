"""Offline MFA authorization, never an HTTP route or an email workflow.

Only synthetic local operation is enabled until an independently authenticated
operator trust integration is chosen and reviewed. A boolean env flag is not
proof of operator MFA and cannot enable production authorization.
"""
from getpass import getpass
import os
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .security import new_token, token_digest


def approve_request(db, request_id, reference):
    flags = db.execute("""SELECT r.rolsuper OR r.rolbypassrls
       OR NOT pg_has_role(current_user,'maaher_mfa_operator','MEMBER')
       OR pg_has_role(current_user,'maaher_runtime','MEMBER')
       OR pg_has_role(current_user,'maaher_auth','MEMBER') AS unsafe
       FROM pg_roles r WHERE r.rolname=current_user""").fetchone()
    if flags['unsafe']:
        raise RuntimeError('Operator role must be separate, nonowner and nonprivileged')
    if os.environ.get('APP_ENV') not in {'local','test'}:
        raise RuntimeError('Production operator trust is unconfigured; authorization denied')
    if not db.execute('SELECT current_database() AS name').fetchone()['name'].startswith('maaher_test_'):
        raise RuntimeError('Only disposable synthetic databases may use this trust adapter')
    if not 8 <= len(reference) <= 120:
        raise ValueError('Independent verification reference required')
    token = new_token()
    changed = db.execute('SELECT authorize_mfa_request(%s,%s,%s) AS ok',
                         (request_id,token_digest(token),reference)).fetchone()['ok']
    if not changed:
        raise ValueError('Request expired, approved already or session inactive')
    return token


def main():
    if os.environ.get('APP_ENV') != 'local':
        raise SystemExit('Production trust is not configured; local synthetic workflow only')
    request_id = UUID(input('ID permintaan sintetis pada perangkat pemilik: '))
    reference = input('Referensi verifikasi independen sintetis (bukan email): ').strip()
    with psycopg.connect(os.environ['MFA_OPERATOR_DATABASE_URL'],row_factory=dict_row) as db:
        token = approve_request(db,request_id,reference)
    # Output only after successful COMMIT. Deliver in person to the verified device.
    print('Kode otorisasi sekali pakai (jangan gunakan email login/reset):',token)


if __name__ == '__main__':
    main()
