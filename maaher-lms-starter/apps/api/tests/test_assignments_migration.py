"""0010→0012 preserves parent; seeded history blocks destructive rollback."""
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit,urlunsplit
from types import SimpleNamespace
import io,os
import psycopg,pytest
from psycopg import sql
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import DBAPIError
from app.security import token_digest
from app.database import session_context,tenant_context


def test_assignment_seeded_upgrade_offline_guard_rollback_and_reupgrade(database,monkeypatch):
    original=urlsplit(os.environ['TEST_MIGRATION_DATABASE_URL']);name='maaher_test_lms05_migration_'+uuid4().hex[:12]
    with psycopg.connect(urlunsplit(original._replace(path='/postgres')),autocommit=True) as db:db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    owner=urlunsplit(original._replace(path='/'+name));monkeypatch.setenv('MIGRATION_DATABASE_URL',owner)
    cfg=Config(str(Path(__file__).parents[1]/'alembic.ini'));command.upgrade(cfg,'0010_learning_progress')
    uid,tid,cid,hid,eid,mid,lid,aid,vid,sid=(uuid4() for _ in range(10));cap='migration-'+uuid4().hex
    with psycopg.connect(owner) as db:
        db.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,'preserve-assignment-hash')",(uid,f'{uid}@example.invalid'))
        db.execute("INSERT INTO tenants(id,slug,name) VALUES(%s,%s,'Preserve')",(tid,str(tid)))
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'student')",(uuid4(),tid,uid))
        db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(%s,%s,now()+interval '1 hour')",(token_digest(cap),uid))
        db.execute("INSERT INTO courses(id,tenant_id,owner_id,title,state) VALUES(%s,%s,%s,'Preserve','published')",(cid,tid,uid))
        db.execute("INSERT INTO cohorts(id,tenant_id,course_id,title) VALUES(%s,%s,%s,'Cohort')",(hid,tid,cid))
        db.execute('INSERT INTO enrollments(id,tenant_id,course_id,cohort_id,student_id) VALUES(%s,%s,%s,%s,%s)',(eid,tid,cid,hid,uid))
        db.execute("INSERT INTO course_modules(id,tenant_id,course_id,title,position) VALUES(%s,%s,%s,'Module',1)",(mid,tid,cid))
        db.execute("INSERT INTO course_lessons(id,tenant_id,course_id,module_id,title,content,position) VALUES(%s,%s,%s,%s,'Lesson','Preserve material',1)",(lid,tid,cid,mid))
        db.execute('INSERT INTO lesson_progress(tenant_id,course_id,enrollment_id,student_id,lesson_id,lesson_revision) VALUES(%s,%s,%s,%s,%s,1)',(tid,cid,eid,uid,lid))
    command.upgrade(cfg,'head')
    with psycopg.connect(owner) as db:
        assert db.execute('SELECT content,revision,content_attestation FROM course_lessons WHERE id=%s',(lid,)).fetchone()==('Preserve material',1,None)
        db.execute('INSERT INTO assignments(id,tenant_id,course_id,lesson_id) VALUES(%s,%s,%s,%s)',(aid,tid,cid,lid))
        db.execute('''INSERT INTO assignment_versions(id,tenant_id,course_id,assignment_id,version_no,title,instructions,language,rubric,max_attempts,allow_late,content_attestation)
           VALUES(%s,%s,%s,%s,1,'Fixture','Fixture instructions','text','[{"criterion":"All","max_points":100}]',3,false,'trusted-migration-fixture-not-a-publish-proof')''',(vid,tid,cid,aid))
        db.execute("UPDATE assignments SET draft_version_id=%s,published_version_id=%s,state='published' WHERE id=%s",(vid,vid,aid))
        # Session-bound owner fixture exercises draft/submission triggers too.
        session_context(db,token_digest(cap));tenant_context(db,tid)
        db.execute("INSERT INTO submission_drafts(tenant_id,course_id,assignment_id,enrollment_id,student_id,version_id,source_code) VALUES(%s,%s,%s,%s,%s,%s,'Preserve answer')",(tid,cid,aid,eid,uid,vid))
        db.execute("""INSERT INTO submissions(id,tenant_id,course_id,assignment_id,enrollment_id,student_id,version_id,draft_revision,request_id,attempt_no,source_code,note,submitted_at,status)
            VALUES(%s,%s,%s,%s,%s,%s,%s,1,%s,1,'','',now(),'submitted')""",(sid,tid,cid,aid,eid,uid,vid,uuid4()))
    for flags in ([],['allow_assignment_data_loss=no'],['allow_assignment_data_loss=YES'],['allow_assignment_data_loss=true']):
        cfg.cmd_opts=SimpleNamespace(x=flags)
        with pytest.raises(DBAPIError,match='allow_assignment_data_loss'):command.downgrade(cfg,'0010_learning_progress')
        with psycopg.connect(owner) as db:
            assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0013_grading'
            assert db.execute('SELECT source_code FROM submissions WHERE id=%s',(sid,)).fetchone()[0]=='Preserve answer'
    output=io.StringIO();offline=Config(str(Path(__file__).parents[1]/'alembic.ini'),output_buffer=output)
    command.downgrade(offline,'0012_assignments:0010_learning_progress',sql=True)
    assert output.getvalue().index('LOCK TABLE')<output.getvalue().index('RAISE EXCEPTION')<output.getvalue().index('DROP TABLE')
    cfg.cmd_opts=SimpleNamespace(x=['allow_assignment_data_loss=yes']);command.downgrade(cfg,'0010_learning_progress')
    with psycopg.connect(owner) as db:
        assert db.execute('SELECT content,revision FROM course_lessons WHERE id=%s',(lid,)).fetchone()==('Preserve material',1)
        assert db.execute('SELECT count(*) FROM lesson_progress WHERE enrollment_id=%s',(eid,)).fetchone()[0]==1
        assert db.execute('SELECT status FROM enrollments WHERE id=%s',(eid,)).fetchone()[0]=='active'
        assert db.execute('SELECT password_hash FROM users WHERE id=%s',(uid,)).fetchone()[0]=='preserve-assignment-hash'
    command.upgrade(cfg,'head')
    with psycopg.connect(owner) as db:assert db.execute('SELECT count(*) FROM assignments').fetchone()[0]==0
