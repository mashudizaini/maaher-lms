"""Own revision-aware lesson completion, navigation and authorization."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import os
import psycopg
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import transaction,session_context,tenant_context,user_context
from app.security import token_digest
from test_enrollment import enrollment_case,enroll,action
from test_courses import author,detail,filled,write


def path(c,suffix=''):
    return f'/learning/courses/{c["author"][2]}/modules/{c["mid"]}/lessons/{c["lid"]}'+suffix


def mark(c,revision=1,complete=True,client=None,**extra):
    identity,headers,_=c['author']
    return (client or c['student']).post(path(c,'/complete' if complete else '/uncomplete'),json={'revision':revision,**extra},headers=headers)


def outline(c):return c['student'].get('/learning/courses/'+c['author'][2],headers=c['author'][1])


@pytest.fixture
def learning(enrollment_case):
    c=enrollment_case
    response=enroll(c);assert response.status_code==201;c['eid']=response.json()['id']
    assert write(c['author'],'/publish').status_code==200
    return c


def test_completion_idempotent_reload_and_uncomplete(learning):
    c=learning
    assert outline(c).json()['progress']=={'completed':0,'total':1}
    assert mark(c).status_code==200
    assert mark(c).status_code==200
    assert outline(c).json()['progress']=={'completed':1,'total':1}
    with TestClient(app,base_url='https://testserver') as restarted:
        restarted.cookies.update(c['student'].cookies)
        assert restarted.get(path(c),headers=c['author'][1]).json()['completed'] is True
    assert mark(c,complete=False).status_code==200
    assert mark(c,complete=False).status_code==200
    assert outline(c).json()['progress']['completed']==0
    with psycopg.connect(c['author'][0][1]) as db:
        assert db.execute("SELECT count(*) FROM audit_events WHERE target_id=%s AND action='lesson.completed'",(c['lid'],)).fetchone()[0]==1
        assert db.execute("SELECT count(*) FROM audit_events WHERE target_id=%s AND action='lesson.uncompleted'",(c['lid'],)).fetchone()[0]==1


def test_material_revision_requires_fresh_completion(learning):
    c=learning;assert mark(c).status_code==200
    response=write(c['author'],f'/modules/{c["mid"]}/lessons/{c["lid"]}',title='Updated',content='New material')
    assert response.status_code==200
    assert mark(c).status_code==404
    assert write(c['author'],'/publish').status_code==200
    l=c['student'].get(path(c),headers=c['author'][1]).json()
    assert l['revision']==2 and not l['completed'] and l['needs_review']
    assert mark(c).status_code==409
    assert mark(c,2).status_code==200
    assert outline(c).json()['progress']['completed']==1


def test_title_only_change_and_explicit_reactivation_keep_current_completion(learning):
    c=learning;mark(c)
    write(c['author'],f'/modules/{c["mid"]}/lessons/{c["lid"]}',title='New title',content='# Halo\n\n```python\nprint("Halo")\n```',resources=[{'label':'Dokumentasi Python','url':'https://docs.python.org/3/'}])
    write(c['author'],'/publish')
    assert outline(c).json()['progress']['completed']==1
    assert action(c,c['eid'],'revoke').status_code==200
    assert mark(c).status_code==404
    assert outline(c).status_code==404
    assert action(c,c['eid'],'reactivate',2,cohort_id=c['hid']).status_code==200
    assert outline(c).json()['progress']['completed']==1


def test_ordered_previous_next_and_resume_across_modules(learning):
    c=learning;mid=write(c['author'],'/modules',title='Next module').json()['id']
    lid=write(c['author'],f'/modules/{mid}/lessons',title='Next lesson',content='Continue').json()['id']
    write(c['author'],'/publish')
    first=c['student'].get(path(c),headers=c['author'][1]).json()
    assert first['previous'] is None and first['next']['id']==lid
    mark(c)
    assert outline(c).json()['resume']=={'id':lid,'module_id':mid}
    next_path=f'/learning/courses/{c["author"][2]}/modules/{mid}/lessons/{lid}'
    last=c['student'].get(next_path,headers=c['author'][1]).json()
    assert last['previous']['id']==c['lid'] and last['next'] is None


def test_foreign_and_extra_authority_input_denied(learning):
    c=learning
    assert mark(c,tenant_id=str(c['author'][0][4])).status_code==422
    assert mark(c,student_id=str(uuid4())).status_code==422
    assert mark(c,0).status_code==422
    assert mark(c,client=c['author'][0][0]).status_code==403
    headers={**c['author'][1],'x-tenant-id':str(c['author'][0][4])}
    assert c['student'].post(path(c,'/complete'),json={'revision':1},headers=headers).status_code==403
    with TestClient(app,base_url='https://testserver') as anon:
        assert anon.post(path(c,'/complete'),json={'revision':1},headers=c['author'][1]).status_code==401
    assert mark(c).status_code==200


def test_student_sql_cannot_access_other_students_progress(learning):
    c=learning;identity,headers,cid=c['author'];mark(c)
    with transaction() as db:
        session_context(db,token_digest(c['student'].cookies['maaher_session']));tenant_context(db,identity[3])
        assert len(db.execute('SELECT lesson_id FROM lesson_progress').fetchall())==1
        user_context(db,identity[2]);tenant_context(db,identity[4])
        assert db.execute('SELECT lesson_id FROM lesson_progress').fetchall()==[]
    with transaction() as db:
        session_context(db,token_digest(identity[0].cookies['maaher_session']));tenant_context(db,identity[3])
        assert db.execute('SELECT lesson_id FROM lesson_progress').fetchall()==[]
    with transaction() as db:
        tenant_context(db,identity[3]);user_context(db,c['uid'])
        assert db.execute('SELECT lesson_id FROM lesson_progress').fetchall()==[]


def test_concurrent_complete_is_idempotent(learning):
    c=learning
    def save(_):
        with TestClient(app,base_url='https://testserver') as client:
            client.cookies.update(c['student'].cookies);return mark(c,client=client).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:assert list(pool.map(save,range(2)))==[200,200]
    with psycopg.connect(c['author'][0][1]) as db:
        assert db.execute('SELECT count(*) FROM lesson_progress WHERE enrollment_id=%s',(c['eid'],)).fetchone()[0]==1


def test_learning_budget_and_missing_origin(learning):
    c=learning;identity,headers,cid=c['author']
    assert c['student'].post(path(c,'/complete'),json={'revision':1},headers={'x-tenant-id':str(identity[3])}).status_code==403
    outline(c)
    with psycopg.connect(identity[1]) as db:db.execute('UPDATE learning_request_limits SET attempts=120,window_start=now() WHERE tenant_id=%s AND user_id=%s',(identity[3],c['uid']))
    limited=outline(c);assert limited.status_code==429 and limited.headers['retry-after']=='60'


def test_sql_revision_and_cross_owner_completion_constraints(learning):
    c=learning;identity,headers,cid=c['author']
    with pytest.raises(psycopg.errors.InsufficientPrivilege),transaction() as db:
        session_context(db,token_digest(c['student'].cookies['maaher_session']));tenant_context(db,identity[3])
        db.execute('INSERT INTO lesson_progress(tenant_id,course_id,enrollment_id,student_id,lesson_id,lesson_revision) VALUES(%s,%s,%s,%s,%s,999)',(identity[3],cid,c['eid'],c['uid'],c['lid']))
    with pytest.raises(psycopg.errors.InsufficientPrivilege),transaction() as db:
        session_context(db,token_digest(c['student'].cookies['maaher_session']));tenant_context(db,identity[3])
        db.execute('INSERT INTO lesson_progress(tenant_id,course_id,enrollment_id,student_id,lesson_id,lesson_revision) VALUES(%s,%s,%s,%s,%s,1)',(identity[3],cid,c['eid'],identity[2],c['lid']))
    with psycopg.connect(identity[1]) as db:
        db.execute('UPDATE course_lessons SET content=%s WHERE id=%s',('Owner SQL change',c['lid']))
        assert db.execute('SELECT revision FROM course_lessons WHERE id=%s',(c['lid'],)).fetchone()[0]==2
    assert mark(c).status_code==409
