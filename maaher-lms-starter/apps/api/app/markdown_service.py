"""Single bounded parser process; fail closed on CPU/wall/crash/busy."""
import atexit
from collections import OrderedDict
import hashlib
import json
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
        self.lock=threading.Lock();self.cache_lock=threading.Lock();self.cache=OrderedDict();self.process=None

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
        payload=json.dumps({'content':value},ensure_ascii=False).encode()+b'\n';offset=0;reply=bytearray();deadline=time.monotonic()+1.5
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
                        if b'\n' in reply:return json.loads(reply)['result']
        raise TimeoutError()

    def validate(self,value,cache_scope="library"):
        if not isinstance(value,str) or len(value)>30000:raise ValueError('Materi terlalu panjang')
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


parser=Parser()
atexit.register(parser.close)
validate=parser.validate
