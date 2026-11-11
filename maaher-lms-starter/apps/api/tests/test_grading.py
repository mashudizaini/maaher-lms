"""Private grading, release/correction/withdrawal, original rubric and SQL guards."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import os,time
import psycopg,pytest
from psycopg.types.json import Jsonb
from fastapi.testclient import TestClient
from app.main import app
from app.database import transaction,session_context,tenant_context,user_context
from app.security import token_digest
from test_assignments import assignment,content,draft,submit,edit,transition
from test_learning import learning
from test_enrollment import enrollment_case,action
from test_courses import author,write
from test_course_review import teacher_account


@pytest.fixture
def grading(assignment):
    c=assignment;assert draft(c).status_code==200;r=submit(c);assert r.status_code==201;c['sid']=r.json()['id'];return c


def staff(c,client=None):return (client or c['author'][0][0]).get('/grading/submissions/'+c['sid'],headers=c['author'][1])


def visible(c):return c['student'].get('/work/submissions/'+c['sid']+'/grade',headers=c['author'][1])


def history(c,**params):return c['author'][0][0].get('/grading/submissions/'+c['sid']+'/history',params=params,headers=c['author'][1])


def save(c,client=None,**extra):
    return (client or c['author'][0][0]).post('/grading/submissions/'+c['sid']+'/draft',json={
       'version':staff(c,client).json()['version'],'scores':[{'criterion_index':0,'points':50,'comment':'Cukup'},{'criterion_index':1,'points':20}],
       'feedback':'Feedback untuk siswa','reason':'',**extra},headers=c['author'][1])


def release(c,operation='release',client=None,**extra):
    return (client or c['author'][0][0]).post('/grading/submissions/'+c['sid']+'/'+operation,json={'version':staff(c,client).json()['version'],**extra},headers=c['author'][1])


def test_private_draft_release_correction_and_withdrawal(grading):
    c=grading;assert visible(c).json()=={'state':'ungraded','grade':None}
    r=save(c);assert r.status_code==201,r.text;assert r.json()['total']==70
    assert staff(c).json()['draft']['reason']=='Penilaian awal'
    assert visible(c).json()=={'state':'ungraded','grade':None}
    assert release(c).status_code==200
    assert visible(c).json()['grade']['total']==70
    assert save(c,feedback='Privat koreksi').status_code==422
    assert save(c,feedback='Feedback koreksi',reason='Koreksi rubrik',scores=[{'criterion_index':0,'points':60},{'criterion_index':1,'points':20}]).status_code==201
    assert visible(c).json()['grade']['total']==70
    assert 'Feedback koreksi' not in visible(c).text
    assert release(c).status_code==422
    assert release(c,reason='Bagikan koreksi').status_code==200
    assert visible(c).json()['grade']['total']==80
    assert release(c,'withdraw').status_code==422
    assert release(c,'withdraw',reason='Perlu moderasi ulang').status_code==200
    assert visible(c).json()=={'state':'withdrawn','grade':None}
    assert release(c,reason='Moderasi selesai').status_code==200
    assert visible(c).json()['grade']['feedback']=='Feedback koreksi'
    events=history(c).json();assert [e['action'] for e in events['events']]==['draft_saved','released','draft_saved','released','withdrawn','released']
    assert len(events['revisions'])==2
    assert {e['actor_id'] for e in events['events']}=={str(c['author'][0][2])}


def test_original_submission_rubric_survives_new_task_version(grading):
    c=grading;assert edit(c,rubric=[{'criterion':'Baru','max_points':100}]).status_code==200;transition(c,'publish')
    assert staff(c).json()['submission']['assignment_version']['rubric'][0]['max_points']==70
    assert save(c,scores=[{'criterion_index':0,'points':100}]).status_code==422
    assert save(c).status_code==201;release(c)
    assert visible(c).json()['grade']['total']==70


@pytest.mark.parametrize('extra',[
 {'scores':[]},{'scores':[{'criterion_index':0,'points':70}]},
 {'scores':[{'criterion_index':0,'points':71},{'criterion_index':1,'points':20}]},
 {'scores':[{'criterion_index':0,'points':20},{'criterion_index':0,'points':20}]},
 {'scores':[{'criterion_index':0,'points':True},{'criterion_index':1,'points':20}]},
 {'scores':[{'criterion_index':0,'points':1.5},{'criterion_index':1,'points':20}]},
 {'scores':[{'criterion_index':9,'points':10},{'criterion_index':1,'points':20}]},
 {'scores':[{'criterion_index':0,'points':-1},{'criterion_index':1,'points':20}]},
 {'feedback':'x'*6001},{'feedback':'\x00'},{'reason':'x'*1001},
 {'reviewer_id':'00000000-0000-0000-0000-000000000001'},{'total':100},
 {'tenant_id':'00000000-0000-0000-0000-000000000001'}])
def test_invalid_scores_and_authority_fields_do_not_create_grade(grading,extra):
    c=grading;r=save(c,**extra);assert r.status_code==422,r.text
    assert staff(c).json()['version']==0
    assert history(c).json()['events']==[]


def test_zero_grade_and_plaintext_feedback_are_preserved(grading):
    c=grading;feedback='<script>alert("never")</script>\n😀 学習'
    assert save(c,scores=[{'criterion_index':1,'points':0},{'criterion_index':0,'points':0}],feedback=feedback).status_code==201
    release(c);pub=visible(c).json()['grade'];assert pub['total']==0 and pub['feedback']==feedback
    assert [score['criterion_index'] for score in pub['scores']]==[0,1]


def test_teacher_assigned_course_only_and_role_revocation(grading,teacher_account):
    c=grading;uid,teacher=teacher_account
    assert staff(c,teacher).status_code==404
    write(c['author'],'/teachers',user_id=str(uid),assigned=True)
    assert save(c,teacher).status_code==201
    assert release(c,client=teacher).status_code==200
    assert staff(c).json()['draft']['reviewer_id']==str(uid)
    write(c['author'],'/teachers',user_id=str(uid),assigned=False)
    assert staff(c,teacher).status_code==404
    assert visible(c).json()['grade']['total']==70


def test_student_sql_cannot_read_private_revisions_events_or_draft_values(grading):
    c=grading;identity=c['author'][0];save(c,reason='Privat staf')
    def check(expected):
        with transaction() as db:
            session_context(db,token_digest(c['student'].cookies['maaher_session']));tenant_context(db,identity[3])
            for table in ('grading_entries','grade_revisions','grading_events'):assert db.execute('SELECT * FROM '+table).fetchall()==[]
            rows=db.execute('SELECT * FROM grade_publications').fetchall()
            assert len(rows)==expected
            return rows
    check(0);release(c)
    row=check(1)[0];assert row['total']==70 and 'reason' not in row and 'reviewer_id' not in row
    release(c,'withdraw',reason='Privat penarikan');row=check(1)[0]
    assert row['feedback'] is None and row['scores'] is None and row['total'] is None and row['revision_id'] is None
    with transaction() as db:
        session_context(db,token_digest(c['student'].cookies['maaher_session']));tenant_context(db,identity[4]);user_context(db,identity[2])
        assert db.execute('SELECT * FROM grade_publications').fetchall()==[]
    assert c['student'].get('/grading/submissions/'+c['sid'],headers=c['author'][1]).status_code==403


def test_peer_cannot_read_published_grade(grading):
    from auth_helpers import sign_in
    from app.auth import passwords
    c=grading;identity,headers,cid=c['author'];save(c);release(c);uid=uuid4();mail=f'{uid}@example.invalid'
    with psycopg.connect(identity[1]) as db:
        db.execute('INSERT INTO users(id,email,password_hash) VALUES(%s,%s,%s)',(uid,mail,passwords.hash(identity[6])))
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'student')",(uuid4(),identity[3],uid))
    assert identity[0].post('/enrollments',json={'course_id':cid,'cohort_id':c['hid'],'student_id':str(uid)},headers=headers).status_code==201
    with TestClient(app,base_url='https://testserver') as peer:
        assert sign_in(peer,mail,identity[6]).status_code==200
        assert peer.get('/work/submissions/'+c['sid']+'/grade',headers=headers).status_code==404
        with transaction() as db:
            session_context(db,token_digest(peer.cookies['maaher_session']));tenant_context(db,identity[3])
            assert db.execute('SELECT * FROM grade_publications').fetchall()==[]


def test_course_pause_and_enrollment_revoke_close_student_grade_access(grading):
    c=grading;save(c);release(c);assert visible(c).status_code==200
    write(c['author'],'/unpublish');assert visible(c).status_code==404
    write(c['author'],'/publish');assert visible(c).status_code==200
    action(c,c['eid'],'revoke');assert visible(c).status_code==404
    action(c,c['eid'],'reactivate',2,cohort_id=c['hid']);assert visible(c).json()['grade']['total']==70
    write(c['author'],'/archive');assert visible(c).status_code==404
    assert save(c,reason='Archived').status_code==409
    assert staff(c).json()['draft']['total']==70


def test_concurrent_first_grade_and_revision_use_one_version(grading):
    c=grading
    def post(_):
        with TestClient(app,base_url='https://testserver') as client:
            client.cookies.update(c['author'][0][0].cookies)
            return client.post('/grading/submissions/'+c['sid']+'/draft',headers=c['author'][1],json={'version':0,'scores':[{'criterion_index':0,'points':50},{'criterion_index':1,'points':20}]}).status_code
    with ThreadPoolExecutor(max_workers=4) as pool:assert sorted(pool.map(post,range(4)))==[201,409,409,409]
    assert len(history(c).json()['events'])==1
    assert save(c,version=0,feedback='stale').status_code==409
    assert release(c,version=2).status_code==409


def test_runtime_sql_cannot_forge_totals_actor_time_or_public_snapshot(grading):
    c=grading;identity,headers,cid=c['author'];save(c)
    with transaction() as db:
        session_context(db,token_digest(identity[0].cookies['maaher_session']));tenant_context(db,identity[3])
        row=db.execute('''INSERT INTO grade_revisions(id,tenant_id,course_id,submission_id,entry_version,revision_no,scores,total,feedback,reason,reviewer_id,created_at)
          VALUES(%s,%s,%s,%s,2,99,%s,100,'SQL feedback','SQL correction',%s,'2000-01-01') RETURNING total,reviewer_id,revision_no,created_at''',
          (uuid4(),identity[3],cid,c['sid'],Jsonb([{'criterion_index':0,'points':1},{'criterion_index':1,'points':2}]),c['uid'])).fetchone()
        assert row['total']==3 and row['reviewer_id']==identity[2] and row['revision_no']==2 and row['created_at'].year>=2026
    assert release(c).status_code==200
    with pytest.raises(psycopg.errors.CheckViolation),transaction() as db:
        session_context(db,token_digest(identity[0].cookies['maaher_session']));tenant_context(db,identity[3])
        db.execute("UPDATE grade_publications SET total=100,feedback='Forged' WHERE submission_id=%s",(c['sid'],))
    assert visible(c).json()['grade']['total']==3
    for table in ('grade_revisions','grading_events'):
        for operation in ('UPDATE','DELETE','TRUNCATE'):
            query=f"UPDATE {table} SET created_at=now()" if operation=='UPDATE' else f'DELETE FROM {table}' if operation=='DELETE' else f'TRUNCATE {table}'
            with pytest.raises(psycopg.errors.InsufficientPrivilege),transaction() as db:
                session_context(db,token_digest(identity[0].cookies['maaher_session']));tenant_context(db,identity[3]);db.execute(query)
        with pytest.raises(psycopg.errors.CheckViolation),psycopg.connect(identity[1]) as db:db.execute('DELETE FROM '+table+' WHERE submission_id=%s',(c['sid'],))


def test_grading_read_budget_origin_body_and_private_authority(grading):
    c=grading;identity,headers,cid=c['author']
    r=identity[0].post('/grading/submissions/'+c['sid']+'/draft',json={'version':0},headers={'x-tenant-id':str(identity[3])});assert r.status_code==403
    assert identity[0].post('/grading/submissions/'+c['sid']+'/draft',content=b' '*262145,headers=headers).status_code==413
    assert staff(c).status_code==200
    with psycopg.connect(identity[1]) as db:db.execute('UPDATE grading_read_limits SET attempts=180,window_start=now() WHERE tenant_id=%s AND user_id=%s',(identity[3],identity[2]))
    response=staff(c);assert response.status_code==429 and response.headers['retry-after']=='60'


def test_lost_teacher_authority_while_waiting_cannot_save(grading,teacher_account):
    c=grading;identity,headers,cid=c['author'];uid,teacher=teacher_account;write(c['author'],'/teachers',user_id=str(uid),assigned=True);save(c)
    with psycopg.connect(identity[1]) as lock:
        lock.execute('SELECT submission_id FROM grading_entries WHERE submission_id=%s FOR UPDATE',(c['sid'],))
        def post():
            with TestClient(app,base_url='https://testserver') as client:
                client.cookies.update(teacher.cookies)
                return client.post('/grading/submissions/'+c['sid']+'/draft',headers=headers,json={'version':1,'scores':[{'criterion_index':0,'points':50},{'criterion_index':1,'points':20}]}).status_code
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(post);until=time.monotonic()+5
            while True:
                with psycopg.connect(identity[1]) as monitor:
                    waiting=monitor.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND wait_event_type='Lock' AND query LIKE '%grading%'").fetchone()
                if waiting:break
                if time.monotonic()>=until:
                    lock.rollback();pytest.fail('Expected grading lock wait was not observed')
                time.sleep(.02)
            with psycopg.connect(identity[1]) as owner:owner.execute('DELETE FROM courses_teachers WHERE tenant_id=%s AND course_id=%s AND user_id=%s',(identity[3],cid,uid))
            lock.commit();assert future.result(timeout=5) in {403,404,409}
    assert len(history(c).json()['events'])==1


def test_queue_filters_audit_and_history_pagination(grading):
    c=grading;identity,headers,cid=c['author']
    def queue(state):return identity[0].get('/grading/submissions',params={'course_id':cid,'state':state},headers=headers).json()['submissions']
    assert len(queue('ungraded'))==1
    save(c);assert queue('ungraded')==[] and len(queue('draft'))==1
    release(c);assert len(queue('released'))==1 and queue('pending')==[]
    save(c,reason='Periksa ulang');assert len(queue('pending'))==1
    for _ in range(18):assert save(c,reason='Iterasi draf').status_code==201
    first=history(c).json();assert len(first['events'])==20 and first['next_version']==20
    second=history(c,after=first['next_version']).json();assert len(second['events'])==1 and second['next_version'] is None
    with psycopg.connect(identity[1]) as db:
        audit=db.execute("SELECT action FROM audit_events WHERE tenant_id=%s AND target_id=%s AND action LIKE 'grade.%%' ORDER BY created_at,id",(identity[3],c['sid'])).fetchall()
        assert len(audit)==21


def test_grading_counter_retention_has_no_grade_read_permission(grading):
    from app.maintenance import retain
    from psycopg.rows import dict_row
    c=grading;identity=c['author'][0];staff(c);save(c)
    with psycopg.connect(identity[1]) as db:
        db.execute("UPDATE grading_read_limits SET window_start=now()-interval '2 days' WHERE tenant_id=%s AND user_id=%s",(identity[3],identity[2]))
        for table in ('grading_entries','grade_revisions','grading_events','grade_publications'):
            assert not db.execute("SELECT has_table_privilege('maaher_maintenance',%s,'SELECT')",(table,)).fetchone()[0]
        assert not db.execute("SELECT has_table_privilege('maaher_definer','grade_revisions','SELECT')").fetchone()[0]
    with psycopg.connect(os.environ['TEST_MAINTENANCE_DATABASE_URL'],row_factory=dict_row) as db:retain(db)
    with psycopg.connect(identity[1]) as db:
        assert db.execute('SELECT 1 FROM grading_read_limits WHERE tenant_id=%s AND user_id=%s',(identity[3],identity[2])).fetchall()==[]
        assert db.execute('SELECT count(*) FROM grade_revisions WHERE submission_id=%s',(c['sid'],)).fetchone()[0]==1


def test_raw_runtime_score_excess_and_student_inserts_fail(grading):
    c=grading;identity,headers,cid=c['author'];save(c)
    for actor,score in [(identity[0],99),(c['student'],10)]:
        with pytest.raises((psycopg.errors.CheckViolation,psycopg.errors.InsufficientPrivilege)),transaction() as db:
            session_context(db,token_digest(actor.cookies['maaher_session']));tenant_context(db,identity[3])
            db.execute('''INSERT INTO grade_revisions(id,tenant_id,course_id,submission_id,entry_version,revision_no,scores,total,feedback,reason,reviewer_id)
             VALUES(%s,%s,%s,%s,2,2,%s,0,'','Rejected',%s)''',(uuid4(),identity[3],cid,c['sid'],Jsonb([{'criterion_index':0,'points':score},{'criterion_index':1,'points':20}]),identity[2]))
    assert len(history(c).json()['revisions'])==1


def test_authority_denied_before_foreign_submission_lock(grading,teacher_account):
    c=grading;identity,headers,_=c['author'];_,outsider=teacher_account;save(c)
    with psycopg.connect(identity[1]) as lock:
        lock.execute('SELECT submission_id FROM grading_entries WHERE submission_id=%s FOR UPDATE',(c['sid'],))
        start=time.monotonic()
        assert outsider.post('/grading/submissions/'+c['sid']+'/draft',headers=headers,json={'version':1,'scores':[{'criterion_index':0,'points':50},{'criterion_index':1,'points':20}]}).status_code==404
        assert time.monotonic()-start<2


def test_raw_sql_authority_is_rechecked_after_entry_lock(grading,teacher_account):
    c=grading;identity,headers,cid=c['author'];uid,teacher=teacher_account;write(c['author'],'/teachers',user_id=str(uid),assigned=True);save(c)
    with psycopg.connect(identity[1]) as lock:
        lock.execute('SELECT submission_id FROM grading_entries WHERE submission_id=%s FOR UPDATE',(c['sid'],))
        def insert():
            try:
                with transaction() as db:
                    session_context(db,token_digest(teacher.cookies['maaher_session']));tenant_context(db,identity[3])
                    db.execute('''INSERT INTO grade_revisions(id,tenant_id,course_id,submission_id,entry_version,revision_no,scores,total,feedback,reason,reviewer_id)
                     VALUES(%s,%s,%s,%s,2,1,%s,0,'','Waiting actor',%s)''',(uuid4(),identity[3],cid,c['sid'],Jsonb([{'criterion_index':0,'points':1},{'criterion_index':1,'points':2}]),uid))
                return 'unexpected success'
            except psycopg.errors.InsufficientPrivilege:return 'denied'
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(insert);until=time.monotonic()+5
            while True:
                with psycopg.connect(identity[1]) as monitor:
                    waiting=monitor.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'INSERT INTO grade_revisions%%'").fetchone()
                if waiting:break
                if time.monotonic()>=until:
                    lock.rollback();pytest.fail('Expected grading lock wait was not observed')
                time.sleep(.02)
            with psycopg.connect(identity[1]) as owner:owner.execute('DELETE FROM courses_teachers WHERE tenant_id=%s AND course_id=%s AND user_id=%s',(identity[3],cid,uid))
            lock.commit();assert future.result(timeout=5)=='denied'
    assert len(history(c).json()['events'])==1


@pytest.mark.parametrize('operation',['release','withdraw'])
def test_concurrent_draft_and_visibility_change_never_release_unreviewed_revision(grading,operation):
    c=grading;save(c)
    if operation=='withdraw':release(c)
    version=staff(c).json()['version']
    def post(kind):
        with TestClient(app,base_url='https://testserver') as client:
            client.cookies.update(c['author'][0][0].cookies)
            body={'version':version,'reason':'Concurrent moderation'}
            if kind=='draft':body.update(scores=[{'criterion_index':0,'points':60},{'criterion_index':1,'points':20}],feedback='New private revision')
            return client.post('/grading/submissions/'+c['sid']+'/'+kind,json=body,headers=c['author'][1]).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(post,['draft',operation]))
    assert statuses in ([201,409],[409,200]),statuses
    result=visible(c).json()
    assert result['grade'] is None or result['grade']['total']==70
    assert 'New private revision' not in visible(c).text
    assert staff(c).json()['version']==version+1
    assert len(history(c).json()['events'])==version+1
