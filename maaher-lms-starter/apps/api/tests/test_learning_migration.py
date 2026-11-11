"""Seeded progress upgrade and locked destructive downgrade guard."""
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit,urlunsplit
from types import SimpleNamespace
import os,io
import psycopg
from psycopg import sql
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import DBAPIError


def test_progress_upgrade_guard_downgrade_and_revision_preservation(database,monkeypatch):
    url=urlsplit(os.environ['TEST_MIGRATION_DATABASE_URL']);name='maaher_test_lms04_migration_'+uuid4().hex[:12]
    with psycopg.connect(urlunsplit(url._replace(path='/postgres')),autocommit=True) as db:db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    url=urlunsplit(url._replace(path='/'+name));monkeypatch.setenv('MIGRATION_DATABASE_URL',url)
    cfg=Config(str(Path(__file__).parents[1]/'alembic.ini'));command.upgrade(cfg,'0008_enrollment')
    uid,tid,cid,hid,eid,mid,lid=(uuid4() for _ in range(7))
    with psycopg.connect(url) as db:
        db.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,'preserve-learning-hash')",(uid,f'{uid}@example.invalid'))
        db.execute("INSERT INTO tenants(id,slug,name) VALUES(%s,%s,'Learning fixture')",(tid,str(tid)))
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'student')",(uuid4(),tid,uid))
        db.execute("INSERT INTO courses(id,tenant_id,owner_id,title,state) VALUES(%s,%s,%s,'Preserve course','published')",(cid,tid,uid))
        db.execute("INSERT INTO cohorts(id,tenant_id,course_id,title) VALUES(%s,%s,%s,'Preserve cohort')",(hid,tid,cid))
        db.execute('INSERT INTO enrollments(id,tenant_id,course_id,cohort_id,student_id) VALUES(%s,%s,%s,%s,%s)',(eid,tid,cid,hid,uid))
        db.execute("INSERT INTO course_modules(id,tenant_id,course_id,title,position) VALUES(%s,%s,%s,'Module',1)",(mid,tid,cid))
        db.execute("INSERT INTO course_lessons(id,tenant_id,course_id,module_id,title,content,position) VALUES(%s,%s,%s,%s,'Lesson','Preserve material',1)",(lid,tid,cid,mid))
    command.upgrade(cfg,'head')
    with psycopg.connect(url) as db:
        assert db.execute('SELECT content,revision FROM course_lessons WHERE id=%s',(lid,)).fetchone()==('Preserve material',1)
        db.execute('INSERT INTO lesson_progress(tenant_id,course_id,enrollment_id,student_id,lesson_id,lesson_revision) VALUES(%s,%s,%s,%s,%s,1)',(tid,cid,eid,uid,lid))
    with pytest.raises(DBAPIError,match='allow_progress_data_loss'):command.downgrade(cfg,'0008_enrollment')
    with psycopg.connect(url) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0012_assignments'
        assert db.execute('SELECT count(*) FROM lesson_progress').fetchone()[0]==1
    output=io.StringIO();offline=Config(str(Path(__file__).parents[1]/'alembic.ini'),output_buffer=output)
    command.downgrade(offline,'0010_learning_progress:0009_read_scope',sql=True)
    assert output.getvalue().index('LOCK TABLE')<output.getvalue().index('RAISE EXCEPTION')
    cfg.cmd_opts=SimpleNamespace(x=['allow_progress_data_loss=yes']);command.downgrade(cfg,'0008_enrollment')
    with psycopg.connect(url) as db:
        assert db.execute('SELECT content FROM course_lessons WHERE id=%s',(lid,)).fetchone()[0]=='Preserve material'
        assert db.execute('SELECT status FROM enrollments WHERE id=%s',(eid,)).fetchone()[0]=='active'
        assert db.execute("SELECT password_hash FROM users WHERE id=%s",(uid,)).fetchone()[0]=='preserve-learning-hash'
    command.upgrade(cfg,'head')
    with psycopg.connect(url) as db:assert db.execute('SELECT count(*) FROM lesson_progress').fetchone()[0]==0
