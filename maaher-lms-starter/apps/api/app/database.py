"""Separate tenant and authentication credentials; commit before response send."""
from contextlib import contextmanager
import os

import psycopg
from psycopg.rows import dict_row

# Tests instrument this connector in a separate uvicorn process, never via HTTP.
_connect = psycopg.connect


@contextmanager
def transaction(environment='DATABASE_URL', group='maaher_runtime'):
    with _connect(os.environ[environment], row_factory=dict_row) as db:
        flags = db.execute("""
            SELECT r.rolsuper OR r.rolbypassrls OR NOT pg_has_role(current_user,%s,'MEMBER') OR EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind='r'
                AND pg_has_role(current_user,c.relowner,'USAGE')
            ) OR (pg_has_role(current_user,'maaher_runtime','MEMBER')
                  AND pg_has_role(current_user,'maaher_auth','MEMBER')) AS unsafe
            FROM pg_roles r WHERE r.rolname=current_user
        """,(group,)).fetchone()
        if flags['unsafe']:
            raise RuntimeError('Koneksi harus memakai role runtime terpisah tanpa owner/BYPASSRLS')
        yield db
        # psycopg's connection context commits here. FastAPI callers must use
        # Depends(..., scope='function'), whose teardown precedes response send.


@contextmanager
def auth_transaction():
    with transaction('AUTH_DATABASE_URL','maaher_auth') as db:
        yield db


def user_context(db, user_id):
    db.execute("SELECT set_config('app.user_id', %s, true)",(str(user_id),))


def tenant_context(db, tenant_id):
    db.execute("SELECT set_config('app.tenant_id', %s, true)",(str(tenant_id),))


def session_context(db, token_hash):
    db.execute("SELECT set_config('app.session_hash',%s,true)",(token_hash,))


def external_managed(db, user_id):
    # A revoked binding must not silently re-enable the old local credentials.
    return db.execute('SELECT 1 FROM oidc_identities WHERE user_id=%s LIMIT 1', (user_id,)).fetchone() is not None
