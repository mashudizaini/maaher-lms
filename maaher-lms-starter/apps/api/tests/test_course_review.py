"""Regression evidence for the seven LMS-02 review findings."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import os
import time
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.course_content import validate_markdown
from app.courses import Resource
from app.database import transaction, session_context, tenant_context, user_context
from app.main import app
from app.security import token_digest
from auth_helpers import sign_in
from test_courses import author, detail, filled, write


@pytest.fixture
def teacher_account(author):
    identity, headers, cid = author
    with psycopg.connect(identity[1]) as db:
        uid = db.execute('SELECT user_id FROM memberships WHERE tenant_id=%s', (identity[4],)).fetchone()[0]
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'teacher')", (uuid4(),identity[3],uid))
    with TestClient(app, base_url='https://testserver') as client:
        assert sign_in(client, f'{uid}@example.invalid', identity[6]).status_code == 200
        yield uid, client


def test_teacher_changes_preserve_publication_and_content(author, teacher_account):
    uid, _ = teacher_account; filled(author)
    assert write(author, '/publish').status_code == 200
    version = detail(author)['version']
    for assigned in (True, False):
        response = write(author, '/teachers', user_id=str(uid), assigned=assigned)
        assert response.status_code == 200 and response.json()['state'] == 'published'
        assert response.json()['version'] == version + 1
        version += 1
    assert detail(author)['modules'][0]['lessons'][0]['title'] == 'Hello Python'


def test_role_cycle_does_not_restore_old_assignments(author, teacher_account):
    uid, teacher = teacher_account; identity, headers, cid = author
    assert write(author, '/teachers', user_id=str(uid), assigned=True).status_code == 200
    assert teacher.get('/courses/' + cid, headers=headers).status_code == 200
    for role in ('student', 'teacher'):
        response = identity[0].post(f'/auth/memberships/{uid}/role', json={'role':role}, headers=headers)
        assert response.status_code == 200, response.text
    assert teacher.get('/courses/' + cid, headers=headers).status_code == 404
    assert detail(author)['teachers'] == []
    events = identity[0].get('/auth/audit', headers=headers).json()
    assert any(e['action'] == 'course.teacher_access_revoked' and e['target_id'] == cid for e in events)
    assert write(author, '/teachers', user_id=str(uid), assigned=True).status_code == 200
    assert teacher.get('/courses/' + cid, headers=headers).status_code == 200


@pytest.mark.parametrize('scope', ['membership', 'user'])
def test_reactivation_needs_fresh_assignment(author, teacher_account, scope):
    uid, teacher = teacher_account; identity, headers, cid = author
    assert write(author, '/teachers', user_id=str(uid), assigned=True).status_code == 200
    with psycopg.connect(identity[1]) as db:
        if scope == 'membership':
            db.execute("UPDATE memberships SET status='revoked' WHERE tenant_id=%s AND user_id=%s", (identity[3],uid))
            db.execute("UPDATE memberships SET status='active' WHERE tenant_id=%s AND user_id=%s", (identity[3],uid))
        else:
            db.execute("UPDATE users SET status='disabled' WHERE id=%s", (uid,))
            db.execute("UPDATE users SET status='active' WHERE id=%s", (uid,))
    assert teacher.get('/courses/' + cid, headers=headers).status_code == 404
    assert detail(author)['teachers'] == []


def test_archives_hide_course_and_children_from_teacher_but_preserve_admin_access(author, teacher_account):
    uid, teacher = teacher_account; identity, headers, cid = author; mid, lid = filled(author)
    assert write(author, '/teachers', user_id=str(uid), assigned=True).status_code == 200
    assert write(author, '/archive').status_code == 200
    assert teacher.get('/courses?archived=true', headers=headers).json()['courses'] == []
    assert teacher.get('/courses/' + cid, headers=headers).status_code == 404
    assert teacher.get(f'/courses/{cid}/modules/{mid}/lessons/{lid}', headers=headers).status_code == 404
    with transaction() as db:
        session_context(db, token_digest(teacher.cookies['maaher_session'])); tenant_context(db, identity[3])
        assert db.execute('SELECT id FROM course_modules WHERE course_id=%s', (cid,)).fetchall() == []
        assert db.execute('SELECT id FROM course_lessons WHERE course_id=%s', (cid,)).fetchall() == []
    assert identity[0].get(f'/courses/{cid}/modules/{mid}/lessons/{lid}', headers=headers).status_code == 200
    assert write(author, '/restore').status_code == 200
    assert teacher.get('/courses/' + cid, headers=headers).status_code == 200


def wait_for_lock(owner, name):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        with psycopg.connect(owner) as db:
            if db.execute("SELECT 1 FROM pg_stat_activity WHERE application_name=%s AND wait_event_type='Lock'", (name,)).fetchone():
                return
        time.sleep(.03)
    raise AssertionError('Expected assignment/membership lock was not observed')


@pytest.mark.parametrize('first', ['role', 'assignment'])
def test_assignment_and_role_changes_serialize_without_revived_access(author, teacher_account, first):
    uid, _ = teacher_account; identity, headers, cid = author
    name = 'maaher_course_race_' + uuid4().hex[:12]
    started = Event()
    def change_role():
        with psycopg.connect(identity[1], application_name=name, options='-c lock_timeout=4000 -c statement_timeout=5000') as db:
            started.set()
            db.execute("UPDATE memberships SET role='student' WHERE tenant_id=%s AND user_id=%s", (identity[3],uid))
        return 'changed'
    def assign():
        try:
            with psycopg.connect(os.environ['TEST_DATABASE_URL'], row_factory=dict_row, application_name=name,
                                 options='-c lock_timeout=4000 -c statement_timeout=5000') as db:
                session_context(db, token_digest(identity[0].cookies['maaher_session'])); tenant_context(db, identity[3])
                started.set()
                db.execute('INSERT INTO courses_teachers(tenant_id,course_id,user_id) VALUES(%s,%s,%s)', (identity[3],cid,uid))
            return 'assigned'
        except (psycopg.errors.CheckViolation, psycopg.errors.InsufficientPrivilege):
            return 'denied'
    if first == 'role':
        with psycopg.connect(identity[1]) as holder, ThreadPoolExecutor(max_workers=1) as pool:
            holder.execute("UPDATE memberships SET role='student' WHERE tenant_id=%s AND user_id=%s", (identity[3],uid))
            future = pool.submit(assign)
            try:
                assert started.wait(2); wait_for_lock(identity[1], name)
            finally:
                holder.commit()
            assert future.result(timeout=5) == 'denied'
    else:
        with transaction() as holder, ThreadPoolExecutor(max_workers=1) as pool:
            session_context(holder, token_digest(identity[0].cookies['maaher_session'])); tenant_context(holder, identity[3])
            holder.execute('INSERT INTO courses_teachers(tenant_id,course_id,user_id) VALUES(%s,%s,%s)', (identity[3],cid,uid))
            future = pool.submit(change_role)
            try:
                assert started.wait(2); wait_for_lock(identity[1], name)
            finally:
                holder.commit()
            assert future.result(timeout=5) == 'changed'
    with psycopg.connect(identity[1]) as db:
        assert db.execute('SELECT count(*) FROM courses_teachers WHERE course_id=%s AND user_id=%s', (cid,uid)).fetchone()[0] == 0


@pytest.mark.parametrize('content', [
    '[x](http://example.org)', '[x](//example.org)', '[x](/relative)', '[x](#heading)',
    '[x](mailto:a@example.org)', '[x](javascript:alert(1))', '![x](http://example.org)',
    '![x](data:image/png;base64,abc)', '[x][ref]\n\n[ref]: http://example.org', '<http://example.org>',
    '<a@example.org>', '[x](https://example.org/path\u202e)', '[x](https://exam\u200bple.org/)',
    '[x](https://example.org/%E2%80%8B)', '[x](https://example.org./path)',
])
def test_server_rejects_non_https_or_hidden_markdown_targets(content):
    with pytest.raises(ValueError): validate_markdown(content)


@pytest.mark.parametrize('content', [
    '[x](https://example.org)', '![x](https://example.org/a.png)', '<https://example.org>',
    '[x][ref]\n\n[ref]: https://example.org', '`[x](http://example.org)`',
    '```text\n[x](javascript:alert(1))\n```', 'Alamat contoh: http://example.org',
])
def test_markdown_preserves_safe_links_and_literal_code_examples(content):
    assert validate_markdown(content) == content


@pytest.mark.parametrize('url', [
    'https://example.org.', 'https://example.org./a', 'https://example.org\u3002',
    'https://example.org/a\u202eb', 'https://exam\u200bple.org', 'https://example.org/\ufeff',
    'https://example.org/%E2%80%AE', 'https://example.org/%E2%80%8B', 'https://example.org/%00',
    'https://example.org/a\u2066b', 'https://example.org/%FF',
])
def test_resource_validator_rejects_unicode_controls_and_trailing_dots(url):
    with pytest.raises((ValidationError,ValueError)): Resource(label='Doc', url=url)


def test_server_content_policy_and_legacy_publish_validation_are_atomic(author):
    identity, headers, cid = author; mid,lid = filled(author)
    before = detail(author)
    assert write(author, f'/modules/{mid}/lessons/{lid}', title='Unsafe', content='[x](http://example.org)').status_code == 422
    assert detail(author)['version'] == before['version']
    with psycopg.connect(identity[1]) as db:
        db.execute('UPDATE course_lessons SET content=%s WHERE id=%s', ('[legacy](http://example.org)',lid))
    assert write(author, '/publish').status_code == 409
    assert detail(author)['state'] == 'draft' and detail(author)['version'] == before['version']


def test_course_detail_returns_an_explicit_public_field_set(author):
    assert set(detail(author)) == {'id','title','description','state','version','created_at','updated_at','modules','teachers'}


def test_budget_commits_on_invalid_body_then_resets_without_affecting_other_actors(author, teacher_account):
    identity, headers, cid = author; _, teacher = teacher_account
    with psycopg.connect(identity[1]) as db:
        db.execute('UPDATE course_write_limits SET attempts=59,window_start=now() WHERE tenant_id=%s AND user_id=%s', (identity[3],identity[2]))
    assert identity[0].post('/courses', json={'title':'Invalid','tenant_id':str(identity[4])}, headers=headers).status_code == 422
    denied = identity[0].post('/courses', json={'title':'Over budget'}, headers=headers)
    assert denied.status_code == 429 and denied.headers['retry-after'] == '60'
    assert teacher.post(f'/courses/{cid}/modules', json={'title':'Unassigned','version':1}, headers=headers).status_code == 404
    with psycopg.connect(identity[1]) as db:
        assert db.execute('SELECT attempts FROM course_write_limits WHERE tenant_id=%s AND user_id=%s', (identity[3],identity[2])).fetchone()[0] == 61
        db.execute("UPDATE course_write_limits SET window_start=now()-interval '2 minutes' WHERE tenant_id=%s AND user_id=%s", (identity[3],identity[2]))
    assert identity[0].post('/courses', json={'title':'After window'}, headers=headers).status_code == 201


def test_last_budget_slot_is_atomic_across_connections(author):
    identity, headers, cid = author; version = detail(author)['version']
    with psycopg.connect(identity[1]) as db:
        db.execute('UPDATE course_write_limits SET attempts=59,window_start=now() WHERE tenant_id=%s AND user_id=%s', (identity[3],identity[2]))
    def save(title):
        with TestClient(app, base_url='https://testserver') as client:
            client.cookies.update(identity[0].cookies)
            return client.post('/courses/' + cid, json={'title':title,'version':version}, headers=headers).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, ['Writer one','Writer two'])) == [200,429]


def test_anonymous_and_student_writes_do_not_allocate_budget(identity):
    headers = {'origin':'https://testserver','x-tenant-id':str(identity[3])}
    assert identity[0].post('/courses', json={'title':'Anon'}, headers=headers).status_code == 401
    assert sign_in(identity[0],identity[5],identity[6]).status_code == 200
    assert identity[0].post('/courses', json={'title':'Student'}, headers=headers).status_code == 403
    with psycopg.connect(identity[1]) as db:
        assert db.execute('SELECT count(*) FROM course_write_limits WHERE user_id=%s', (identity[2],)).fetchone()[0] == 0


def test_budget_rls_and_retention_keep_the_live_actor_row(author):
    from app.maintenance import retain
    identity, headers, cid = author
    with psycopg.connect(identity[1]) as db:
        other = db.execute('SELECT user_id FROM memberships WHERE tenant_id=%s', (identity[4],)).fetchone()[0]
        db.execute("INSERT INTO course_write_limits(tenant_id,user_id,attempts,window_start) VALUES(%s,%s,1,now()-interval '2 days')", (identity[4],other))
    with transaction() as db:
        session_context(db, token_digest(identity[0].cookies['maaher_session'])); tenant_context(db, identity[3])
        assert [r['user_id'] for r in db.execute('SELECT user_id FROM course_write_limits').fetchall()] == [identity[2]]
        user_context(db,other); tenant_context(db,identity[4])
        assert db.execute('SELECT user_id FROM course_write_limits').fetchall() == []
    with psycopg.connect(os.environ['TEST_MAINTENANCE_DATABASE_URL'], row_factory=dict_row) as db:
        retain(db)
    with psycopg.connect(identity[1]) as db:
        assert db.execute('SELECT 1 FROM course_write_limits WHERE tenant_id=%s AND user_id=%s', (identity[4],other)).fetchone() is None
        assert db.execute('SELECT 1 FROM course_write_limits WHERE tenant_id=%s AND user_id=%s', (identity[3],identity[2])).fetchone() == (1,)
