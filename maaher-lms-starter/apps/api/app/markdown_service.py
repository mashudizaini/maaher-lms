"""Bounded interactive/maintenance parser processes; fail closed on overload."""
import atexit
from collections import OrderedDict
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


class MarkdownComplexity(ValueError): pass


class Parser:
    def __init__(self):
        self.lock=threading.Lock();self.cache_lock=threading.Lock();self.cache=OrderedDict();self.process=None;self.limits={}

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
        payload=json.dumps({'content':value},ensure_ascii=False).encode()+b'\n';offset=0;reply=bytearray();deadline=time.monotonic()+2.0
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
                            response=json.loads(reply);self.limits=response.get('limits',{})
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
    def __init__(self,count):
        self.workers=[Parser() for _ in range(count)];self.rotation=0;self.rotation_lock=threading.Lock()
    def validate(self,value,cache_scope="library"):
        with self.rotation_lock:
            start=self.rotation;self.rotation=(self.rotation+1)%len(self.workers)
        for n in range(len(self.workers)):
            try:return self.workers[(start+n)%len(self.workers)].validate(value,cache_scope)
            except HTTPException as error:
                if error.status_code!=429:raise
        raise HTTPException(429,'Validasi materi sedang sibuk. Coba lagi sebentar lagi',headers={'Retry-After':'1'})
    def close(self):
        for worker in self.workers:worker.close()


parser=ParserPool(2)
maintenance_parser=ParserPool(1)
atexit.register(parser.close);atexit.register(maintenance_parser.close)
validate=parser.validate
validate_maintenance=maintenance_parser.validate
