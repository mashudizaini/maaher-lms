"""Bounded interactive/maintenance parser processes; fail closed on overload."""
import atexit
from collections import OrderedDict,Counter,deque
from concurrent.futures import Future,TimeoutError as FutureTimeout
import hashlib
import json
import re
import logging
import os
from pathlib import Path
import selectors
import subprocess
import sys
import threading
import time

from fastapi import HTTPException
from .markdown_budget import WALL_SECONDS,QUEUE_SECONDS,MAX_PENDING


class MarkdownComplexity(ValueError): pass


class Parser:
    def __init__(self):
        self.lock=threading.Lock();self.cache_lock=threading.Lock();self.cache=OrderedDict();self.process=None;self.limits={};self.usage={}

    def close(self):
        p=self.process;self.process=None
        if p:
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=.3)
                except subprocess.TimeoutExpired:p.kill();p.wait(timeout=.3)
            for pipe in (p.stdin,p.stdout):
                if pipe:pipe.close()

    def start(self):
        if self.process is None or self.process.poll() is not None:
            self.close()
            self.process=subprocess.Popen([sys.executable,'-m','app.markdown_worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,bufsize=0,close_fds=True,
                env={'PYTHONPATH':str(Path(__file__).resolve().parents[1]),'PYTHONUNBUFFERED':'1','PYTHONUTF8':'1'})
            os.set_blocking(self.process.stdin.fileno(),False);os.set_blocking(self.process.stdout.fileno(),False)

    def exchange(self,value):
        self.start();p=self.process
        payload=json.dumps({'content':value},ensure_ascii=False).encode()+b'\n';offset=0;reply=bytearray();deadline=time.monotonic()+WALL_SECONDS
        with selectors.DefaultSelector() as ready:
            ready.register(p.stdin,selectors.EVENT_WRITE);ready.register(p.stdout,selectors.EVENT_READ)
            while time.monotonic()<deadline:
                for key,_ in ready.select(max(0,deadline-time.monotonic())):
                    if key.fileobj is p.stdin:
                        offset+=os.write(p.stdin.fileno(),payload[offset:])
                        if offset==len(payload):ready.unregister(p.stdin)
                    else:
                        chunk=os.read(p.stdout.fileno(),4096)
                        if not chunk:raise EOFError()
                        reply.extend(chunk)
                        if len(reply)>4096:raise ValueError()
                        if b'\n' in reply:
                            response=json.loads(reply);self.limits=response.get('limits',{});self.usage=response.get('usage',{})
                            if not self.limits.get('memory_active'):
                                if not getattr(self,'memory_warning',False):
                                    logging.getLogger(__name__).warning('markdown.memory_limit_unavailable: use a Linux/container memory limit for real data')
                                    self.memory_warning=True
                                if os.environ.get('APP_ENV','local') not in {'local','test'}:
                                    raise OSError('required parser memory limit unavailable')
                            return response['result']
        raise TimeoutError()

    def validate(self,value,cache_scope="library"):
        if self.limits and not self.limits.get("memory_active") and os.environ.get("APP_ENV","local") not in {"local","test"}:
            raise HTTPException(503,"Batas memori validator belum tersedia")
        if not isinstance(value,str) or len(value)>30000:raise ValueError('Materi terlalu panjang')
        if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]',value):raise ValueError('Materi memuat karakter kontrol yang tidak diizinkan')
        try:encoded=value.encode('utf8')
        except UnicodeError:raise ValueError('Encoding materi tidak valid') from None
        digest=hashlib.sha256(cache_scope.encode()+b"\0"+encoded).digest()
        with self.cache_lock:
            if digest in self.cache:self.cache.move_to_end(digest);return value
        if not self.lock.acquire(blocking=False):
            raise HTTPException(429,'Validasi materi sedang sibuk. Coba lagi sebentar lagi',headers={'Retry-After':'1'})
        try:
            try:result=self.exchange(value)
            except (OSError,ValueError,EOFError,TimeoutError,KeyError):
                self.close();raise HTTPException(503,'Validasi materi sementara tidak tersedia. Coba lagi') from None
            if result=='complexity':raise MarkdownComplexity('Materi terlalu kompleks. Sederhanakan struktur Markdown lalu simpan kembali')
            if result!='ok':raise ValueError('Tautan materi tidak valid')
            with self.cache_lock:
                self.cache[digest]=True
                while len(self.cache)>128:self.cache.popitem(last=False)
            return value
        finally:self.lock.release()


class ParserPool:
    """Bounded FIFO within tenant, least-active tenant first, no busy-slot 429.

    Callers pass only a server-validated tenant:user scope. At most one request
    per principal may be queued/running. The finite process/thread count does
    not grow with principals; queued waits release the GIL and expire boundedly.
    """
    def __init__(self,count,max_pending=MAX_PENDING,queue_seconds=QUEUE_SECONDS):
        self.workers=[Parser() for _ in range(count)]
        self.condition=threading.Condition()
        self.pending=OrderedDict();self.principals=set();self.active=Counter()
        self.waiting=0;self.threads=[];self.closed=False
        self.max_pending=max_pending;self.queue_seconds=queue_seconds

    def _start(self):
        if not self.threads:
            self.threads=[threading.Thread(target=self._dispatch,args=(worker,),daemon=True,
                name='maaher-markdown') for worker in self.workers]
            for thread in self.threads:thread.start()

    def _dispatch(self,worker):
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(lambda:self.closed or self.waiting)
                    if self.closed:return
                    # Stable ordering breaks equal-active ties round-robin.
                    tenant=min(self.pending,key=lambda key:self.active[key])
                    jobs=self.pending.pop(tenant);job=jobs.popleft()
                    if jobs:self.pending[tenant]=jobs
                    self.waiting-=1
                    future,scope,value,deadline=job
                    if future.cancelled() or time.monotonic()>deadline:
                        self.principals.discard(scope)
                        if not future.done():future.set_exception(HTTPException(503,'Antrean validasi penuh waktu. Coba lagi',headers={'Retry-After':'1'}))
                        continue
                    if not future.set_running_or_notify_cancel():
                        self.principals.discard(scope);continue
                    self.active[tenant]+=1
                error=None;result=None
                try:result=worker.validate(value,scope)
                except Exception as caught:error=caught
                finally:
                    with self.condition:
                        self.principals.discard(scope);self.active[tenant]-=1
                        if not self.active[tenant]:del self.active[tenant]
                        self.condition.notify_all()
                # Release this principal before waking its caller: a sequential
                # next save must not race its own previous admission record.
                if error is None:future.set_result(result)
                else:future.set_exception(error)
        finally:worker.close()

    def validate(self,value,cache_scope="library"):
        # Reject malformed text before it can occupy a queue entry.
        if not isinstance(value,str) or len(value)>30000:raise ValueError('Materi terlalu panjang')
        if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]',value):raise ValueError('Materi memuat karakter kontrol yang tidak diizinkan')
        try:value.encode('utf8')
        except UnicodeError:raise ValueError('Encoding materi tidak valid') from None
        tenant=cache_scope.split(':',1)[0]
        future=Future()
        with self.condition:
            if self.closed:raise HTTPException(503,'Validator sedang berhenti. Coba lagi',headers={'Retry-After':'1'})
            if cache_scope in self.principals:
                raise HTTPException(429,'Validasi akun Anda masih berlangsung. Tunggu sebelum menyimpan lagi',headers={'Retry-After':'1'})
            if sum(key.split(':',1)[0]==tenant for key in self.principals)>=10:
                raise HTTPException(429,'Kapasitas validasi organisasi sedang penuh. Coba lagi',headers={'Retry-After':'1'})
            if self.waiting>=self.max_pending:
                raise HTTPException(503,'Kapasitas antrean validasi sedang penuh. Coba lagi',headers={'Retry-After':'1'})
            self.principals.add(cache_scope)
            self.pending.setdefault(tenant,deque()).append((future,cache_scope,value,time.monotonic()+self.queue_seconds))
            self.waiting+=1;self._start();self.condition.notify_all()
        try:return future.result(timeout=self.queue_seconds+WALL_SECONDS+.2)
        except FutureTimeout:
            # Remove cancelled waits immediately, freeing their finite capacity.
            with self.condition:
                future.cancel()
                jobs=self.pending.get(tenant)
                if jobs:
                    kept=deque(job for job in jobs if job[0] is not future)
                    if len(kept)!=len(jobs):
                        self.waiting-=1;self.principals.discard(cache_scope)
                        if kept:self.pending[tenant]=kept
                        else:self.pending.pop(tenant,None)
            raise HTTPException(503,'Validasi melewati batas waktu. Coba lagi',headers={'Retry-After':'1'}) from None

    def close(self):
        with self.condition:
            self.closed=True
            for jobs in self.pending.values():
                for future,scope,_,_ in jobs:
                    self.principals.discard(scope)
                    if not future.done():future.set_exception(HTTPException(503,'Validator sedang berhenti'))
            self.pending.clear();self.waiting=0;self.condition.notify_all()
        for thread in self.threads:thread.join(timeout=WALL_SECONDS+.5)
        # Never-started workers have no dispatcher to close them.
        if not self.threads:
            for worker in self.workers:worker.close()


parser=ParserPool(2)
maintenance_parser=ParserPool(1)
atexit.register(parser.close);atexit.register(maintenance_parser.close)
validate=parser.validate
validate_maintenance=maintenance_parser.validate
