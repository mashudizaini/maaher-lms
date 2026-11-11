"""Reproducible F1 SQL baseline/current + current HTTP at the documented caps."""
import json
from pathlib import Path
import time
from uuid import uuid4
import psycopg
import pytest
from app.database import transaction,session_context,tenant_context,user_context
from app.security import token_digest
from test_courses import author,write
from test_enrollment import enrollment_case,enroll


def set_read_policies(owner,legacy):
    with psycopg.connect(owner) as db:
        if legacy:
            for s in (Path(__file__).parents[1]/'migrations/enrollment.sql').read_text().split('\n-- statement\n'):
                if s.startswith(('ALTER POLICY course_read','ALTER POLICY module_read','ALTER POLICY lesson_read')):db.execute(s)
            for table,prefix in [('course_modules','module'),('course_lessons','lesson')]:
                expr=f"course_can_manage(tenant_id,course_id) AND EXISTS(SELECT 1 FROM courses c WHERE c.tenant_id={table}.tenant_id AND c.id={table}.course_id AND c.state='draft')"
                db.execute(f'CREATE POLICY {prefix}_legacy_perf ON {table} FOR ALL TO maaher_runtime USING({expr}) WITH CHECK({expr})')
        else:
            for s in (Path(__file__).parents[1]/'migrations/read_scope.sql').read_text().split('\n-- statement\n'):
                if s.startswith(('ALTER POLICY course_read','ALTER POLICY module_read','ALTER POLICY lesson_read')):db.execute(s)
            for table,prefix in [('course_modules','module'),('course_lessons','lesson')]:db.execute(f'DROP POLICY IF EXISTS {prefix}_legacy_perf ON {table}')


def test_rls_caps_benchmark_and_statement_initplans(enrollment_case,tmp_path):
    c=enrollment_case;identity,headers,cid=c['author'];assert enroll(c).status_code==201;write(c['author'],'/publish')
    small=uuid4(); data={'courses':[],'modules':[],'lessons':[]}
    with psycopg.connect(identity[1]) as db:
        # Replace only this fixture's single lesson with the documented 30x50 cap.
        db.execute('DELETE FROM course_lessons WHERE tenant_id=%s AND course_id=%s',(identity[3],cid))
        db.execute('DELETE FROM course_modules WHERE tenant_id=%s AND course_id=%s',(identity[3],cid))
        for course,count in [(cid,1500),(small,100)]:
            if course!=cid:db.execute("INSERT INTO courses(id,tenant_id,owner_id,title,state) VALUES(%s,%s,%s,'Small benchmark','published')",(course,identity[3],identity[2]))
            for n in range((count+49)//50):
                mid=uuid4();data['modules'].append((mid,identity[3],course,'Module',n+1))
                for pos in range(min(50,count-n*50)):data['lessons'].append((uuid4(),identity[3],course,mid,'Lesson','Valid content',pos+1))
        for _ in range(449):
            course,mid=uuid4(),uuid4();data['courses'].append((course,identity[3],identity[2],'Catalog benchmark','published'))
            data['modules'].append((mid,identity[3],course,'Module',1));data['lessons'].append((uuid4(),identity[3],course,mid,'Lesson','Valid content',1))
        with db.cursor() as cur:
            cur.executemany('INSERT INTO courses(id,tenant_id,owner_id,title,state) VALUES(%s,%s,%s,%s,%s)',data['courses'])
            cur.executemany('INSERT INTO course_modules(id,tenant_id,course_id,title,position) VALUES(%s,%s,%s,%s,%s)',data['modules'])
            cur.executemany('INSERT INTO course_lessons(id,tenant_id,course_id,module_id,title,content,position) VALUES(%s,%s,%s,%s,%s,%s,%s)',data['lessons'])
        hid=uuid4();db.execute("INSERT INTO cohorts(id,tenant_id,course_id,title) VALUES(%s,%s,%s,'Small')",(hid,identity[3],small))
        db.execute('INSERT INTO enrollments(id,tenant_id,course_id,cohort_id,student_id) VALUES(%s,%s,%s,%s,%s)',(uuid4(),identity[3],small,hid,c['uid']))
        db.execute('ANALYZE courses');db.execute('ANALYZE course_lessons');db.execute('ANALYZE enrollments')
    metrics={}
    queries=[('student_100',c['student'],small),('student_1500',c['student'],cid),('admin_1500',identity[0],cid),('catalog_451',c['student'],None)]
    try:
        for mode in ('legacy','current'):
            set_read_policies(identity[1],mode=='legacy')
            for name,client,course in queries:
                with transaction() as db:
                    session_context(db,token_digest(client.cookies['maaher_session']));tenant_context(db,identity[3]);db.execute("SET LOCAL statement_timeout='60s'")
                    start=time.perf_counter()
                    rows=db.execute('SELECT id,title,module_id,position FROM course_lessons WHERE tenant_id=%s AND course_id=%s ORDER BY position,id',(identity[3],course)).fetchall() if course else db.execute("SELECT id,title FROM courses WHERE tenant_id=%s AND state='published' ORDER BY id LIMIT 31",(identity[3],)).fetchall()
                    metrics[mode+'_'+name+'_ms']=round((time.perf_counter()-start)*1000,2)
                    assert len(rows)==(100 if course==small else 1500 if course else 2)
        with transaction() as db:
            session_context(db,token_digest(c['student'].cookies['maaher_session']));tenant_context(db,identity[3])
            plan=db.execute('EXPLAIN (ANALYZE,FORMAT JSON,VERBOSE) SELECT id FROM course_lessons WHERE tenant_id=%s AND course_id=%s',(identity[3],cid)).fetchone()['QUERY PLAN']
            serialized=json.dumps(plan)
            assert 'InitPlan' in serialized and 'course_student_access' not in serialized and 'course_can_manage' not in serialized
        start=time.perf_counter();response=c['student'].get('/learning/courses/'+str(cid),headers=headers)
        metrics['current_http_1500_ms']=round((time.perf_counter()-start)*1000,2)
        assert response.status_code==200,response.text
        assert response.json()['progress']['total']==1500
        assert metrics['current_http_1500_ms']<2000
        assert metrics['current_student_1500_ms']<metrics['legacy_student_1500_ms']/3
    finally:set_read_policies(identity[1],False)
    report=tmp_path/'rls-performance.json';report.write_text(json.dumps(metrics,indent=2))
    print('LMS04_RLS_BENCHMARK '+json.dumps(metrics,sort_keys=True))


def test_scope_revalidates_same_connection_after_membership_revocation(enrollment_case):
    c=enrollment_case;identity,headers,cid=c['author'];enroll(c);write(c['author'],'/publish')
    with transaction() as db:
        session_context(db,token_digest(c['student'].cookies['maaher_session']));tenant_context(db,identity[3])
        db.execute('PREPARE visible_courses AS SELECT id FROM courses')
        assert len(db.execute('EXECUTE visible_courses').fetchall())==1
        with psycopg.connect(identity[1]) as owner:owner.execute("UPDATE memberships SET status='revoked' WHERE tenant_id=%s AND user_id=%s",(identity[3],c['uid']))
        assert db.execute('EXECUTE visible_courses').fetchall()==[]


def test_reader_role_is_non_bypass_read_only_and_not_assumable(enrollment_case):
    c=enrollment_case;identity=c['author'][0]
    with psycopg.connect(identity[1]) as db:
        flags=db.execute("SELECT rolsuper,rolcanlogin,rolbypassrls,rolcreaterole,rolinherit FROM pg_roles WHERE rolname='maaher_access_reader'").fetchone();assert not any(flags)
        for table in ('users','sessions','mfa_factors','lesson_progress'):
            assert not db.execute("SELECT has_table_privilege('maaher_access_reader',%s,'SELECT')",(table,)).fetchone()[0]
        for table in ('memberships','tenants','courses','courses_teachers','cohorts','enrollments'):
            assert not db.execute("SELECT has_table_privilege('maaher_access_reader',%s,'UPDATE')",(table,)).fetchone()[0]
    with pytest.raises(psycopg.errors.InsufficientPrivilege),transaction() as db:db.execute('SET ROLE maaher_access_reader')
