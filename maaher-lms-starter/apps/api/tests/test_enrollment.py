"""Real DB student lifecycle, tenant isolation, concurrency and live access."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import os

import psycopg
from psycopg.rows import dict_row
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import passwords
from app.database import transaction,session_context,tenant_context,user_context
from app.security import token_digest
from auth_helpers import sign_in
from test_courses import author,detail,filled,write
from test_course_review import teacher_account


@pytest.fixture
def enrollment_case(author):
    identity,headers,cid=author; uid=uuid4(); email=f'{uid}@example.invalid'
    with psycopg.connect(identity[1]) as db:
        db.execute('INSERT INTO users(id,email,password_hash) VALUES(%s,%s,%s)',(uid,email,passwords.hash(identity[6])))
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'student')",(uuid4(),identity[3],uid))
    response=identity[0].post('/cohorts',json={'course_id':cid,'title':'Python A'},headers=headers)
    assert response.status_code==201,response.text
    mid,lid=filled(author)
    with TestClient(app,base_url='https://testserver') as client:
        assert sign_in(client,email,identity[6]).status_code==200
        yield {'author':author,'uid':uid,'student':client,'hid':response.json()['id'],'mid':mid,'lid':lid}


def enroll(case,**override):
    identity,headers,cid=case['author']
    return identity[0].post('/enrollments',json={'course_id':cid,'cohort_id':case['hid'],'student_id':str(case['uid']),**override},headers=headers)


def roster(case,status='active',client=None,**extra):
    identity,headers,cid=case['author']
    return (client or identity[0]).get('/enrollments',params={'course_id':cid,'status':status,**extra},headers=headers)


def action(case,eid,kind,version=1,**body):
    identity,headers,_=case['author']
    return identity[0].post(f'/enrollments/{eid}/{kind}',json={'version':version,**body},headers=headers)


def access(case,status):
    identity,headers,cid=case['author']; student=case['student']
    assert student.get('/learning/courses/'+cid,headers=headers).status_code==status
    assert student.get(f'/learning/courses/{cid}/modules/{case["mid"]}/lessons/{case["lid"]}',headers=headers).status_code==status
    listed=student.get('/learning/courses',headers=headers)
    assert listed.status_code==200 and bool(listed.json()['courses'])==(status==200)


def test_enrollment_publish_revoke_reactivation_and_student_read_only(enrollment_case):
    c=enrollment_case; identity,headers,cid=c['author']; access(c,404)
    response=enroll(c); assert response.status_code==201,response.text; eid=response.json()['id']; access(c,404)
    assert write(c['author'],'/publish').status_code==200; access(c,200)
    outline=c['student'].get('/learning/courses/'+cid,headers=headers).json(); assert 'teachers' not in outline and 'owner_id' not in outline
    assert c['student'].get('/courses/'+cid,headers=headers).status_code==403
    assert c['student'].post('/enrollments',json={'course_id':cid,'cohort_id':c['hid'],'student_id':str(c['uid'])},headers=headers).status_code==403
    assert roster(c,client=c['student']).json()['enrollments'][0]['student_id']==str(c['uid'])
    assert enroll(c).status_code==409
    assert action(c,eid,'revoke').status_code==200; access(c,404)
    assert action(c,eid,'reactivate',2,cohort_id=c['hid']).status_code==200; access(c,200)
    events=identity[0].get('/auth/audit',headers=headers).json()
    assert {'cohort.created','enrollment.created','enrollment.revoked','enrollment.reactivated'}<={x['action'] for x in events}


@pytest.mark.parametrize('scope',['role','membership','user','cohort','course'])
def test_revoked_authority_never_implicitly_restores_enrollment(enrollment_case,scope):
    c=enrollment_case; identity,headers,cid=c['author']; assert enroll(c).status_code==201
    assert write(c['author'],'/publish').status_code==200; access(c,200)
    if scope=='role':
        for role in ('teacher','student'):
            assert identity[0].post(f'/auth/memberships/{c["uid"]}/role',json={'role':role},headers=headers).status_code==200
    elif scope in {'membership','user'}:
        with psycopg.connect(identity[1]) as db:
            if scope=='membership':
                for state in ('revoked','active'): db.execute('UPDATE memberships SET status=%s WHERE tenant_id=%s AND user_id=%s',(state,identity[3],c['uid']))
            else:
                for state in ('disabled','active'): db.execute('UPDATE users SET status=%s WHERE id=%s',(state,c['uid']))
    elif scope=='cohort':
        assert identity[0].post(f'/cohorts/{c["hid"]}/archive',json={'version':1},headers=headers).status_code==200
        assert identity[0].post(f'/cohorts/{c["hid"]}/restore',json={'version':2},headers=headers).status_code==200
    else:
        assert write(c['author'],'/archive').status_code==200
        assert write(c['author'],'/restore').status_code==200
        assert write(c['author'],'/publish').status_code==200
    access(c,404)
    assert roster(c).json()['enrollments']==[]
    old=roster(c,'revoked').json()['enrollments']; assert len(old)==1 and old[0]['version']==2
    assert action(c,old[0]['id'],'reactivate',2,cohort_id=c['hid']).status_code==200; access(c,200)


def test_unpublish_temporarily_pauses_read_without_reenrollment(enrollment_case):
    c=enrollment_case; assert enroll(c).status_code==201; assert write(c['author'],'/publish').status_code==200
    access(c,200); assert write(c['author'],'/unpublish').status_code==200; access(c,404)
    assert write(c['author'],'/publish').status_code==200; access(c,200)


def test_move_cohort_is_atomic_and_conflict_does_not_change_assignment(enrollment_case):
    c=enrollment_case; identity,headers,cid=c['author']; eid=enroll(c).json()['id']
    new=identity[0].post('/cohorts',json={'course_id':cid,'title':'Python B'},headers=headers).json()['id']
    assert action(c,eid,'move',cohort_id=new).status_code==200
    assert roster(c).json()['enrollments'][0]['cohort_id']==new
    assert action(c,eid,'move',cohort_id=c['hid']).status_code==409
    assert roster(c).json()['enrollments'][0]['cohort_id']==new
    assert action(c,eid,'move',2,cohort_id=str(uuid4())).status_code==404
    assert roster(c).json()['enrollments'][0]['version']==2


def test_teacher_sees_assigned_roster_only_and_cannot_mutate(enrollment_case,teacher_account):
    c=enrollment_case; uid,teacher=teacher_account; identity,headers,cid=c['author']; eid=enroll(c).json()['id']
    assert roster(c,client=teacher).json()['enrollments']==[]
    assert write(c['author'],'/teachers',user_id=str(uid),assigned=True).status_code==200
    assert roster(c,client=teacher).json()['enrollments'][0]['id']==eid
    assert teacher.post(f'/enrollments/{eid}/revoke',json={'version':1},headers=headers).status_code==403
    assert teacher.get('/cohorts',params={'course_id':cid},headers=headers).json()['cohorts'][0]['id']==c['hid']
    assert write(c['author'],'/archive').status_code==200
    assert roster(c,client=teacher).json()['enrollments']==[]


def test_foreign_student_course_cohort_and_extra_authority_fields_are_rejected(enrollment_case):
    c=enrollment_case; identity,headers,cid=c['author']
    with psycopg.connect(identity[1]) as db:
        foreign=db.execute('SELECT user_id FROM memberships WHERE tenant_id=%s',(identity[4],)).fetchone()[0]
    assert enroll(c,student_id=str(foreign)).status_code==409
    assert enroll(c,student_id=str(identity[2])).status_code==409
    assert enroll(c,course_id=str(uuid4())).status_code==404
    assert enroll(c,cohort_id=str(uuid4())).status_code==404
    assert enroll(c,tenant_id=str(identity[4])).status_code==422
    assert enroll(c,status='active').status_code==422
    other=identity[0].post('/courses',json={'title':'Other'},headers=headers).json()['id']
    h=identity[0].post('/cohorts',json={'title':'Other cohort','course_id':other},headers=headers).json()['id']
    assert enroll(c,cohort_id=h).status_code==404
    assert roster(c).json()['enrollments']==[]


def test_concurrent_duplicate_and_reactivation_use_one_version(enrollment_case):
    c=enrollment_case; identity,headers,cid=c['author']
    def concurrent(kind):
        with TestClient(app,base_url='https://testserver') as client:
            client.cookies.update(identity[0].cookies)
            if kind=='create': return client.post('/enrollments',json={'course_id':cid,'cohort_id':c['hid'],'student_id':str(c['uid'])},headers=headers).status_code
            return client.post(f'/enrollments/{eid}/reactivate',json={'version':2,'cohort_id':c['hid']},headers=headers).status_code
    with ThreadPoolExecutor(max_workers=2) as pool: assert sorted(pool.map(concurrent,['create','create']))==[201,409]
    eid=roster(c).json()['enrollments'][0]['id']; assert action(c,eid,'revoke').status_code==200
    with ThreadPoolExecutor(max_workers=2) as pool: assert sorted(pool.map(concurrent,['reactivate','reactivate']))==[200,409]
    assert len(roster(c).json()['enrollments'])==1


def test_student_sql_rls_and_forged_context_do_not_grant_content(enrollment_case):
    c=enrollment_case; identity,headers,cid=c['author']; assert enroll(c).status_code==201; assert write(c['author'],'/publish').status_code==200
    with transaction() as db:
        session_context(db,token_digest(c['student'].cookies['maaher_session'])); tenant_context(db,identity[3])
        assert len(db.execute('SELECT id FROM courses').fetchall())==1
        assert len(db.execute('SELECT id FROM course_lessons').fetchall())==1
        assert len(db.execute('SELECT id FROM cohorts').fetchall())==1
        assert len(db.execute('SELECT id FROM enrollments').fetchall())==1
        assert db.execute("UPDATE enrollments SET status='revoked' RETURNING id").fetchall()==[]
        tenant_context(db,identity[4]); user_context(db,identity[2])
        assert db.execute('SELECT id FROM courses').fetchall()==[]
        assert db.execute('SELECT id FROM enrollments').fetchall()==[]
    with transaction() as db:
        user_context(db,c['uid']); tenant_context(db,identity[3])
        assert db.execute('SELECT id FROM courses').fetchall()==[]
        assert db.execute('SELECT id FROM enrollments').fetchall()==[]
    with psycopg.connect(os.environ['TEST_DATABASE_URL']) as db:
        for table in ('cohorts','enrollments'):
            assert not db.execute('SELECT has_table_privilege(current_user,%s,\'DELETE\')',(table,)).fetchone()[0]


def test_archive_course_keeps_course_publication_and_cohort_audit_consistent(enrollment_case):
    c=enrollment_case; identity,headers,cid=c['author']; enroll(c)
    response=identity[0].post(f'/cohorts/{c["hid"]}',json={'version':1,'title':'Renamed cohort'},headers=headers)
    assert response.status_code==200
    assert identity[0].post(f'/cohorts/{c["hid"]}/archive',json={'version':1},headers=headers).status_code==409
    assert identity[0].post(f'/cohorts/{c["hid"]}/archive',json={'version':2},headers=headers).status_code==200
    assert enroll(c).status_code==409
    assert detail(c['author'])['state']=='draft'
    events=identity[0].get('/auth/audit',headers=headers).json()
    assert any(x['action']=='enrollment.access_revoked' for x in events)


def test_students_cannot_read_peers_cohort_or_roster(enrollment_case):
    c=enrollment_case; identity,headers,cid=c['author']; enroll(c)
    uid=uuid4()
    with psycopg.connect(identity[1]) as db:
        db.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,'synthetic')",(uid,f'{uid}@example.invalid'))
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'student')",(uuid4(),identity[3],uid))
    h=identity[0].post('/cohorts',json={'course_id':cid,'title':'Peers'},headers=headers).json()['id']
    assert enroll(c,student_id=str(uid),cohort_id=h).status_code==201; write(c['author'],'/publish')
    visible=roster(c,client=c['student']).json()['enrollments']; assert [r['student_id'] for r in visible]==[str(c['uid'])]
    visible=c['student'].get('/cohorts',params={'course_id':cid},headers=headers).json()['cohorts']; assert [r['id'] for r in visible]==[c['hid']]


def test_membership_cleanup_preserves_another_tenants_enrollment(enrollment_case):
    c=enrollment_case; identity,headers,cid=c['author']; enroll(c)
    with psycopg.connect(identity[1]) as db:
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'admin')",(uuid4(),identity[4],identity[2]))
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'student')",(uuid4(),identity[4],c['uid']))
    foreign={**headers,'x-tenant-id':str(identity[4])}; client=identity[0]
    cid2=client.post('/courses',json={'title':'Foreign enrollment'},headers=foreign).json()['id']
    hid2=client.post('/cohorts',json={'course_id':cid2,'title':'Foreign cohort'},headers=foreign).json()['id']
    eid2=client.post('/enrollments',json={'course_id':cid2,'cohort_id':hid2,'student_id':str(c['uid'])},headers=foreign).json()['id']
    assert client.post(f'/auth/memberships/{c["uid"]}/role',json={'role':'teacher'},headers=headers).status_code==200
    assert roster(c).json()['enrollments']==[]
    rows=client.get('/enrollments',params={'course_id':cid2},headers=foreign).json()['enrollments']; assert [r['id'] for r in rows]==[eid2]


@pytest.mark.parametrize('operation',['create','reactivate'])
def test_concurrent_membership_change_serializes_with_api_activation(enrollment_case,operation):
    import time
    c=enrollment_case; identity,headers,cid=c['author']
    eid=None
    if operation=='reactivate': eid=enroll(c).json()['id']; assert action(c,eid,'revoke').status_code==200
    def activate():
        with TestClient(app,base_url='https://testserver') as client:
            client.cookies.update(identity[0].cookies)
            if operation=='create': return client.post('/enrollments',json={'course_id':cid,'cohort_id':c['hid'],'student_id':str(c['uid'])},headers=headers).status_code
            return client.post(f'/enrollments/{eid}/reactivate',json={'version':2,'cohort_id':c['hid']},headers=headers).status_code
    with psycopg.connect(identity[1]) as holder,ThreadPoolExecutor(max_workers=1) as pool:
        holder.execute('SET LOCAL lock_timeout=\'5s\'')
        holder.execute("UPDATE memberships SET role='teacher' WHERE tenant_id=%s AND user_id=%s",(identity[3],c['uid']))
        pending=pool.submit(activate)
        try:
            deadline=time.monotonic()+3; blocked=False
            while time.monotonic()<deadline:
                with psycopg.connect(identity[1]) as probe:
                    blocked=bool(probe.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT enrollment_lock_student%%'").fetchone())
                if blocked: break
                time.sleep(.03)
            assert blocked,'Expected membership lock was not observed'
        finally: holder.commit()
        assert pending.result(timeout=5)==409
    assert roster(c).json()['enrollments']==[]


def test_insert_then_role_update_revokes_after_waiting_for_student_lock(enrollment_case):
    from threading import Event
    from test_course_review import wait_for_lock
    c=enrollment_case; identity,headers,cid=c['author']; started=Event(); name='lms03_role_'+uuid4().hex[:12]
    def role_change():
        with psycopg.connect(identity[1],application_name=name,options='-c lock_timeout=5000') as db:
            started.set();db.execute("UPDATE memberships SET role='teacher' WHERE tenant_id=%s AND user_id=%s",(identity[3],c['uid']))
    with transaction() as holder,ThreadPoolExecutor(max_workers=1) as pool:
        session_context(holder,token_digest(identity[0].cookies['maaher_session']));tenant_context(holder,identity[3])
        holder.execute('INSERT INTO enrollments(id,tenant_id,course_id,cohort_id,student_id) VALUES(%s,%s,%s,%s,%s)',(uuid4(),identity[3],cid,c['hid'],c['uid']))
        pending=pool.submit(role_change)
        try: assert started.wait(2);wait_for_lock(identity[1],name)
        finally: holder.commit()
        pending.result(timeout=6)
    assert roster(c).json()['enrollments']==[] and len(roster(c,'revoked').json()['enrollments'])==1


def test_roster_pagination_has_no_duplicates(enrollment_case):
    c=enrollment_case; identity,headers,cid=c['author']; enroll(c)
    for i in range(2):
        uid=uuid4()
        with psycopg.connect(identity[1]) as db:
            db.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,'synthetic')",(uid,f'{uid}@example.invalid'))
            db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'student')",(uuid4(),identity[3],uid))
        assert enroll(c,student_id=str(uid)).status_code==201
    first=roster(c,limit=2).json(); assert len(first['enrollments'])==2 and first['next_cursor']
    second=roster(c,limit=2,after=first['next_cursor']).json();assert len(second['enrollments'])==1 and second['next_cursor'] is None
    assert len({r['id'] for r in first['enrollments']+second['enrollments']})==3


def test_enrollment_column_grants_and_foreign_keys(enrollment_case):
    c=enrollment_case;identity,headers,cid=c['author'];eid=enroll(c).json()['id']
    with transaction() as db:
        session_context(db,token_digest(identity[0].cookies['maaher_session']));tenant_context(db,identity[3])
        assert not db.execute("SELECT has_column_privilege(current_user,'enrollments','student_id','UPDATE') AS ok").fetchone()['ok']
        assert not db.execute("SELECT has_column_privilege(current_user,'enrollments','tenant_id','UPDATE') AS ok").fetchone()['ok']
        assert not db.execute("SELECT has_column_privilege(current_user,'cohorts','course_id','UPDATE') AS ok").fetchone()['ok']
    other=identity[0].post('/courses',json={'title':'Parent FK'},headers=headers).json()['id']
    with pytest.raises(psycopg.errors.ForeignKeyViolation),psycopg.connect(identity[1]) as db:
        db.execute("INSERT INTO enrollments(id,tenant_id,course_id,cohort_id,student_id,status) VALUES(%s,%s,%s,%s,%s,'revoked')",(uuid4(),identity[3],other,c['hid'],c['uid']))


@pytest.mark.parametrize('operation',['helper','insert'])
def test_runtime_checks_tenant_before_locking_foreign_rows(enrollment_case,operation):
    c=enrollment_case;identity,headers,cid=c['author'];foreign_course,foreign_cohort=uuid4(),uuid4()
    with psycopg.connect(identity[1]) as db:
        foreign=db.execute('SELECT user_id FROM memberships WHERE tenant_id=%s',(identity[4],)).fetchone()[0]
        db.execute("INSERT INTO courses(id,tenant_id,owner_id,title) VALUES(%s,%s,%s,'Foreign lock fixture')",(foreign_course,identity[4],foreign))
        db.execute("INSERT INTO cohorts(id,tenant_id,course_id,title) VALUES(%s,%s,%s,'Foreign cohort')",(foreign_cohort,identity[4],foreign_course))
    with psycopg.connect(identity[1]) as holder:
        holder.execute("UPDATE users SET status='disabled' WHERE id=%s",(foreign,))
        holder.execute("UPDATE courses SET state='archived' WHERE id=%s",(foreign_course,))
        with transaction() as runtime:
            session_context(runtime,token_digest(identity[0].cookies['maaher_session']));tenant_context(runtime,identity[3])
            runtime.execute("SET LOCAL lock_timeout='200ms'")
            if operation=='helper':
                assert runtime.execute('SELECT enrollment_lock_student(%s,%s) AS ok',(identity[3],foreign)).fetchone()['ok'] is False
            else:
                with pytest.raises(psycopg.errors.InsufficientPrivilege,match='admin enrollment mutation required'):
                    runtime.execute('INSERT INTO enrollments(id,tenant_id,course_id,cohort_id,student_id) VALUES(%s,%s,%s,%s,%s)',(uuid4(),identity[4],foreign_course,foreign_cohort,foreign))
                runtime.rollback()
        holder.rollback()
