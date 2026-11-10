"""ASGI framing and worker isolation, independent of a database."""
import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app import course_ingress, courses


@pytest.mark.parametrize('chunks,status', [([b'a',b'b'],200),([b'a'*262144],200),([b'a'*262144,b'x'],413)])
def test_streamed_body_is_bounded_and_replayed_once(monkeypatch, chunks, status):
    monkeypatch.setattr(course_ingress,'admit_course_write',lambda _:True)
    seen=[]; sent=[]
    async def endpoint(scope,receive,send):
        message=await receive(); seen.append(message)
        await send({'type':'http.response.start','status':200,'headers':[]})
        await send({'type':'http.response.body','body':b'ok'})
    async def run():
        messages=deque({'type':'http.request','body':chunk,'more_body':i<len(chunks)-1} for i,chunk in enumerate(chunks))
        async def receive(): return messages.popleft() if messages else {'type':'http.disconnect'}
        async def send(message): sent.append(message)
        await course_ingress.CourseIngress(endpoint)({'type':'http','method':'POST','path':'/courses','headers':[]},receive,send)
    asyncio.run(run())
    assert sent[0]['status']==status
    if status==200: assert seen==[{'type':'http.request','body':b''.join(chunks),'more_body':False}]
    else: assert seen==[]


def test_disconnect_does_not_dispatch_partial_body(monkeypatch):
    monkeypatch.setattr(course_ingress,'admit_course_write',lambda _:True)
    async def unreachable(*_): raise AssertionError('Disconnected body reached endpoint')
    async def receive(): return {'type':'http.disconnect'}
    asyncio.run(course_ingress.CourseIngress(unreachable)({'type':'http','method':'POST','path':'/courses','headers':[]},receive,unreachable))


def test_markdown_validation_runs_in_worker_and_health_remains_responsive(monkeypatch):
    entered,release=Event(),Event(); ids={}
    def parse(_):
        ids['parser']=get_ident(); entered.set(); assert release.wait(3)
    monkeypatch.setattr(courses,'validate_markdown',parse)
    app=FastAPI()
    @app.post('/lesson')
    def lesson(body:courses.Lesson): courses.validate_lesson_content(body); return {'ok':True}
    @app.get('/health')
    async def health(): ids['loop']=get_ident(); return {'ok':True}
    with TestClient(app) as client,ThreadPoolExecutor(max_workers=1) as pool:
        pending=pool.submit(client.post,'/lesson',json={'title':'Test','version':1,'content':'Adversarial placeholder'})
        try:
            assert entered.wait(2)
            assert client.get('/health').status_code==200
            assert not pending.done() and ids['parser']!=ids['loop']
        finally: release.set()
        assert pending.result(timeout=3).status_code==200
