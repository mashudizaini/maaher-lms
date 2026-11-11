"""Real CPU work in a bounded child, no Event-based isolation claim."""
from concurrent.futures import ThreadPoolExecutor
import os
import time
import pytest
from fastapi import HTTPException
from app.markdown_service import Parser,MarkdownComplexity
from test_enrollment import enrollment_case
from test_courses import author


def test_cpu_budget_and_child_process_separation():
    parser=Parser()
    try:
        assert parser.validate('# Trusted parser')=='# Trusted parser'
        assert parser.process.pid!=os.getpid()
        start=time.monotonic()
        with pytest.raises(MarkdownComplexity):parser.validate('['*30000)
        assert time.monotonic()-start<1.5
        assert parser.validate('[valid](https://example.org)')
    finally:parser.close()


def test_busy_is_bounded_and_does_not_queue_unlimited_cpu():
    parser=Parser()
    try:
        parser.validate('Warm up')
        with ThreadPoolExecutor(max_workers=8) as pool:
            def parse(i):
                try:parser.validate('['*(29990+i));return 200
                except MarkdownComplexity:return 422
                except HTTPException as e:return e.status_code
            statuses=list(pool.map(parse,range(8)))
        assert 422 in statuses and 429 in statuses and set(statuses)<={422,429}
    finally:parser.close()


def test_child_crash_restarts_without_weakening_policy():
    parser=Parser()
    try:
        parser.validate('First');parser.process.kill();parser.process.wait()
        assert parser.validate('Second')=='Second'
        with pytest.raises(ValueError):parser.validate('[bad](javascript:alert(1))')
    finally:parser.close()


def test_actual_http_cpu_pressure_with_original_account_budget(enrollment_case):
    import json, socket, subprocess, sys
    from pathlib import Path
    import httpx
    from test_courses import write
    c=enrollment_case;identity,headers,cid=c['author']
    port_probe=socket.socket();port_probe.bind(('127.0.0.1',0));port=port_probe.getsockname()[1];port_probe.close()
    env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).parents[1])
    process=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port),'--no-access-log','--log-level','error'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    stats={}
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=6) as client:
            deadline=time.monotonic()+15
            while True:
                try:
                    if client.get('/healthz').status_code==200:break
                except httpx.TransportError:pass
                assert time.monotonic()<deadline and process.poll() is None
                time.sleep(.03)
            def health():
                start=time.perf_counter();assert client.get('/healthz').status_code==200;return (time.perf_counter()-start)*1000
            def p95(values):return round(sorted(values)[int((len(values)-1)*.95)],2)
            stats['baseline_p95_ms']=p95([health() for _ in range(20)])
            version=identity[0].get('/courses/'+cid,headers=headers).json()['version']
            auth={**headers,'cookie':'maaher_session='+identity[0].cookies['maaher_session']}
            target=f'/courses/{cid}/modules/{c["mid"]}/lessons/{c["lid"]}'
            for concurrency,repeats in ((2,4),(8,4),(1,8)):
                def save(i):
                    codes=[]
                    for repeat in range(repeats):
                        response=client.post(target,headers=auth,json={'version':version,'title':'CPU policy probe','content':'['*(29980+i)+str(repeat)})
                        codes.append(response.status_code)
                    return codes
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    pending=[pool.submit(save,i) for i in range(concurrency)];samples=[]
                    while any(not f.done() for f in pending):samples.append(health())
                    codes=[code for f in pending for code in f.result()]
                stats[f'load_{concurrency}_p95_ms']=p95(samples)
                stats[f'load_{concurrency}_samples']=len(samples)
                stats[f'load_{concurrency}_statuses']={str(code):codes.count(code) for code in set(codes)}
                assert set(codes)<={422,429} and 422 in codes
                # Fixed headroom for shared CI hosts, still below the reported
                # 513ms/8 writers; exact numbers are recorded, not generalized.
                assert stats[f'load_{concurrency}_p95_ms']<max(100,stats['baseline_p95_ms']*8+25)
            import psycopg
            with psycopg.connect(identity[1]) as owner:
                budget=owner.execute('SELECT attempts FROM course_write_limits WHERE tenant_id=%s AND user_id=%s',(identity[3],identity[2])).fetchone()[0]
            assert budget<=60
            stats['actual_account_budget_attempts']=budget
            print('LMS04_CPU_HTTP_BENCHMARK '+json.dumps(stats,sort_keys=True))
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)


def test_worker_timeout_and_invalid_unicode_fail_closed(monkeypatch):
    parser=Parser()
    try:
        with pytest.raises(ValueError):parser.validate('\ud800')
        monkeypatch.setattr(parser,'exchange',lambda _:(_ for _ in ()).throw(TimeoutError()))
        with pytest.raises(HTTPException) as error:parser.validate('Unvalidated content')
        assert error.value.status_code==503 and not parser.cache
    finally:parser.close()


def test_valid_digest_cache_is_scoped_per_validated_actor(monkeypatch):
    parser=Parser();seen=[]
    monkeypatch.setattr(parser,'exchange',lambda content:seen.append(content) or 'ok')
    try:
        parser.validate('Same content','tenant-A:user-A')
        parser.validate('Same content','tenant-A:user-A')
        parser.validate('Same content','tenant-B:user-A')
        parser.validate('Same content','tenant-A:user-B')
        assert len(seen)==3 and len(parser.cache)==3
    finally:parser.close()
