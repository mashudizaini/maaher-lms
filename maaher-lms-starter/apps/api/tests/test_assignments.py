"""Version/tenant boundaries, immutable snapshots, deadlines and concurrent attempts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import psycopg
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import transaction,session_context,tenant_context,user_context
from app.security import token_digest
from test_learning import learning
from test_enrollment import enrollment_case,enroll,action
from test_courses import author,write
from test_course_review import teacher_account


def content(**extra):return {'title':'Latihan Python','instructions':'Buat fungsi penjumlahan.','language':'python','starter_code':'def add(a, b):\n    pass','rubric':[{'criterion':'Hasil benar','max_points':70},{'criterion':'Keterbacaan','max_points':30}],'max_attempts':3,'allow_late':False,**extra}


def create(c,**extra):
    identity,headers,cid=c['author']
    return identity[0].post('/assignments',json={'course_id':cid,'lesson_id':c['lid'],**content(**extra)},headers=headers)


def staff(c,suffix='',body=None,method='get'):
    identity,headers,_=c['author'];path='/assignments/'+c['aid']+suffix
    return identity[0].get(path,headers=headers) if method=='get' else identity[0].post(path,json=body,headers=headers)


def edit(c,**extra):return staff(c,body={'version':staff(c).json()['version'],**content(**extra)},method='post')


def transition(c,operation):return staff(c,'/'+operation,{'version':staff(c).json()['version']},'post')


def get(c):return c['student'].get('/work/assignments/'+c['aid'],headers=c['author'][1])


def draft(c,**extra):
    current=get(c).json();d=current['draft']
    return c['student'].post('/work/assignments/'+c['aid']+'/draft',json={'version_id':current['published']['id'],'revision':d['revision'] if d else 0,'source_code':'print("Halo")','note':'Jawaban saya',**extra},headers=c['author'][1])


def submit(c,**extra):
    d=get(c).json()['draft']
    return c['student'].post('/work/assignments/'+c['aid']+'/submit',json={'version_id':d['version_id'],'draft_revision':d['revision'],'request_id':str(uuid4()),**extra},headers=c['author'][1])


@pytest.fixture
def assignment(learning):
    c=learning;r=create(c);assert r.status_code==201,r.text;c['aid']=r.json()['id'];assert transition(c,'publish').status_code==200;return c


def test_assignment_draft_publish_pointer_and_immutable_versions(assignment):
    c=assignment;first=get(c).json()['published'];assert draft(c).status_code==200
    assert edit(c,title='Latihan versi dua',max_attempts=4).status_code==200
    assert get(c).json()['published']['id']==first['id']
    assert staff(c).json()['draft']['version_no']==2
    assert transition(c,'publish').status_code==200
    assert get(c).json()['published']['title']=='Latihan versi dua'
    assert get(c).json()['draft']['version_id']==first['id']
    assert submit(c).status_code==409
    assert draft(c,source_code='Versi dua').status_code==200
    assert submit(c).status_code==201
    assert len(staff(c,'/versions').json()['versions'])==2


def test_submission_snapshot_reload_retry_and_history(assignment):
    c=assignment;assert draft(c,source_code='<script>alert(1)</script>').status_code==200
    key=str(uuid4());r=submit(c,request_id=key);assert r.status_code==201,r.text;sid=r.json()['id'];assert r.json()['attempt_no']==1
    assert submit(c,request_id=key).json()['id']==sid
    assert draft(c,source_code='Changed draft').status_code==200
    assert submit(c,request_id=key).status_code==409
    with TestClient(app,base_url='https://testserver') as restarted:
        restarted.cookies.update(c['student'].cookies)
        snapshot=restarted.get('/work/submissions/'+sid,headers=c['author'][1]).json()
        assert snapshot['source_code']=='<script>alert(1)</script>' and snapshot['assignment_version']['version_no']==1
        assert 'content_attestation' not in snapshot['assignment_version']
    history=c['student'].get('/work/submissions',params={'course_id':c['author'][2]},headers=c['author'][1]).json()
    assert len(history['submissions'])==1 and 'source_code' not in history['submissions'][0]
    assert c['author'][0][0].get('/assignment-submissions/'+sid,headers=c['author'][1]).status_code==200


def test_stale_draft_and_stale_author_version_do_not_overwrite(assignment):
    c=assignment;assert draft(c).json()['revision']==1
    assert draft(c,revision=0,source_code='stale').status_code==409
    assert draft(c,revision=9).status_code==409
    assert get(c).json()['draft']['source_code']=='print("Halo")'
    assert staff(c,body={'version':1,**content()},method='post').status_code==409


@pytest.mark.parametrize('kind',['unpublish','archive'])
def test_task_visibility_and_history_survive_explicit_restore(assignment,kind):
    c=assignment;draft(c);sid=submit(c).json()['id'];transition(c,kind)
    assert get(c).status_code==404
    assert c['student'].get('/work/submissions/'+sid,headers=c['author'][1]).status_code==200
    if kind=='archive':assert transition(c,'restore').status_code==200
    assert get(c).status_code==404
    assert transition(c,'publish').status_code==200;assert get(c).json()['attempts']==1


@pytest.mark.parametrize('late,expected',[(False,409),(True,201)])
def test_deadline_server_clock_and_late_status(assignment,late,expected):
    c=assignment;past=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
    edit(c,due_at=past,allow_late=late);transition(c,'publish');draft(c);response=submit(c)
    assert response.status_code==expected,response.text
    if late:
        value=response.json();assert value['status']=='late'
        assert datetime.fromisoformat(value['submitted_at'].replace('Z','+00:00'))>datetime.fromisoformat(past)


def test_attempts_across_versions_and_idempotent_concurrent_retry(assignment):
    c=assignment;edit(c,max_attempts=1);transition(c,'publish');draft(c)
    d=get(c).json()['draft'];key=str(uuid4());body={'version_id':d['version_id'],'draft_revision':d['revision'],'request_id':key}
    def send(_):
        with TestClient(app,base_url='https://testserver') as client:
            client.cookies.update(c['student'].cookies);return client.post('/work/assignments/'+c['aid']+'/submit',json=body,headers=c['author'][1])
    with ThreadPoolExecutor(max_workers=4) as pool:responses=list(pool.map(send,range(4)))
    assert {r.status_code for r in responses}=={201};assert len({r.json()['id'] for r in responses})==1
    assert submit(c).status_code==409
    edit(c,title='Versi baru tetap satu percobaan',max_attempts=1);transition(c,'publish');draft(c)
    assert submit(c).status_code==409


def test_distinct_concurrent_attempts_never_exceed_cap(assignment):
    c=assignment;edit(c,max_attempts=2);transition(c,'publish');draft(c)
    d=get(c).json()['draft']
    def send(_):
        with TestClient(app,base_url='https://testserver') as client:
            client.cookies.update(c['student'].cookies);return client.post('/work/assignments/'+c['aid']+'/submit',json={'version_id':d['version_id'],'draft_revision':d['revision'],'request_id':str(uuid4())},headers=c['author'][1])
    with ThreadPoolExecutor(max_workers=6) as pool:responses=list(pool.map(send,range(6)))
    assert sorted(r.status_code for r in responses)==[201,201,409,409,409,409]
    assert sorted(r.json()['attempt_no'] for r in responses if r.status_code==201)==[1,2]


@pytest.mark.parametrize('field,value',[('rubric',[{'criterion':'Bad total','max_points':99}]),('due_at','2026-11-11T10:00:00'),('language','shell'),('max_attempts',21),('instructions','[bad](javascript:alert(1))'),('starter_code','\x00'),('instructions','\x01'*22000)])
def test_invalid_assignment_input(assignment,field,value):
    assert edit(assignment,**{field:value}).status_code==422


def test_revoke_and_course_unpublish_cut_every_work_route(assignment):
    c=assignment;draft(c);sid=submit(c).json()['id'];write(c['author'],'/unpublish')
    assert get(c).status_code==404
    assert c['student'].get('/work/submissions/'+sid,headers=c['author'][1]).status_code==404
    write(c['author'],'/publish');assert get(c).status_code==200
    assert action(c,c['eid'],'revoke').status_code==200
    assert get(c).status_code==404
    assert c['student'].get('/work/submissions/'+sid,headers=c['author'][1]).status_code==404
    action(c,c['eid'],'reactivate',2,cohort_id=c['hid']);assert get(c).status_code==200


def test_teacher_assignment_and_student_role_boundaries(assignment,teacher_account):
    c=assignment;uid,teacher=teacher_account;headers=c['author'][1]
    assert teacher.get('/assignments/'+c['aid'],headers=headers).status_code==404
    write(c['author'],'/teachers',user_id=str(uid),assigned=True)
    assert teacher.get('/assignments/'+c['aid'],headers=headers).status_code==200
    assert teacher.get('/work/assignments/'+c['aid'],headers=headers).status_code==403
    assert c['student'].get('/assignments/'+c['aid'],headers=headers).status_code==403
    write(c['author'],'/teachers',user_id=str(uid),assigned=False)
    assert teacher.get('/assignments/'+c['aid'],headers=headers).status_code==404


def test_direct_runtime_sql_snapshot_and_immutable_grants(assignment):
    c=assignment;identity,headers,cid=c['author'];draft(c,source_code='real draft');d=get(c).json()['draft']
    with transaction() as db:
        session_context(db,token_digest(c['student'].cookies['maaher_session']));tenant_context(db,identity[3])
        r=db.execute('''INSERT INTO submissions(id,tenant_id,course_id,assignment_id,enrollment_id,student_id,version_id,draft_revision,request_id,attempt_no,source_code,note,submitted_at,status)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,20,'forged','forged','2000-01-01','late') RETURNING id,attempt_no,source_code,note,submitted_at,status''',
          (uuid4(),identity[3],cid,c['aid'],c['eid'],c['uid'],d['version_id'],d['revision'],uuid4())).fetchone()
        assert r['source_code']=='real draft' and r['attempt_no']==1 and r['status']=='submitted'
        assert r['submitted_at'].year>=2026
    for query in ('UPDATE submissions SET source_code=\'overwrite\'','DELETE FROM submissions','UPDATE assignment_versions SET title=\'overwrite\'','DELETE FROM assignment_versions'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege),transaction() as db:
            session_context(db,token_digest(c['student'].cookies['maaher_session']));tenant_context(db,identity[3]);db.execute(query)
    with pytest.raises(psycopg.errors.CheckViolation),psycopg.connect(identity[1]) as db:db.execute('UPDATE submissions SET source_code=\'owner overwrite\' WHERE id=%s',(r['id'],))
    with transaction() as db:
        session_context(db,token_digest(c['student'].cookies['maaher_session']));tenant_context(db,identity[4]);user_context(db,identity[2])
        for table in ('assignments','assignment_versions','submission_drafts','submissions'):assert db.execute('SELECT id FROM '+table if table!='submission_drafts' else 'SELECT assignment_id FROM '+table).fetchall()==[]


def test_assignment_fk_prevents_deleting_history_parent(assignment):
    c=assignment
    response=write(c['author'],f'/modules/{c["mid"]}/lessons/{c["lid"]}/delete')
    assert response.status_code==409
    assert write(c['author'],f'/modules/{c["mid"]}/delete').status_code==409
    assert get(c).status_code==200


def test_work_body_and_budget_and_extra_authority(assignment):
    c=assignment;headers=c['author'][1];identity=c['author'][0]
    assert draft(c,student_id=str(identity[2])).status_code==422
    d=get(c).json()['published']['id']
    assert c['student'].post('/work/assignments/'+c['aid']+'/draft',json={'version_id':d,'revision':0},headers={'x-tenant-id':str(identity[3])}).status_code==403
    assert c['student'].post('/work/assignments/'+c['aid']+'/draft',content=b' '*262145,headers=headers).status_code==413
    with psycopg.connect(identity[1]) as db:db.execute('UPDATE learning_request_limits SET attempts=120,window_start=now() WHERE tenant_id=%s AND user_id=%s',(identity[3],c['uid']))
    r=get(c);assert r.status_code==429 and r.headers['retry-after']=='60'


def test_peer_cannot_read_draft_submission_or_unpublished_version(assignment):
    from auth_helpers import sign_in
    from app.auth import passwords
    c=assignment;identity,headers,cid=c['author'];draft(c);sid=submit(c).json()['id'];old=get(c).json()['published']['id']
    uid=uuid4();mail=f'{uid}@example.invalid'
    with psycopg.connect(identity[1]) as db:
        db.execute('INSERT INTO users(id,email,password_hash) VALUES(%s,%s,%s)',(uid,mail,passwords.hash(identity[6])))
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'student')",(uuid4(),identity[3],uid))
    assert identity[0].post('/enrollments',json={'course_id':cid,'cohort_id':c['hid'],'student_id':str(uid)},headers=headers).status_code==201
    with TestClient(app,base_url='https://testserver') as peer:
        assert sign_in(peer,mail,identity[6]).status_code==200
        assert peer.get('/work/assignments/'+c['aid'],headers=headers).json()['draft'] is None
        assert peer.get('/work/submissions/'+sid,headers=headers).status_code==404
        assert peer.get('/work/submissions',params={'course_id':cid},headers=headers).json()['submissions']==[]
        edit(c,title='New unpublished version')
        new=staff(c).json()['draft']['id']
        with transaction() as db:
            session_context(db,token_digest(peer.cookies['maaher_session']));tenant_context(db,identity[3])
            assert db.execute('SELECT id FROM assignment_versions WHERE id=%s',(new,)).fetchall()==[]
            assert db.execute('SELECT assignment_id FROM submission_drafts').fetchall()==[]
            assert db.execute('SELECT id FROM submissions').fetchall()==[]
        transition(c,'publish')
        with transaction() as db:
            session_context(db,token_digest(peer.cookies['maaher_session']));tenant_context(db,identity[3])
            assert db.execute('SELECT id FROM assignment_versions WHERE id=%s',(old,)).fetchall()==[]
        # The original student still reads the exact old-version snapshot.
        assert c['student'].get('/work/submissions/'+sid,headers=headers).json()['assignment_version']['id']==old


def test_runtime_sql_foreign_parent_and_stale_draft_cannot_submit(assignment):
    c=assignment;identity,headers,cid=c['author'];draft(c);d=get(c).json()['draft']
    def insert(db,**override):
        data={'tenant':identity[3],'course':cid,'assignment':c['aid'],'enrollment':c['eid'],'student':c['uid'],'version':d['version_id'],'revision':d['revision'],**override}
        db.execute('''INSERT INTO submissions(id,tenant_id,course_id,assignment_id,enrollment_id,student_id,version_id,draft_revision,request_id,attempt_no,source_code,note,submitted_at,status)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,1,'','',now(),'submitted')''',(uuid4(),*data.values(),uuid4()))
    for override in ({'student':identity[2]},{'tenant':identity[4]},{'course':uuid4()},{'enrollment':uuid4()},{'version':uuid4()},{'revision':9}):
        with pytest.raises((psycopg.errors.CheckViolation,psycopg.errors.InsufficientPrivilege)),transaction() as db:
            session_context(db,token_digest(c['student'].cookies['maaher_session']));tenant_context(db,identity[3]);insert(db,**override)
    assert get(c).json()['attempts']==0


def test_deadline_offset_is_normalized_and_submission_records_version_rubric(assignment):
    c=assignment;edit(c,due_at='2099-01-02T07:30:00+07:00',rubric=[{'criterion':'Semua','max_points':100}]);transition(c,'publish');draft(c)
    sid=submit(c).json()['id'];edit(c,rubric=[{'criterion':'Beda','max_points':100}]);transition(c,'publish')
    snap=c['student'].get('/work/submissions/'+sid,headers=c['author'][1]).json()['assignment_version']
    assert datetime.fromisoformat(snap['due_at'].replace('Z','+00:00')).hour==0
    assert snap['rubric']==[{'criterion':'Semua','max_points':100}]



def test_attestation_deadline_is_independent_of_database_display_timezone():
    from app.assignments import proof_payload
    utc=datetime(2099,1,2,0,30,tzinfo=timezone.utc)
    data=content(due_at=utc)
    assert proof_payload(data)==proof_payload({**data,'due_at':utc.astimezone(timezone(timedelta(hours=7)))})



def test_concurrent_lesson_delete_and_task_create_preserve_parent_without_500(author):
    from test_courses import filled,detail
    mid,lid=filled(author);identity,headers,cid=author
    for n in range(10):
        if n:lid=write(author,'/modules/'+mid+'/lessons',title='Race lesson',content='Safe').json()['id']
        version=detail(author)['version']
        def request(kind):
            with TestClient(app,base_url='https://testserver') as client:
                client.cookies.update(identity[0].cookies)
                if kind=='task':return client.post('/assignments',json={'course_id':cid,'lesson_id':lid,**content()},headers=headers).status_code
                return client.post(f'/courses/{cid}/modules/{mid}/lessons/{lid}/delete',json={'version':version},headers=headers).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(request,['task','delete']))
        assert codes in ([201,409],[404,200],[409,200]),codes
