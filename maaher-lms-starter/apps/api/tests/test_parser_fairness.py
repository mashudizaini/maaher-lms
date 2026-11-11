"""Queue ordering/bounds plus real CPU contention through authenticated TCP."""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from pathlib import Path
from uuid import uuid4
import json,os,socket,subprocess,sys,threading,time
import httpx,psycopg,pytest
from fastapi import HTTPException
from app.markdown_service import ParserPool
from app.security import token_digest
from test_courses import author,filled
from test_assignments import assignment
from test_learning import learning
from test_enrollment import enrollment_case


def pressure_response(response):
    """Whitelist diagnostics; never emit raw bodies, headers, cookies or URLs."""
    status=response.status_code
    result={'status':status,'category':{200:'ok',422:'validation_rejected'}.get(status,'other_status')}
    if status in {429,503}:
        categories={
            'Validasi materi sementara tidak tersedia. Coba lagi':'worker_unavailable',
            'Batas memori validator belum tersedia':'memory_capability_unavailable',
            'Antrean validasi penuh waktu. Coba lagi':'queue_expired',
            'Kapasitas antrean validasi sedang penuh. Coba lagi':'queue_capacity',
            'Validasi melewati batas waktu. Coba lagi':'caller_timeout',
            'Validator sedang berhenti. Coba lagi':'stopping',
            'Validator sedang berhenti':'stopping',
            'Layanan penyimpanan sementara tidak tersedia':'storage_unavailable',
            'Validasi akun Anda masih berlangsung. Tunggu sebelum menyimpan lagi':'principal_busy',
            'Kapasitas validasi organisasi sedang penuh. Coba lagi':'tenant_capacity',
            'Terlalu banyak perubahan kursus. Coba lagi sebentar lagi':'course_budget',
            'Terlalu banyak permintaan belajar. Coba lagi sebentar lagi':'learning_budget',
        }
        try:body=response.json()
        except ValueError:body=None
        detail=body.get('detail') if isinstance(body,dict) else None
        result['category']=categories.get(detail,'unclassified') if isinstance(detail,str) else 'unclassified'
        retry=response.headers.get('Retry-After','')
        if len(retry)<=4 and retry.isascii() and retry.isdigit():result['retry_after_seconds']=int(retry)
    return result


def test_pressure_diagnostics_whitelist_omits_response_secrets():
    sentinel='PRIVATE-CONTENT-DO-NOT-LOG'
    for body in ({'detail':sentinel,'token':sentinel},{'detail':{'secret':sentinel}},[sentinel],sentinel):
        response=httpx.Response(503,json=body,headers={'Retry-After':sentinel,'Set-Cookie':sentinel})
        assert pressure_response(response)=={'status':503,'category':'unclassified'}
    response=httpx.Response(503,json={'detail':'Antrean validasi penuh waktu. Coba lagi','secret':sentinel},headers={'Retry-After':'1','Set-Cookie':sentinel})
    assert pressure_response(response)=={'status':503,'category':'queue_expired','retry_after_seconds':1}
    assert sentinel not in json.dumps(pressure_response(response))
    assert pressure_response(httpx.Response(503,content=sentinel))=={'status':503,'category':'unclassified'}
    assert pressure_response(httpx.Response(422,json={'detail':sentinel}))=={'status':422,'category':'validation_rejected'}


def await_waiting(pool,count):
    until=time.monotonic()+3
    while True:
        with pool.condition:
            if pool.waiting>=count:return
        assert time.monotonic()<until
        time.sleep(.002)


def test_fair_tenant_order_and_own_principal_limit_with_bounded_queue():
    # Events control ordering only. CPU-isolation evidence is the real HTTP test.
    entered=threading.Barrier(3);release=threading.Event();order=[];lock=threading.Lock()
    class Worker:
        def validate(self,value,scope):
            with lock:order.append(scope)
            if value=='hold':entered.wait(timeout=3);assert release.wait(5)
            return value
        def close(self):pass
    scheduler=ParserPool(2,max_pending=3);scheduler.workers=[Worker(),Worker()]
    try:
        with ThreadPoolExecutor(max_workers=6) as callers:
            first=[callers.submit(scheduler.validate,'hold',f'A:{i}') for i in range(2)]
            entered.wait(timeout=3)
            with pytest.raises(HTTPException) as duplicate:scheduler.validate('duplicate','A:0')
            assert duplicate.value.status_code==429 and 'akun' in duplicate.value.detail
            queued=[]
            for scope in ('A:2','A:3','B:0'):
                queued.append(callers.submit(scheduler.validate,'queued',scope));await_waiting(scheduler,len(queued))
            with pytest.raises(HTTPException) as capacity:scheduler.validate('overflow','C:0')
            assert capacity.value.status_code==503 and capacity.value.headers['Retry-After']=='1'
            release.set()
            assert [f.result(timeout=5) for f in first]==['hold','hold']
            assert [f.result(timeout=5) for f in queued]==['queued']*3
            assert order.index('B:0')<=3 and order.index('A:2')<order.index('A:3')
        assert not scheduler.principals and not scheduler.active and scheduler.waiting==0
    finally:release.set();scheduler.close()


def test_expired_queue_job_does_not_run_and_releases_its_scope():
    started=threading.Event();calls=[]
    class Worker:
        def validate(self,value,scope):
            calls.append(scope)
            if value=='hold':started.set();time.sleep(.15)
            return value
        def close(self):pass
    scheduler=ParserPool(1,queue_seconds=.03);scheduler.workers=[Worker()]
    try:
        with ThreadPoolExecutor(max_workers=2) as callers:
            first=callers.submit(scheduler.validate,'hold','A:first');assert started.wait(2)
            with pytest.raises(HTTPException) as expired:scheduler.validate('expired','B:second')
            assert expired.value.status_code==503 and first.result()=='hold'
        assert 'B:second' not in calls
        assert scheduler.validate('retry','B:second')=='retry'
        for n in range(100):assert scheduler.validate('sequential','C:same')=='sequential'
        assert not scheduler.principals and scheduler.waiting==0
    finally:scheduler.close()


def test_one_tenant_cannot_take_all_global_waiting_capacity():
    release=threading.Event();started=threading.Event()
    class Worker:
        def validate(self,value,scope):
            if value=='hold':started.set();assert release.wait(5)
            return value
        def close(self):pass
    scheduler=ParserPool(1);scheduler.workers=[Worker()]
    try:
        with ThreadPoolExecutor(max_workers=11) as callers:
            active=callers.submit(scheduler.validate,'hold','A:0');assert started.wait(2)
            jobs=[]
            for n in range(1,10):jobs.append(callers.submit(scheduler.validate,'queued',f'A:{n}'));await_waiting(scheduler,n)
            with pytest.raises(HTTPException) as limit:scheduler.validate('over-tenant','A:10')
            assert limit.value.status_code==429 and 'organisasi' in limit.value.detail
            other=callers.submit(scheduler.validate,'other','B:0');await_waiting(scheduler,10)
            release.set();assert other.result(timeout=5)=='other'
            assert active.result()=='hold' and all(f.result()=='queued' for f in jobs)
    finally:release.set();scheduler.close()


def seed_teacher(owner,tenant=None):
    uid,cid,mid,lid=(uuid4() for _ in range(4));cap='synthetic-fairness-'+uuid4().hex;tid=tenant or uuid4()
    with psycopg.connect(owner) as db:
        if tenant is None:db.execute("INSERT INTO tenants(id,slug,name) VALUES(%s,%s,'Fairness synthetic')",(tid,str(tid)))
        db.execute("INSERT INTO users(id,email,password_hash) VALUES(%s,%s,'no-password-login-fixture')",(uid,f'{uid}@example.invalid'))
        db.execute("INSERT INTO memberships(id,tenant_id,user_id,role) VALUES(%s,%s,%s,'teacher')",(uuid4(),tid,uid))
        db.execute("INSERT INTO sessions(token_hash,user_id,expires_at,mfa_verified) VALUES(%s,%s,now()+interval '1 hour',true)",(token_digest(cap),uid))
        db.execute("INSERT INTO courses(id,tenant_id,owner_id,title) VALUES(%s,%s,%s,'Fairness course')",(cid,tid,uid))
        db.execute("INSERT INTO courses_teachers(tenant_id,course_id,user_id) VALUES(%s,%s,%s)",(tid,cid,uid))
        db.execute("INSERT INTO course_modules(id,tenant_id,course_id,title,position) VALUES(%s,%s,%s,'Module',1)",(mid,tid,cid))
        db.execute("INSERT INTO course_lessons(id,tenant_id,course_id,module_id,title,content,position) VALUES(%s,%s,%s,%s,'Lesson','Initial',1)",(lid,tid,cid,mid))
    return {'tenant':tid,'cid':cid,'target':f'/courses/{cid}/modules/{mid}/lessons/{lid}',
        'headers':{'origin':'https://testserver','x-tenant-id':str(tid),'cookie':'maaher_session='+cap}}


@pytest.mark.parametrize('tenant_mode',['same','different'])
def test_real_http_fairness_multiple_accounts_and_tenants(assignment,tenant_mode):
    c=assignment;identity,headers,cid=c['author']
    pupil_headers={**headers,'cookie':'maaher_session='+c['student'].cookies['maaher_session']}
    victim=seed_teacher(identity[1],identity[3]);actors=[seed_teacher(identity[1],victim['tenant'] if tenant_mode=='same' else None) for _ in range(8)]
    port_probe=socket.socket();port_probe.bind(('127.0.0.1',0));port=port_probe.getsockname()[1];port_probe.close()
    env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).parents[1])
    process=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port),'--no-access-log','--log-level','error'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    metrics={'tenant_mode':tenant_mode,'api_workers':1,'rounds':[],'completed':False}
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=14) as health:
            until=time.monotonic()+20
            while True:
                try:
                    if health.get('/healthz').status_code==200:break
                except httpx.TransportError:pass
                assert time.monotonic()<until and process.poll() is None;time.sleep(.03)
            # Confirm real session+membership+assignment authority before pressure.
            for actor in [victim,*actors]:assert health.get('/courses/'+str(actor['cid']),headers=actor['headers']).status_code==200
            for count in (2,4,8):
                # Append before assertions so a failing full-suite run retains
                # its partial episode. No body/source/identifier is recorded.
                episode={'attacker_accounts':count,'attacker_max_requests_per_second_per_account':1,'requests':[],'completed':False}
                metrics['rounds'].append(episode);metrics_lock=threading.Lock()
                def observe(client,method,path,phase,actor_index=None,request_index=None,**kwargs):
                    started=time.perf_counter()
                    try:
                        response=client.request(method,path,**kwargs)
                        evidence=pressure_response(response)
                    except httpx.TransportError as error:
                        evidence={'category':'transport_error','error_type':type(error).__name__}
                        raise
                    finally:
                        if 'evidence' in locals():
                            evidence={**evidence,'phase':phase,'elapsed_ms':round((time.perf_counter()-started)*1000,2)}
                            if actor_index is not None:evidence['actor_index']=actor_index
                            if request_index is not None:evidence['request_index']=request_index
                            with metrics_lock:
                                if len(episode['requests'])<128:episode['requests'].append(evidence)
                    return response
                stop_load=threading.Event();start_load=threading.Barrier(count+1)
                def attack(index):
                    actor=actors[index];codes=[]
                    with httpx.Client(base_url=str(health.base_url),trust_env=False,timeout=14) as client:
                        start_load.wait(timeout=5)
                        for n in range(12):
                            if stop_load.is_set():break
                            tick=time.monotonic()
                            text='[deny](javascript:alert(1))\n'+('![**'*7500)[:29800+index]+f'{count}:{n}'
                            response=observe(client,'POST',actor['target'],'attacker',index,n,headers=actor['headers'],json={'version':1,'title':'Pressure fixture','content':text})
                            codes.append(response.status_code)
                            delay=1-(time.monotonic()-tick)
                            if delay>0:time.sleep(delay)
                    return codes
                def normal():
                    values=[];codes=[];loaders=[]
                    with httpx.Client(base_url=str(health.base_url),trust_env=False,timeout=14) as client:
                        version=observe(client,'GET','/courses/'+str(victim['cid']),'normal_context',headers=victim['headers']).json()['version']
                        for n in range(6):
                            loaders.append(sum(not f.done() for f in attacker_futures))
                            start=time.perf_counter()
                            response=observe(client,'POST',victim['target'],'normal',request_index=n,headers=victim['headers'],json={'version':version,'title':'Normal writer','content':'Valid material '+str(uuid4())})
                            codes.append(response.status_code);values.append(round((time.perf_counter()-start)*1000,2))
                            if response.status_code==200:version=response.json()['version']
                            time.sleep(.2)
                    return codes,values,loaders
                def pupil():
                    codes=[];latency=[];loaders=[]
                    with httpx.Client(base_url=str(health.base_url),trust_env=False,timeout=14) as client:
                        row=observe(client,'GET','/work/assignments/'+c['aid'],'student_context',headers=pupil_headers).json()
                        revision=row['draft']['revision'] if row['draft'] else 0
                        for n in range(6):
                            loaders.append(sum(not f.done() for f in attacker_futures));start=time.perf_counter()
                            response=observe(client,'POST','/work/assignments/'+c['aid']+'/draft','student',request_index=n,headers=pupil_headers,json={'version_id':row['published']['id'],'revision':revision,'source_code':'print("student '+str(uuid4())+'")'})
                            codes.append(response.status_code);latency.append(round((time.perf_counter()-start)*1000,2))
                            if response.status_code==200:revision=response.json()['revision']
                            time.sleep(.2)
                    return codes,latency,loaders
                with ThreadPoolExecutor(max_workers=count+2) as callers:
                    attacker_futures=[callers.submit(attack,i) for i in range(count)]
                    # Let real CPU work start. This is a load probe, not Event isolation.
                    start_load.wait(timeout=5);time.sleep(.12);normal_future=callers.submit(normal);pupil_future=callers.submit(pupil);samples=[]
                    while not normal_future.done() or not pupil_future.done():
                        t=time.perf_counter();assert health.get('/healthz').status_code==200;samples.append((time.perf_counter()-t)*1000);time.sleep(.015)
                    stop_load.set()
                    while any(not f.done() for f in attacker_futures):
                        t=time.perf_counter();assert health.get('/healthz').status_code==200;samples.append((time.perf_counter()-t)*1000);time.sleep(.015)
                    attack_codes=[code for f in attacker_futures for code in f.result()]
                    normal_codes,latency,loaders=normal_future.result();pupil_codes,pupil_latency,pupil_loaders=pupil_future.result()
                with psycopg.connect(identity[1]) as db:
                    attempts=db.execute('SELECT max(attempts) FROM course_write_limits WHERE tenant_id=ANY(%s)',([a['tenant'] for a in actors],)).fetchone()[0]
                episode.update({'attacker_statuses':dict(Counter(attack_codes)),
                    'student_statuses':pupil_codes,'student_latency_ms':pupil_latency,'active_attacker_loops_at_each_student_save':pupil_loaders,'active_attacker_loops_at_each_normal_save':loaders,'normal_statuses':normal_codes,'normal_latency_ms':latency,'normal_429_fraction':0,
                    'health_p95_ms':round(sorted(samples)[int((len(samples)-1)*.95)],2),'max_account_budget_attempts':attempts})
                episode['normal_429_fraction']=normal_codes.count(429)/len(normal_codes)
                assert normal_codes==[200]*6,normal_codes
                assert all(loaders),loaders
                assert pupil_codes==[200]*6 and all(pupil_loaders),(pupil_codes,pupil_loaders)
                assert set(attack_codes)=={422},attack_codes
                assert max(latency)<10000
                assert attempts<=60
                episode['completed']=True
            metrics['completed']=True
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
        # pytest captures this on FAIL; -s also retains it on PASS. Diagnostics
        # do not turn a failed episode into a pass or relax its assertions.
        print('LMS05_FAIRNESS_HTTP '+json.dumps(metrics,sort_keys=True))
