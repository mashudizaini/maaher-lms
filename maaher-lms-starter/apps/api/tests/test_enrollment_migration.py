"""Disposable seeded upgrade, guarded online/offline downgrade, no old DB use."""
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit,urlunsplit
import os

import psycopg
from psycopg import sql
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import DBAPIError
from types import SimpleNamespace


def test_seeded_enrollment_upgrade_rollback_guard_and_reupgrade(database,monkeypatch):
    owner=urlsplit(os.environ['TEST_MIGRATION_DATABASE_URL']);name='maaher_test_lms03_migration_'+uuid4().hex[:12]
    with psycopg.connect(urlunsplit(owner._replace(path='/postgres')),autocommit=True) as db:
        db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    url=urlunsplit(owner._replace(path='/'+name));monkeypatch.setenv('MIGRATION_DATABASE_URL',url)
    cfg=Config(str(Path(__file__).parents[1]/'alembic.ini')); command.upgrade(cfg,'0007_course_review')
    uid,tid,cid,hid,eid=(uuid4() for _ in range(5))
    with psycopg.connect(url) as db:
        db.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,'preserve-hash')",(uid,f'{uid}@example.invalid'))
        db.execute("INSERT INTO tenants(id,slug,name) VALUES(%s,%s,'Migration fixture')",(tid,str(tid)))
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'student')",(uuid4(),tid,uid))
        db.execute("INSERT INTO courses(id,tenant_id,owner_id,title) VALUES(%s,%s,%s,'Preserve course')",(cid,tid,uid))
    command.upgrade(cfg,'head')
    with psycopg.connect(url) as db:
        assert db.execute('SELECT title FROM courses WHERE id=%s',(cid,)).fetchone()[0]=='Preserve course'
        db.execute("INSERT INTO cohorts(id,tenant_id,course_id,title) VALUES(%s,%s,%s,'Preserve cohort')",(hid,tid,cid))
        db.execute('INSERT INTO enrollments(id,tenant_id,course_id,cohort_id,student_id) VALUES(%s,%s,%s,%s,%s)',(eid,tid,cid,hid,uid))
    with pytest.raises(DBAPIError,match='allow_enrollment_data_loss'): command.downgrade(cfg,'0007_course_review')
    with psycopg.connect(url) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0008_enrollment'
        assert db.execute('SELECT status FROM enrollments WHERE id=%s',(eid,)).fetchone()[0]=='active'
    import io
    output=io.StringIO();offline=Config(str(Path(__file__).parents[1]/'alembic.ini'),output_buffer=output)
    command.downgrade(offline,'0008_enrollment:0007_course_review',sql=True)
    generated=output.getvalue();assert 'allow_enrollment_data_loss' in generated
    assert generated.index('RAISE EXCEPTION')<generated.index('DROP TABLE enrollments')
    cfg.cmd_opts=SimpleNamespace(x=['allow_enrollment_data_loss=yes'])
    command.downgrade(cfg,'0007_course_review');command.upgrade(cfg,'head')
    with psycopg.connect(url) as db:
        assert db.execute('SELECT password_hash FROM users WHERE id=%s',(uid,)).fetchone()[0]=='preserve-hash'
        assert db.execute('SELECT title FROM courses WHERE id=%s',(cid,)).fetchone()[0]=='Preserve course'
        assert db.execute('SELECT count(*) FROM enrollments').fetchone()[0]==0
    # Retain this new synthetic DB for inspection, just like the main suite DB.
