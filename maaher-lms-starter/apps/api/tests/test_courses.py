"""Authoring against real PostgreSQL roles, RLS and composite constraints."""
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.courses import Resource
from app.database import transaction, session_context, tenant_context, user_context
from app.main import app
from app.security import token_digest
from auth_helpers import make_admin, sign_in


@pytest.fixture
def author(identity):
    headers, _ = make_admin(identity)
    client = identity[0]
    response = client.post('/courses', json={'title': 'Python untuk pemula', 'description': 'Belajar dari dasar'}, headers=headers)
    assert response.status_code == 201, response.text
    return identity, headers, response.json()['id']


def detail(author):
    identity, headers, cid = author
    response = identity[0].get('/courses/' + cid, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def write(author, path='', **body):
    identity, headers, cid = author
    return identity[0].post('/courses/' + cid + path, json={'version': detail(author)['version'], **body}, headers=headers)


def filled(author):
    mod = write(author, '/modules', title='Dasar Python'); assert mod.status_code == 201, mod.text
    mid = mod.json()['id']
    lesson = write(author, f'/modules/{mid}/lessons', title='Hello Python', content='# Halo\n\n```python\nprint("Halo")\n```',
                   resources=[{'label': 'Dokumentasi Python', 'url': 'https://docs.python.org/3/'}])
    assert lesson.status_code == 201, lesson.text
    return mid, lesson.json()['id']


def test_course_lifecycle_publish_edit_and_archive_preserve_data(author):
    identity, headers, cid = author; client = identity[0]
    assert write(author, '/publish').status_code == 409
    mid, lid = filled(author)
    assert write(author, '/publish').json()['state'] == 'published'
    response = write(author, f'/modules/{mid}/lessons/{lid}', title='Pelajaran diperbarui', content='Materi baru')
    assert response.status_code == 200 and response.json()['state'] == 'draft'
    assert write(author, '/publish').json()['state'] == 'published'
    assert write(author, '/unpublish').json()['state'] == 'draft'
    assert write(author, '/archive').json()['state'] == 'archived'
    assert client.get('/courses', headers=headers).json()['courses'] == []
    assert len(client.get('/courses?archived=true', headers=headers).json()['courses']) == 1
    assert write(author, '/modules', title='Tidak boleh').status_code == 409
    assert write(author, '/restore').json()['state'] == 'draft'
    assert detail(author)['modules'][0]['lessons'][0]['title'] == 'Pelajaran diperbarui'
    actions = [r['action'] for r in client.get('/auth/audit', headers=headers).json()]
    assert {'course.created', 'lesson.updated', 'course.published', 'course.archived', 'course.restored'} <= set(actions)


def test_empty_modules_and_lessons_cannot_be_published(author):
    mid = write(author, '/modules', title='Modul kosong').json()['id']
    assert write(author, '/publish').status_code == 409
    lid = write(author, f'/modules/{mid}/lessons', title='Pelajaran kosong').json()['id']
    assert write(author, '/publish').status_code == 409
    assert write(author, f'/modules/{mid}/lessons/{lid}', title='Pelajaran', content='Materi').status_code == 200
    assert write(author, '/publish').status_code == 200


def test_stale_versions_and_failed_child_edits_are_atomic(author):
    identity, headers, cid = author; client = identity[0]
    mid, lid = filled(author)
    stale = detail(author)['version']
    assert write(author, '/publish').status_code == 200
    response = client.post('/courses/' + cid, json={'title': 'Stale', 'version': stale}, headers=headers)
    assert response.status_code == 409
    before = detail(author)
    assert write(author, f'/modules/{mid}/lessons/{uuid4()}', title='Salah', content='Tidak disimpan').status_code == 404
    after = detail(author)
    assert after['version'] == before['version'] and after['state'] == 'published' and after['title'] == before['title']


def test_simultaneous_writers_cannot_overwrite_each_other(author):
    identity, headers, cid = author; version = detail(author)['version']
    def save(title):
        with TestClient(app, base_url='https://testserver') as client:
            client.cookies.update(identity[0].cookies)
            return client.post('/courses/' + cid, json={'version': version, 'title': title}, headers=headers).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(save, ['Perubahan pertama', 'Perubahan kedua']))
    assert sorted(outcomes) == [200, 409]
    assert detail(author)['version'] == version + 1
    with psycopg.connect(identity[1]) as db:
        assert db.execute("SELECT count(*) FROM audit_events WHERE target_id=%s AND action='course.updated'", (cid,)).fetchone()[0] == 1


def test_module_lesson_order_and_deletion_are_parent_scoped(author):
    mid, lid = filled(author)
    second = write(author, '/modules', title='Modul kedua').json()['id']
    other = write(author, f'/modules/{mid}/lessons', title='Latihan', content='Latihan coding').json()['id']
    assert write(author, '/reorder-modules', ids=[second, mid]).status_code == 200
    assert detail(author)['modules'][0]['id'] == second
    assert write(author, f'/modules/{mid}/reorder-lessons', ids=[other, lid]).status_code == 200
    assert write(author, f'/modules/{second}/reorder-lessons', ids=[lid]).status_code == 409
    assert write(author, '/reorder-modules', ids=[mid, mid]).status_code == 409
    assert write(author, f'/modules/{mid}/lessons/{lid}/delete').status_code == 200
    assert write(author, f'/modules/{mid}/delete').status_code == 200
    assert len(detail(author)['modules']) == 1
    assert write(author, '/modules', title='Setelah hapus').status_code == 201
    assert [r['position'] for r in detail(author)['modules']] == [1, 2]


def test_teacher_only_manages_assigned_courses_and_revocation_is_immediate(author):
    identity, headers, cid = author; _, owner, _, tenant, foreign, _, password = identity
    with psycopg.connect(owner) as db:
        teacher = db.execute('SELECT user_id FROM memberships WHERE tenant_id=%s', (foreign,)).fetchone()[0]
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'teacher')", (uuid4(), tenant, teacher))
    second = identity[0].post('/courses', json={'title': 'Kursus lain'}, headers=headers).json()['id']
    with TestClient(app, base_url='https://testserver') as client:
        assert sign_in(client, f'{teacher}@example.invalid', password).status_code == 200
        assert client.get('/courses', headers=headers).json()['courses'] == []
        assert client.get('/courses/' + cid, headers=headers).status_code == 404
        assert client.post('/courses', json={'title': 'Tidak boleh'}, headers=headers).status_code == 403
        assert write(author, '/teachers', user_id=str(teacher), assigned=True).status_code == 200
        assert [r['id'] for r in client.get('/courses', headers=headers).json()['courses']] == [cid]
        assert client.get('/courses/' + second, headers=headers).status_code == 404
        version = client.get('/courses/' + cid, headers=headers).json()['version']
        assert client.post(f'/courses/{cid}/modules', json={'title': 'Modul guru', 'version': version}, headers=headers).status_code == 201
        assert client.post(f'/courses/{cid}/archive', json={'version': detail(author)['version']}, headers=headers).status_code == 403
        assert write(author, '/teachers', user_id=str(teacher), assigned=False).status_code == 200
        assert client.get('/courses/' + cid, headers=headers).status_code == 404
        assert client.get('/courses', headers=headers).json()['courses'] == []


def test_inactive_or_foreign_members_cannot_be_assigned(author):
    identity, _, _ = author
    with psycopg.connect(identity[1]) as db:
        foreign = db.execute('SELECT user_id FROM memberships WHERE tenant_id=%s', (identity[4],)).fetchone()[0]
    assert write(author, '/teachers', user_id=str(foreign), assigned=True).status_code == 404
    assert write(author, '/teachers', user_id=str(identity[2]), assigned=True).status_code == 404
    with psycopg.connect(identity[1]) as db:
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'teacher')", (uuid4(), identity[3], foreign))
        db.execute("UPDATE users SET status='disabled' WHERE id=%s", (foreign,))
    assert write(author, '/teachers', user_id=str(foreign), assigned=True).status_code == 404


def test_students_anonymous_and_forged_tenant_headers_are_denied(identity):
    client, _, _, tenant, foreign, email, password = identity
    headers = {'origin': 'https://testserver', 'x-tenant-id': str(tenant)}
    assert client.get('/courses', headers=headers).status_code == 401
    assert sign_in(client, email, password).status_code == 200
    assert client.get('/courses', headers=headers).status_code == 403
    assert client.get('/courses', headers={'x-tenant-id': str(foreign)}).status_code == 403


def test_origin_payload_ownership_and_resource_limits(author):
    identity, headers, cid = author; client = identity[0]
    assert client.post('/courses', json={'title': 'No origin'}).status_code == 403
    assert client.post('/courses', json={'title': 'Foreign origin'}, headers={**headers, 'origin': 'https://evil.invalid'}).status_code == 403
    assert client.post('/courses', json={'title': 'Forged', 'tenant_id': str(identity[4])}, headers=headers).status_code == 422
    assert client.post('/courses', content=b'x' * 262145, headers={**headers, 'content-type': 'application/json'}).status_code == 413
    mid, _ = filled(author)
    assert write(author, f'/modules/{mid}/lessons', title='Too long', content='x' * 30001).status_code == 422
    assert write(author, f'/modules/{mid}/lessons', title='Too many', resources=[{'label': 'Doc', 'url': 'https://example.org'}] * 11).status_code == 422
    assert write(author, f'/modules/{mid}/lessons', title='Script URL', resources=[{'label': 'Doc', 'url': 'javascript:alert(1)'}]).status_code == 422


def test_rls_uses_session_capability_and_composite_keys_not_forged_gucs(author):
    identity, _, cid = author; client, owner, user, tenant, foreign = identity[:5]
    with psycopg.connect(owner) as db:
        other = db.execute('SELECT user_id FROM memberships WHERE tenant_id=%s', (foreign,)).fetchone()[0]
        foreign_id = uuid4()
        db.execute("INSERT INTO courses(id,tenant_id,owner_id,title) VALUES(%s,%s,%s,'Private foreign course')", (foreign_id, foreign, other))
    with transaction() as db:
        user_context(db, other); tenant_context(db, foreign)
        assert db.execute('SELECT id FROM courses').fetchall() == []
        session_context(db, token_digest(client.cookies['maaher_session']))
        assert db.execute('SELECT id FROM courses').fetchall() == []
        assert db.execute('SELECT course_member_role(%s,%s) AS role', (foreign, other)).fetchone()['role'] is None
        tenant_context(db, tenant)
        assert [str(r['id']) for r in db.execute('SELECT id FROM courses').fetchall()] == [cid]
    with transaction() as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
        session_context(db, token_digest(client.cookies['maaher_session'])); tenant_context(db, tenant)
        db.execute('UPDATE courses SET tenant_id=%s WHERE id=%s', (foreign, cid))
    with psycopg.connect(owner) as db, pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute("INSERT INTO course_modules(id,tenant_id,course_id,title,position) VALUES(%s,%s,%s,'Wrong FK',1)", (uuid4(), foreign, cid))


def test_published_content_cannot_be_changed_through_direct_runtime_sql(author):
    identity, _, cid = author; mid, lid = filled(author)
    assert write(author, '/publish').status_code == 200
    with transaction() as db:
        session_context(db, token_digest(identity[0].cookies['maaher_session'])); tenant_context(db, identity[3])
        assert db.execute("UPDATE course_lessons SET content='forged' WHERE id=%s RETURNING id", (lid,)).fetchone() is None
    with psycopg.connect(identity[1]) as db:
        assert db.execute('SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname=%s', ('course_lessons',)).fetchone()[0] is True


@pytest.mark.parametrize('change', ['role', 'revoked'])
def test_membership_changes_remove_course_access_on_existing_sessions(author, change):
    identity, headers, cid = author
    with psycopg.connect(identity[1]) as db:
        if change == 'role': db.execute("UPDATE memberships SET role='student' WHERE tenant_id=%s AND user_id=%s", (identity[3], identity[2]))
        else: db.execute("UPDATE memberships SET status='revoked' WHERE tenant_id=%s AND user_id=%s", (identity[3], identity[2]))
    assert identity[0].get('/courses/' + cid, headers=headers).status_code == 403
    with transaction() as db:
        session_context(db, token_digest(identity[0].cookies['maaher_session'])); tenant_context(db, identity[3])
        assert db.execute('SELECT id FROM courses').fetchall() == []


def test_course_module_and_lesson_caps_are_enforced(author):
    identity, headers, cid = author
    mid = uuid4()
    with psycopg.connect(identity[1]) as db:
        with db.cursor() as cursor:
            cursor.executemany("INSERT INTO courses(id,tenant_id,owner_id,title) VALUES(%s,%s,%s,'Cap fixture')", [(uuid4(), identity[3], identity[2]) for _ in range(499)])
            cursor.executemany("INSERT INTO course_modules(id,tenant_id,course_id,title,position) VALUES(%s,%s,%s,'Module fixture',%s)", [(mid if i == 1 else uuid4(), identity[3], cid, i) for i in range(1, 31)])
            cursor.executemany("INSERT INTO course_lessons(id,tenant_id,course_id,module_id,title,position) VALUES(%s,%s,%s,%s,'Lesson fixture',%s)", [(uuid4(), identity[3], cid, mid, i) for i in range(1, 51)])
            teachers = [uuid4() for _ in range(51)]
            cursor.executemany("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,'unused-cap-fixture')", [(t, f'{t}@example.invalid') for t in teachers])
            cursor.executemany("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'teacher')", [(uuid4(), identity[3], t) for t in teachers])
            cursor.executemany("INSERT INTO courses_teachers(tenant_id,course_id,user_id) VALUES(%s,%s,%s)", [(identity[3], cid, t) for t in teachers[:50]])
    assert identity[0].post('/courses', json={'title': 'Over cap'}, headers=headers).status_code == 409
    assert write(author, '/modules', title='Over cap').status_code == 409
    assert write(author, f'/modules/{mid}/lessons', title='Over cap').status_code == 409
    assert write(author, '/teachers', user_id=str(teachers[-1]), assigned=True).status_code == 409
    assert write(author, '/teachers', user_id=str(teachers[0]), assigned=True).status_code == 200


def test_course_pagination_has_no_duplicate_or_foreign_rows(author):
    client, headers, _ = author[0][0], author[1], author[2]
    for i in range(3): assert client.post('/courses', json={'title': f'Kursus {i}'}, headers=headers).status_code == 201
    seen = []; after = None
    while True:
        response = client.get('/courses?limit=2' + (f'&after={after}' if after else ''), headers=headers).json()
        seen.extend(r['id'] for r in response['courses']); after = response['next_cursor']
        if not after: break
    assert len(seen) == len(set(seen)) == 4


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'data:text/html,test', 'http://example.org', 'https://user:pass@example.org',
    'https://127.0.0.1', 'https://localhost', 'https://example.local', 'https://example.org\\@evil.invalid', 'https://example.org\n', 'https://example.org:bad',
    'https://127.1', 'https://localhost.', 'https://0177.0.0.1'])
def test_resources_reject_unsafe_urls(url):
    with pytest.raises((ValidationError, ValueError)):
        Resource(label='Doc', url=url)
