"""Explicit scheduled retention command; never invoked by request processing."""
import os
import psycopg
from psycopg.rows import dict_row


def retain(db):
    role=db.execute("""SELECT r.rolsuper OR r.rolbypassrls OR NOT pg_has_role(current_user,'maaher_maintenance','MEMBER')
      OR pg_has_role(current_user,'maaher_auth','MEMBER') OR pg_has_role(current_user,'maaher_runtime','MEMBER') AS unsafe
      FROM pg_roles r WHERE r.rolname=current_user""").fetchone()
    if role['unsafe']:
        raise RuntimeError('Dedicated restricted maintenance role required')
    db.execute('SELECT retain_auth_data()')


def main():
    if os.environ.get('APP_ENV') not in {'local','test'}:
        raise SystemExit('Production retention policy/scheduler approval is pending')
    with psycopg.connect(os.environ['MAINTENANCE_DATABASE_URL'],row_factory=dict_row) as db:
        name=db.execute('SELECT current_database() AS name').fetchone()['name']
        if not name.startswith('maaher_test_'):
            raise SystemExit('This unapproved policy may only run on disposable test databases')
        retain(db)
    print('Retention committed on disposable test data')


if __name__=='__main__':
    main()
