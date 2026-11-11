"""Publish proofs bind tenant/object/revision/content/resources and rotating keys."""
from concurrent.futures import ThreadPoolExecutor
import json,time,socket,subprocess,sys,os
from pathlib import Path
from uuid import uuid4
import httpx,psycopg,pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from app.auth_support import KeyRing
from app.content_attestation import seal,valid
from app.markdown_service import Parser,ParserPool
from app.markdown_parse import validate_markdown_raw
from test_courses import author,filled,write,detail


def test_proof_binding_and_rotating_keyring(monkeypatch):
    a=Fernet.generate_key().decode();b=Fernet.generate_key().decode()
    monkeypatch.setenv('AUTH_ENCRYPTION_KEYS',json.dumps({'old':a}));monkeypatch.setenv('AUTH_ACTIVE_KEY_ID','old');old=KeyRing()
    monkeypatch.setenv('AUTH_ENCRYPTION_KEYS',json.dumps({'old':a,'new':b}));monkeypatch.setenv('AUTH_ACTIVE_KEY_ID','new');new=KeyRing()
    proof=seal('lesson',('tenant','lesson',1),'Material',[],old)
    assert valid(proof,'lesson',('tenant','lesson',1),'Material',[],new)
    for kind,context,content,resources in [('assignment',('tenant','lesson',1),'Material',[]),('lesson',('foreign','lesson',1),'Material',[]),('lesson',('tenant','lesson',2),'Material',[]),('lesson',('tenant','lesson',1),'Tamper',[]),('lesson',('tenant','lesson',1),'Material',[{'url':'https://example.org'}])]:assert not valid(proof,kind,context,content,resources,new)
    assert not valid('garbage','lesson',('tenant','lesson',1),'Material',[],new)
    monkeypatch.setenv('AUTH_ENCRYPTION_KEYS',json.dumps({'new':b}))
    assert not valid(proof,'lesson',('tenant','lesson',1),'Material',[],KeyRing())


def test_legacy_validation_is_explicit_and_binds_actual_revision(author):
    mid,lid=filled(author);identity,headers,cid=author
    with psycopg.connect(identity[1]) as db:
        db.execute('UPDATE course_lessons SET content_attestation=NULL WHERE id=%s',(lid,))
    assert write(author,'/publish').status_code==409
    r=write(author,'/validate-content');assert r.status_code==200 and r.json()['checked']==1 and r.json()['next_cursor'] is None
    assert write(author,'/publish').status_code==200
    with psycopg.connect(identity[1]) as db:
        proof=db.execute('SELECT content_attestation FROM course_lessons WHERE id=%s',(lid,)).fetchone()[0]
        db.execute('UPDATE course_lessons SET content=%s WHERE id=%s',('Owner edit',lid))
        assert db.execute('SELECT content_attestation,revision FROM course_lessons WHERE id=%s',(lid,)).fetchone()==(None,2)
        db.execute('UPDATE course_lessons SET content_attestation=%s WHERE id=%s',(proof,lid))
    assert write(author,'/publish').status_code==409
    assert write(author,'/validate-content').status_code==409
    assert write(author,'/unpublish').status_code==200
    assert write(author,'/validate-content').status_code==200
    assert write(author,'/publish').status_code==200


def test_invalid_legacy_content_cannot_be_attested(author):
    mid,lid=filled(author);identity,headers,cid=author
    with psycopg.connect(identity[1]) as db:db.execute('UPDATE course_lessons SET content=%s WHERE id=%s',('[bad](javascript:alert(1))',lid))
    assert write(author,'/validate-content').status_code==409
    with psycopg.connect(identity[1]) as db:assert db.execute('SELECT content_attestation FROM course_lessons WHERE id=%s',(lid,)).fetchone()[0] is None
    assert write(author,'/publish').status_code==409


def test_control_character_rejected_without_child_restart_and_large_safe_frame():
    parser=Parser()
    try:
        parser.validate('Warm');pid=parser.process.pid
        for length in (22000,30000):
            with pytest.raises(ValueError):parser.validate('\x01'*length)
            assert parser.process.pid==pid and parser.process.poll() is None
        for text in ('\t'*30000,'\r'*30000,'😀'*30000,'*a* '*7500):assert parser.validate(text)==text
        assert parser.process.pid==pid
        assert parser.limits['memory_active'] is True and parser.limits['cpu_ms']==250
    finally:parser.close()


def test_maintenance_lane_does_not_take_interactive_slots():
    a=ParserPool(2);b=ParserPool(1)
    try:
        b.workers[0].lock.acquire()
        assert a.validate('Save remains possible')
        with pytest.raises(HTTPException) as error:b.validate('Busy maintenance')
        assert error.value.status_code==429
        b.workers[0].lock.release()
    finally:a.close();b.close()


def test_missing_memory_limit_warns_in_dev_and_fails_closed_in_production(monkeypatch,caplog):
    parser=Parser()
    try:
        # Exercise the actual parent exchange policy with a tiny trusted worker;
        # fake capability only, no sleeping/Event CPU isolation claim.
        def start():
            parser.process=subprocess.Popen([sys.executable,'-u','-c',"import sys,json;\nfor line in sys.stdin: print(json.dumps({'result':'ok','limits':{'memory_active':False}}),flush=True)"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,bufsize=0)
            os.set_blocking(parser.process.stdin.fileno(),False);os.set_blocking(parser.process.stdout.fileno(),False)
        monkeypatch.setattr(parser,'start',start);monkeypatch.setenv('APP_ENV','local')
        assert parser.validate('Development')
        assert 'memory_limit_unavailable' in caplog.text
        parser.close();monkeypatch.setenv('APP_ENV','production')
        with pytest.raises(HTTPException) as error:parser.validate('Production')
        assert error.value.status_code==503
    finally:parser.close()


def test_publish_1500_large_valid_lessons_with_concurrent_writer_real_http(author):
    identity,headers,cid=author;filled(author)
    with psycopg.connect(identity[1]) as db:
        # Trusted fixture validates each unique document using the exact parser,
        # then signs it. Setup cost is excluded from the publish measurement.
        db.execute('DELETE FROM course_lessons WHERE course_id=%s',(cid,));db.execute('DELETE FROM course_modules WHERE course_id=%s',(cid,))
        for m in range(30):
            mid=uuid4();db.execute('INSERT INTO course_modules(id,tenant_id,course_id,title,position) VALUES(%s,%s,%s,%s,%s)',(mid,identity[3],cid,f'Module {m}',m+1))
            with db.cursor() as cursor:
                rows=[]
                for n in range(50):
                    lid=uuid4();text=(f'Lesson {m*50+n}: '+'materi aman '*2700)[:29000];validate_markdown_raw(text)
                    proof=seal('lesson',(identity[3],lid,1),text,[])
                    rows.append((lid,identity[3],cid,mid,f'Lesson {n}',text,n+1,proof))
                cursor.executemany('INSERT INTO course_lessons(id,tenant_id,course_id,module_id,title,content,position,content_attestation) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',rows)
    other=identity[0].post('/courses',json={'title':'Concurrent writer'},headers=headers).json()['id']
    def other_write(suffix,**body):
        v=identity[0].get('/courses/'+other,headers=headers).json()['version']
        return identity[0].post('/courses/'+other+suffix,json={'version':v,**body},headers=headers)
    mid=other_write('/modules',title='Writer module').json()['id'];lid=other_write('/modules/'+mid+'/lessons',title='Writer lesson',content='Write initial').json()['id']
    probe=socket.socket();probe.bind(('127.0.0.1',0));port=probe.getsockname()[1];probe.close()
    env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).parents[1])
    process=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port),'--no-access-log','--log-level','error'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=15) as client:
            until=time.monotonic()+15
            while True:
                try:
                    if client.get('/healthz').status_code==200:break
                except httpx.TransportError:pass
                assert process.poll() is None and time.monotonic()<until;time.sleep(.02)
            auth={**headers,'cookie':'maaher_session='+identity[0].cookies['maaher_session']}
            def writer():
                codes=[]
                for i in range(8):
                    v=client.get('/courses/'+other,headers=auth).json()['version']
                    codes.append(client.post(f'/courses/{other}/modules/{mid}/lessons/{lid}',headers=auth,json={'version':v,'title':'Concurrent write','content':'Updated valid text '+str(i)}).status_code)
                    time.sleep(.5)
                return codes
            with ThreadPoolExecutor(max_workers=2) as pool:
                future=pool.submit(writer);version=client.get('/courses/'+cid,headers=auth).json()['version']
                start=time.perf_counter();r=client.post('/courses/'+cid+'/publish',headers=auth,json={'version':version});elapsed=(time.perf_counter()-start)*1000
                health=[]
                for _ in range(30):
                    t=time.perf_counter();assert client.get('/healthz').status_code==200;health.append((time.perf_counter()-t)*1000)
                codes=future.result()
            assert r.status_code==200,r.text;assert codes==[200]*8;assert elapsed<5000
            result={'lessons':1500,'characters_per_lesson':29000,'publish_ms':round(elapsed,2),'writer_statuses':codes,'health_p95_ms':round(sorted(health)[27],2),'setup':'each unique document validated with raw trusted parser before proof signing; excluded from publish timer'}
            print('LMS05_PUBLISH_BENCHMARK '+json.dumps(result))
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait()
