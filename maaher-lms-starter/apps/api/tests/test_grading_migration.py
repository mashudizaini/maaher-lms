"""Seeded0012→0013, guarded/offline rollback and preserved parent hashes."""
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
from uuid import uuid4
from types import SimpleNamespace
import hashlib,io,json,os
import psycopg,pytest
from psycopg import sql
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import DBAPIError
from app.database import session_context,tenant_context
from app.security import token_digest


def test_grading_seeded_upgrade_guard_offline_rollback_and_reupgrade(database,monkeypatch):
    original=urlsplit(os.environ['TEST_MIGRATION_DATABASE_URL']);name='maaher_test_lms06_migration_'+uuid4().hex[:12]
    with psycopg.connect(urlunsplit(original._replace(path='/postgres')),autocommit=True) as db:db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    owner=urlunsplit(original._replace(path='/'+name));monkeypatch.setenv('MIGRATION_DATABASE_URL',owner)
    cfg=Config(str(Path(__file__).parents[1]/'alembic.ini'));command.upgrade(cfg,'0012_assignments')
    uid,teacher,tid,cid,hid,eid,mid,lid,aid,vid,sid=(uuid4() for _ in range(11));student_cap='student-'+uuid4().hex;teacher_cap='teacher-'+uuid4().hex
    with psycopg.connect(owner) as db:
        db.execute("INSERT INTO tenants(id,slug,name) VALUES(%s,%s,'Preserve grading fixture')",(tid,str(tid)))
        for user,role,cap in [(uid,'student',student_cap),(teacher,'teacher',teacher_cap)]:
            db.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,'preserve-grading-hash')",(user,f'{user}@example.invalid'))
            db.execute('INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,%s)',(uuid4(),tid,user,role))
            db.execute("INSERT INTO sessions(token_hash,user_id,expires_at,mfa_verified) VALUES(%s,%s,now()+interval '1 hour',true)",(token_digest(cap),user))
        db.execute("INSERT INTO courses(id,tenant_id,owner_id,title,state) VALUES(%s,%s,%s,'Preserve course','published')",(cid,tid,teacher))
        db.execute('INSERT INTO courses_teachers(tenant_id,course_id,user_id) VALUES(%s,%s,%s)',(tid,cid,teacher))
        db.execute("INSERT INTO cohorts(id,tenant_id,course_id,title) VALUES(%s,%s,%s,'Cohort')",(hid,tid,cid))
        db.execute('INSERT INTO enrollments(id,tenant_id,course_id,cohort_id,student_id) VALUES(%s,%s,%s,%s,%s)',(eid,tid,cid,hid,uid))
        db.execute("INSERT INTO course_modules(id,tenant_id,course_id,title,position) VALUES(%s,%s,%s,'Module',1)",(mid,tid,cid))
        db.execute("INSERT INTO course_lessons(id,tenant_id,course_id,module_id,title,content,position) VALUES(%s,%s,%s,%s,'Lesson','Preserve material',1)",(lid,tid,cid,mid))
        db.execute('INSERT INTO lesson_progress(tenant_id,course_id,enrollment_id,student_id,lesson_id,lesson_revision) VALUES(%s,%s,%s,%s,%s,1)',(tid,cid,eid,uid,lid))
        external=uuid4();db.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,'preserve-external-hash')",(external,f'{external}@example.invalid'))
        db.execute("INSERT INTO oidc_identities(id,user_id,issuer,subject,provision_reference) VALUES(%s,%s,'https://fixture.us.auth0.com/','auth0|grading-migration-fixture','preserve-binding')",(uuid4(),external))
        db.execute('INSERT INTO assignments(id,tenant_id,course_id,lesson_id) VALUES(%s,%s,%s,%s)',(aid,tid,cid,lid))
        db.execute('''INSERT INTO assignment_versions(id,tenant_id,course_id,assignment_id,version_no,title,instructions,language,rubric,max_attempts,allow_late,content_attestation)
         VALUES(%s,%s,%s,%s,1,'Fixture','Instructions','text','[{"criterion":"All","max_points":100}]',3,false,'migration-fixture-not-publish-proof')''',(vid,tid,cid,aid))
        db.execute("UPDATE assignments SET draft_version_id=%s,published_version_id=%s,state='published' WHERE id=%s",(vid,vid,aid))
        session_context(db,token_digest(student_cap));tenant_context(db,tid)
        db.execute("INSERT INTO submission_drafts(tenant_id,course_id,assignment_id,enrollment_id,student_id,version_id,source_code) VALUES(%s,%s,%s,%s,%s,%s,'Preserve source')",(tid,cid,aid,eid,uid,vid))
        db.execute("""INSERT INTO submissions(id,tenant_id,course_id,assignment_id,enrollment_id,student_id,version_id,draft_revision,request_id,attempt_no,source_code,note,submitted_at,status)
         VALUES(%s,%s,%s,%s,%s,%s,%s,1,%s,1,'','',now(),'submitted')""",(sid,tid,cid,aid,eid,uid,vid,uuid4()))
    tables=('users','tenants','memberships','sessions','courses','courses_teachers','course_modules','course_lessons','cohorts','enrollments','assignments','assignment_versions','submission_drafts','submissions','lesson_progress','oidc_identities')
    def hashes():
        with psycopg.connect(owner) as db:
            return {table:hashlib.sha256(json.dumps(sorted(str(row[0]) for row in db.execute(sql.SQL('SELECT row_to_json(t) FROM {} t').format(sql.Identifier(table))).fetchall())).encode()).hexdigest() for table in tables}
    before=hashes();command.upgrade(cfg,'head');assert hashes()==before
    with psycopg.connect(owner) as db:
        session_context(db,token_digest(teacher_cap));tenant_context(db,tid)
        db.execute('INSERT INTO grading_entries(submission_id,tenant_id,course_id) VALUES(%s,%s,%s)',(sid,tid,cid))
        db.execute('''INSERT INTO grade_revisions(id,tenant_id,course_id,submission_id,entry_version,revision_no,scores,total,feedback,reason,reviewer_id)
         VALUES(%s,%s,%s,%s,1,1,'[{"criterion_index":0,"points":80}]',0,'Keep feedback','Initial',%s)''',(uuid4(),tid,cid,sid,teacher))
        db.execute("UPDATE grading_entries SET version=2,last_action='released',last_reason='Publish' WHERE submission_id=%s",(sid,))
        assert db.execute('SELECT total FROM grade_publications WHERE submission_id=%s',(sid,)).fetchone()[0]==80
    for flags in ([],['allow_grading_data_loss=no'],['allow_grading_data_loss=YES'],['allow_grading_data_loss=true']):
        cfg.cmd_opts=SimpleNamespace(x=flags)
        with pytest.raises(DBAPIError,match='allow_grading_data_loss'):command.downgrade(cfg,'0012_assignments')
        with psycopg.connect(owner) as db:assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0013_grading'
    cfg.cmd_opts=None
    with pytest.raises(DBAPIError,match='allow_grading_data_loss'):command.downgrade(cfg,'base')
    output=io.StringIO();offline=Config(str(Path(__file__).parents[1]/'alembic.ini'),output_buffer=output)
    command.downgrade(offline,'0013_grading:0012_assignments',sql=True)
    assert output.getvalue().index('LOCK TABLE')<output.getvalue().index('RAISE EXCEPTION')<output.getvalue().index('DROP TABLE')
    cfg.cmd_opts=SimpleNamespace(x=['allow_grading_data_loss=yes']);command.downgrade(cfg,'0012_assignments')
    # Grade events intentionally append parent audit; all submitted learning data stay identical.
    assert hashes()==before
    with psycopg.connect(owner) as db:assert db.execute("SELECT to_regclass('public.grade_revisions')").fetchone()[0] is None
    command.upgrade(cfg,'head')
    with psycopg.connect(owner) as db:assert db.execute('SELECT count(*) FROM grading_entries').fetchone()[0]==0
